#!/usr/bin/python -tt
# vim: ai ts=4 sts=4 et sw=4
#
# Copyright (c) 2011 Intel, Inc.
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the Free
# Software Foundation; version 2 of the License
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
# or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License
# for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc., 59
# Temple Place - Suite 330, Boston, MA 02111-1307, USA.

"""Implementation of subcmd: build
"""

import os
import glob

from gitbuildsys import utils

from gitbuildsys.errors import Usage, ObsError, GbsError
from gitbuildsys.conf import configmgr, encode_passwd
from gitbuildsys.oscapi import OSC, OSCError
from gitbuildsys.cmd_export import export_sources, get_packaging_dir
from gitbuildsys.cmd_build import get_profile
from gitbuildsys.log import LOGGER as log
from gitbuildsys.log import DEBUG

import gbp.rpm
from gbp.rpm.git import GitRepositoryError, RpmGitRepository
from gbp.errors import GbpError

OSCRC_TEMPLATE = """[general]
apiurl = %(apiurl)s
plaintext_passwd=0
use_keyring=0
http_debug = %(http_debug)s
debug = %(debug)s
gnome_keyring=0
[%(apiurl)s]
user=%(user)s
passx=%(passwdx)s
"""


def main(args):
    """gbs remotebuild entry point."""

    obsconf = get_profile(args).obs

    if not obsconf or not obsconf.url:
        raise GbsError('no obs api found, please add it to gbs conf '
                       'and try again')

    apiurl = obsconf.url

    if not apiurl.user:
        raise GbsError('empty user is not allowed for remotebuild, please '\
                       'add user/passwd to gbs conf, and try again')

    if args.commit and args.include_all:
        raise Usage('--commit can\'t be specified together with '
                           '--include-all')

    obs_repo = args.repository
    obs_arch = args.arch

    if args.buildlog and None in (obs_repo, obs_arch):
        raise GbsError('please specify arch(-A) and repository(-R)')

    try:
        repo = RpmGitRepository(args.gitdir)
    except GitRepositoryError, err:
        raise GbsError(str(err))

    workdir = repo.path

    if not (args.buildlog or args.status):
        utils.git_status_checker(repo, args)

    packaging_dir = get_packaging_dir(args)

    if args.commit:
        commit = args.commit
    elif args.include_all:
        commit = 'WC.UNTRACKED'
    else:
        commit = 'HEAD'

    relative_spec = utils.guess_spec(workdir, packaging_dir,
                                     args.spec, commit)[0]

    if args.include_all:
        # include_all means to use work copy,
        # otherwise use the reversion in git history
        spec_to_parse = os.path.join(workdir, relative_spec)
    else:
        content = utils.show_file_from_rev(workdir, relative_spec, commit)
        if content is None:
            raise GbsError('failed to checkout %s from commit: %s' % 
                            (relative_spec, commit))

        tmp_spec = utils.Temp(content=content)
        spec_to_parse = tmp_spec.path

    # get 'name' and 'version' from spec file
    try:
        spec = gbp.rpm.parse_spec(spec_to_parse)
    except GbpError, err:
        raise GbsError('%s' % err)

    if not spec.name:
        raise GbsError("can't get correct name.")
    package = spec.name

    base_prj = None
    if args.base_obsprj:
        base_prj = args.base_obsprj
    elif obsconf.base:
        base_prj = obsconf.base

    if args.target_obsprj is None:
        if obsconf.target:
            target_prj = obsconf.target
        else:
            target_prj = "home:%s:gbs" % apiurl.user
            if base_prj:
                target_prj += ":%s" % base_prj
    else:
        target_prj = args.target_obsprj

    api_passwd = apiurl.passwd if apiurl.passwd else ''
    # Create temporary oscrc
    oscrc = OSCRC_TEMPLATE % {
                "http_debug": 1 if log.level == DEBUG else 0,
                "debug": 1 if log.level == DEBUG else 0,
                "apiurl": apiurl,
                "user": apiurl.user,
                "passwdx": encode_passwd(api_passwd),
            }

    tmpdir     = configmgr.get('tmpdir', 'general')
    tmpd = utils.Temp(prefix=os.path.join(tmpdir, '.gbs_remotebuild_'),
                      directory=True)
    exportdir = tmpd.path
    tmpf = utils.Temp(dirn=exportdir, prefix='.oscrc', content=oscrc)
    oscrcpath = tmpf.path

    api = OSC(apiurl, oscrc=oscrcpath)

    try:
        if args.buildlog:
            archlist = []
            status = api.get_results(target_prj, package)

            for build_repo in status.keys():
                for arch in status[build_repo]:
                    archlist.append('%-15s%-15s' % (build_repo, arch))
            if not obs_repo or not obs_arch or obs_repo not in status.keys() \
                   or obs_arch not in status[obs_repo].keys():
                raise GbsError('no valid repo / arch specified for buildlog, '\
                               'valid arguments of repo and arch are:\n%s' % \
                               '\n'.join(archlist))
            if status[obs_repo][obs_arch] not in ['failed', 'succeeded',
                                                  'building', 'finishing']:
                raise GbsError('build status of %s for %s/%s is %s, '\
                               'no build log.' % (package, obs_repo, obs_arch,
                                                  status[obs_repo][obs_arch]))
            log.info('build log for %s/%s/%s/%s' % (target_prj, package,
                                                      obs_repo, obs_arch))
            print api.get_buildlog(target_prj, package, obs_repo, obs_arch)

            return 0

        if args.status:
            results = []

            status = api.get_results(target_prj, package)

            for build_repo in status.keys():
                for arch in status[build_repo]:
                    stat = status[build_repo][arch]
                    results.append('%-15s%-15s%-15s' % (build_repo, arch, stat))
            if results:
                log.info('build results from build server:\n%s' \
                          % '\n'.join(results))
            else:
                log.info('no build results from build server')
            return 0

    except OSCError, err:
        raise GbsError(str(err))

    with utils.Workdir(workdir):
        export_sources(repo, commit, exportdir, relative_spec, args)

    try:
        commit_msg = repo.get_commit_info(args.commit or 'HEAD')['subject']
    except GitRepositoryError, exc:
        raise GbsError('failed to get commit info: %s' % exc)

    files = glob.glob("%s/*" % exportdir)
    build_repos = None
    try:
        log.info('checking status of obs project: %s ...' % target_prj)
        if not api.exists(target_prj):
            log.info('creating new project %s' % (target_prj))
            api.create_project(target_prj, base_prj)
        else:
            build_repos = api.get_repos_of_project(target_prj)
            if not build_repos:
                log.warning("no available build repos for %s" % target_prj)
        if api.exists(target_prj, package):
            _old, _not_changed, changed, new = api.diff_files(target_prj,
                                                              package, files)
            commit_files = changed + new
        else:
            log.info('creating new package %s/%s' % (target_prj, package))
            api.create_package(target_prj, package)
            # new project - submitting all local files
            commit_files = files
    except OSCError, err:
        raise GbsError(str(err))

    if not commit_files:
        if build_repos:
            log.warning("no local changes found. Triggering rebuild")
            api.rebuild(target_prj, package, obs_arch)
        else:
            log.warning("no local changes found. can't trigger rebuild "
                          "as no available build repos found")
            return 0
    else:
        log.info('commit packaging files to build server ...')
        commit_files = [(fpath, fpath in commit_files) for fpath in files]
        try:
            api.commit_files(target_prj, package, commit_files, commit_msg)
        except ObsError as exc:
            raise GbsError('commit packages fail: %s, please check the '
                       'permission of target project:%s' % (exc, target_prj))

        log.info('local changes submitted to build server successfully')

    log.info('follow the link to monitor the build progress:\n'
               '  %s/package/show?package=%s&project=%s' \
               % (apiurl.replace('api', 'build'), package, target_prj))
