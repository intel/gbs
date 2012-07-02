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
import tempfile
import glob
import shutil

import msger
from conf import configmgr
import buildservice
import obspkg
import errors
import utils

import gbp.rpm
from gbp.scripts.buildpackage_rpm import git_archive, guess_comp_type
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

APISERVER   = configmgr.get('build_server', 'remotebuild')
USER        = configmgr.get('user', 'remotebuild')
PASSWDX     = configmgr.get('passwdx', 'remotebuild')

def do(opts, args):

    obs_repo = None
    obs_arch = None

    if len(args) == 0:
        workdir = os.getcwd()
    elif len(args) == 1:
        workdir = os.path.abspath(args[0])
    elif len(args) == 2 and opts.buildlog:
        workdir = os.getcwd()
        obs_repo = args[0]
        obs_arch = args[1]
    elif len(args) == 3 and opts.buildlog:
        workdir = os.path.abspath(args[0])
        obs_repo = args[1]
        obs_arch = args[2]
    else:
        msger.error('Invalid arguments, see gbs remotebuild -h for more info')

    try:
        repo = RpmGitRepository(workdir)
        if repo.get_branch() is None:
            msger.error('currently not on a branch')
    except GitRepositoryError, err:
        msger.error(str(err))

    workdir = repo.path

    tmpdir = os.path.join(workdir, 'packaging')
    if not os.path.exists(tmpdir):
        os.makedirs(tmpdir)

    if not os.access(tmpdir, os.W_OK|os.R_OK|os.X_OK):
        msger.error('No access permission to %s, please check' % tmpdir)

    oscrc = OSCRC_TEMPLATE % {
                "http_debug": 1 if msger.get_loglevel() == 'debug' else 0,
                "debug": 1 if msger.get_loglevel() == 'verbose' else 0,
                "apiurl": APISERVER,
                "user": USER,
                "passwdx": PASSWDX,
            }
    (fds, oscrcpath) = tempfile.mkstemp(dir=tmpdir, prefix='.oscrc')
    os.close(fds)
    with file(oscrcpath, 'w+') as foscrc:
        foscrc.write(oscrc)

    # TODO: check ./packaging dir at first
    specs = glob.glob('%s/packaging/*.spec' % workdir)
    if not specs:
        msger.error('no spec file found under /packaging sub-directory')

    specfile = utils.guess_spec(workdir, opts.spec)
    # get 'name' and 'version' from spec file
    try:
        spec = gbp.rpm.parse_spec(specfile)
    except GbpError, err:
        msger.error('%s' % err)

    if not spec.name or not spec.version:
        msger.error('can\'t get correct name or version from spec file.')

    if opts.base_obsprj is None:
        # TODO, get current branch of git to determine it
        base_prj = 'Tizen:Main'
    else:
        base_prj = opts.base_obsprj

    if opts.target_obsprj is None:
        target_prj = "home:%s:gbs:%s" % (USER, base_prj)
    else:
        target_prj = opts.target_obsprj

    if opts.buildlog:
        bs = buildservice.BuildService(apiurl=APISERVER, oscrc=oscrcpath)
        archlist = []
        status = bs.get_results(target_prj, spec.name)
        for repository in status.keys():
            for arch in status[repository]:
                archlist.append('%-15s%-15s' % (repository, arch))
        if not obs_repo or not obs_arch or obs_repo not in status.keys() or \
           obs_arch not in status[obs_repo].keys():
            msger.info('please specify correct repo / arch for buildlog')
            msger.info('valid arguments of repo and arch are:\n%s' % \
                       '\n'.join(archlist))
            return 1
        if status[obs_repo][obs_arch] not in ['failed', 'succeeded', \
                                                                   'building']:
            msger.error('build status of %s for %s/%s is %s, no build log.' % \
                  (spec.name, obs_repo, obs_arch, status[obs_repo][obs_arch]))
        bs.get_buildlog(target_prj, spec.name, obs_repo, obs_arch)
        return 0

    if opts.status:
        bs = buildservice.BuildService(apiurl=APISERVER, oscrc=oscrcpath)
        results = []
        status = bs.get_results(target_prj, spec.name)
        for repository in status.keys():
            for arch in status[repository]:
                stat = status[repository][arch]
                results.append('%-15s%-15s%-15s' % (repository, arch, stat))
        msger.info('build results from build server:\n%s' % '\n'.join(results))
        return 0

    prj = obspkg.ObsProject(target_prj, apiurl = APISERVER, oscrc = oscrcpath)
    msger.info('checking status of obs project: %s ...' % target_prj)
    if prj.is_new():
        # FIXME: How do you know that a certain user does not have permission to
        # create any project, anywhewre?
        if opts.target_obsprj and not target_prj.startswith('home:%s:' % USER):
            msger.error('no permission to create project %s, only sub projects'\
                    'of home:%s are allowed ' % (target_prj, USER))
        msger.info('creating %s for package build ...' % target_prj)
        prj.branch_from(base_prj)

    msger.info('checking out %s/%s to %s ...' % (target_prj, spec.name, tmpdir))

    target_prj_path = os.path.join(tmpdir, target_prj)
    if os.path.exists(target_prj_path) and \
       not os.access(target_prj_path, os.W_OK|os.R_OK|os.X_OK):
        msger.error('No access permission to %s, please check' \
                        % target_prj_path)

    localpkg = obspkg.ObsPackage(tmpdir, target_prj, spec.name,
                                 APISERVER, oscrcpath)
    oscworkdir = localpkg.get_workdir()
    localpkg.remove_all()

    with utils.Workdir(workdir):
        commit = opts.commit or 'HEAD'
        relative_spec = specfile.replace('%s/' % workdir, '')
        try:
            comp_type = guess_comp_type(spec)
            if not git_archive(repo, spec, oscworkdir, commit,
                               comp_type, comp_level=9, with_submodules=True):
                msger.error("Cannot create source tarball %s" % tarball)
            git_files = repo.list_files()
            for f in git_files:
                if f.startswith('packaging/'):
                    shutil.copy(f, oscworkdir)
        except (GbpError, GitRepositoryError), excobj:
            msger.error("Repository error: %s" % excobj)

    localpkg.update_local()

    try:
        commit_msg = repo.get_commit_info('HEAD')['subject']
        msger.info('commit packaging files to build server ...')
        localpkg.commit (commit_msg)
    except errors.ObsError, exc:
        msger.error('commit packages fail: %s, please check the permission '\
                    'of target project:%s' % (exc,target_prj))
    except GitRepositoryError, exc:
        msger.error('failed to get commit info: %s' % exc)

    os.unlink(oscrcpath)
    msger.info('local changes submitted to build server successfully')
    msger.info('follow the link to monitor the build progress:\n'
               '  %s/package/show?package=%s&project=%s' \
               % (APISERVER.replace('api', 'build'), spec.name, target_prj))
