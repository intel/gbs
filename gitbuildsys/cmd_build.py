#!/usr/bin/python -tt
# vim: ai ts=4 sts=4 et sw=4
#
# Copyright (c) 2012 Intel, Inc.
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

"""Implementation of subcmd: localbuild
"""

import os
import shutil
import pwd
import re
import urlparse

from gitbuildsys.utils import Temp, RepoParser, read_localconf,\
                              guess_spec, show_file_from_rev
from gitbuildsys.errors import GbsError, Usage
from gitbuildsys.conf import configmgr
from gitbuildsys.safe_url import SafeURL
from gitbuildsys.cmd_export import get_packaging_dir
from gitbuildsys.log import LOGGER as log

from gbp.rpm.git import GitRepositoryError, RpmGitRepository
from gbp import rpm
from gbp.errors import GbpError


CHANGE_PERSONALITY = {
            'ia32':  'linux32',
            'i686':  'linux32',
            'i586':  'linux32',
            'i386':  'linux32',
            'ppc':   'powerpc32',
            's390':  's390',
            'sparc': 'linux32',
            'sparcv8': 'linux32',
          }

SUPPORTEDARCHS = [
            'x86_64',
            'i586',
            'armv6l',
            'armv7hl',
            'armv7l',
            'aarch64',
          ]

USERID = pwd.getpwuid(os.getuid())[0]
TMPDIR = None

def formalize_build_conf(profile):
    ''' formalize build conf file name from profile'''

    # build conf file name should not start with digital, see:
    # obs-build/Build.pm:read_config_dist()
    start_digital_re = re.compile(r'^[0-9]')
    if start_digital_re.match(profile):
        profile = 'tizen%s' % profile

    # '-' is not allowed, so replace with '_'
    return profile.replace('-', '_')

def get_binary_name_from_git(args, package_dirs):
    ''' get binary rpm name from specified git package'''

    binary_list = []
    packaging_dir = get_packaging_dir(args)
    if args.commit:
        commit = args.commit
    elif args.include_all:
        commit = 'WC.UNTRACKED'
    else:
        commit = 'HEAD'

    for package_dir in package_dirs:
        main_spec, rest_specs = guess_spec(package_dir, packaging_dir,
                                                 None, commit)
        rest_specs.append(main_spec)
        for spec in rest_specs:
            if args.include_all:
                spec_to_parse = os.path.join(package_dir, spec)
            else:
                content = show_file_from_rev(package_dir, spec, commit)
                if content is None:
                    raise GbsError('failed to checkout %s from commit: %s' %
                                    (spec, commit))
                tmp_spec = Temp(content=content)
                spec_to_parse = tmp_spec.path

            try:
                spec = rpm.SpecFile(spec_to_parse)
            except GbpError, err:
                raise GbsError('%s' % err)
            binary_list.append(spec.name)

    return binary_list

def prepare_repos_and_build_conf(args, arch, profile):
    '''generate repos and build conf options for depanneur'''

    cmd_opts = []
    cache = Temp(prefix=os.path.join(TMPDIR, 'gbscache'),
                       directory=True)
    cachedir = cache.path
    if not os.path.exists(cachedir):
        os.makedirs(cachedir)
    log.info('generate repositories ...')

    if args.skip_conf_repos:
        repos = []
    else:
        repos = [i.url for i in profile.repos]

    if args.repositories:
        for repo in args.repositories:
            try:
                if not urlparse.urlsplit(repo).scheme:
                    if os.path.exists(repo):
                        repo = os.path.abspath(os.path.expanduser(repo))
                    else:
                        log.warning('local repo: %s does not exist' % repo)
                        continue
                opt_repo = SafeURL(repo)
            except ValueError, err:
                log.warning('Invalid repo %s: %s' % (repo, str(err)))
            else:
                repos.append(opt_repo)

    if not repos:
        raise GbsError('No package repository specified.')

    repoparser = RepoParser(repos, cachedir)
    repourls = repoparser.get_repos_by_arch(arch)
    if not repourls:
        raise GbsError('no available repositories found for arch %s under the '
                       'following repos:\n%s' % (arch, '\n'.join(repos)))
    cmd_opts += [('--repository=%s' % url.full) for url in repourls]

    profile = get_profile(args)
    profile_name = formalize_build_conf(profile.name.replace('profile.', '', 1))
    distconf = os.path.join(TMPDIR, '%s.conf' % profile_name)

    if args.dist:
        buildconf = args.dist
    elif profile.buildconf:
        buildconf = profile.buildconf
    else:
        if repoparser.buildconf is None:
            raise GbsError('failed to get build conf from repos, please '
                           'use snapshot repo or specify build config using '
                           '-D option')
        else:
            buildconf = repoparser.buildconf
            log.info('build conf has been downloaded at:\n      %s' \
                       % distconf)
    try:
        shutil.copy(buildconf, distconf)
    except IOError, err:
        raise GbsError("Failed to copy build conf: %s" % (str(err)))

    if not os.path.exists(distconf):
        raise GbsError('No build config file specified, please specify in '\
                       '~/.gbs.conf or command line using -D')

    # must use abspath here, because build command will also use this path
    distconf = os.path.abspath(distconf)

    if not distconf.endswith('.conf') or '-' in os.path.basename(distconf):
        raise GbsError("build config file must end with .conf, and can't "
                       "contain '-'")
    dist = os.path.basename(distconf)[:-len('.conf')]
    cmd_opts += ['--dist=%s' % dist]
    cmd_opts += ['--configdir=%s' % os.path.dirname(distconf)]

    return cmd_opts

def prepare_depanneur_opts(args):
    '''generate extra options for depanneur'''

    cmd_opts = []
    if args.exclude:
        cmd_opts += ['--exclude=%s' % i for i in args.exclude.split(',')]
    if args.exclude_from_file:
        cmd_opts += ['--exclude-from-file=%s' % args.exclude_from_file]
    if args.overwrite:
        cmd_opts += ['--overwrite']
    if args.clean_once:
        cmd_opts += ['--clean-once']
    if args.clean_repos:
        cmd_opts += ['--clean-repos']
    if args.debug:
        cmd_opts += ['--debug']
    if args.incremental:
        cmd_opts += ['--incremental']
    if args.no_configure:
        cmd_opts += ['--no-configure']
    if args.keep_packs:
        cmd_opts += ['--keep-packs']
    if args.baselibs:
        cmd_opts += ['--baselibs']

    #
    if args.package_list:
        package_list = args.package_list.split(',')
        binary_list = get_binary_name_from_git(args, package_list)
        args.binary_list += ','+ ','.join(binary_list)
    if args.package_from_file:
        if not os.path.exists(args.package_from_file):
            raise GbsError('specified package list file %s not exists' % \
                           args.package_from_file)
        with open(args.package_from_file) as fobj:
            pkglist = [pkg.strip() for pkg in fobj.readlines() if pkg.strip()]
            binary_list = get_binary_name_from_git(args, pkglist)
        args.binary_list += ',' + ','.join(binary_list)
    if args.binary_list:
        blist = [i.strip() for i in args.binary_list.split(',')]
        cmd_opts += ['--binary-list=%s' % ','.join(blist)]
    if args.binary_from_file:
        if not os.path.exists(args.binary_from_file):
            raise GbsError('specified binary list file %s not exists' % \
                        args.binary_from_file)
        cmd_opts += ['--binary-from-file=%s' % args.binary_from_file]
    if args.deps:
        cmd_opts += ['--deps']
    if args.rdeps:
        cmd_opts += ['--rdeps']
    cmd_opts += ['--threads=%s' % args.threads]
    cmd_opts += ['--packaging-dir=%s' % get_packaging_dir(args)]

    return cmd_opts

def get_profile(args):
    """
    Get the build profile to be used
    """
    if args.profile:
        profile_name = args.profile if args.profile.startswith("profile.") \
                                    else "profile." + args.profile
        profile = configmgr.build_profile_by_name(profile_name)
    else:
        profile = configmgr.get_current_profile()
    return profile


def main(args):
    """gbs build entry point."""

    global TMPDIR
    TMPDIR = os.path.join(configmgr.get('tmpdir', 'general'), '%s-gbs' % USERID)

    if args.commit and args.include_all:
        raise Usage('--commit can\'t be specified together with '\
                    '--include-all')
    if args.noinit and (args.clean or args.clean_once):
        raise Usage('--noinit can\'t be specified together with '\
                    '--clean or --clean-once')
    workdir = args.gitdir

    try:
        repo = RpmGitRepository(workdir)
        workdir = repo.path
    except GitRepositoryError:
        if args.spec:
            raise GbsError("git project can't be found for --spec, "
                           "give it in argument or cd into it")

    read_localconf(workdir)

    hostarch = os.uname()[4]
    if args.arch:
        buildarch = args.arch
    else:
        buildarch = hostarch
        log.info('No arch specified, using system arch: %s' % hostarch)

    if not buildarch in SUPPORTEDARCHS:
        raise GbsError('arch %s not supported, supported archs are: %s ' % \
                       (buildarch, ','.join(SUPPORTEDARCHS)))

    profile = get_profile(args)
    if args.buildroot:
        build_root = args.buildroot
    elif 'TIZEN_BUILD_ROOT' in os.environ:
        build_root = os.environ['TIZEN_BUILD_ROOT']
    elif profile.buildroot:
        build_root = profile.buildroot
    else:
        build_root = configmgr.get('buildroot', 'general')
    build_root = os.path.expanduser(build_root)
    # transform variables from shell to python convention ${xxx} -> %(xxx)s
    build_root = re.sub(r'\$\{([^}]+)\}', r'%(\1)s', build_root)
    sanitized_profile_name = re.sub("[^a-zA-Z0-9:._-]", "_", profile.name)
    build_root = build_root % {'tmpdir': TMPDIR,
                               'profile': sanitized_profile_name}
    os.environ['TIZEN_BUILD_ROOT'] = os.path.abspath(build_root)

    # get virtual env from system env first
    if 'VIRTUAL_ENV' in os.environ:
        cmd = ['%s/usr/bin/depanneur' % os.environ['VIRTUAL_ENV']]
    else:
        cmd = ['depanneur']

    cmd += ['--arch=%s' % buildarch]

    if args.clean:
        cmd += ['--clean']

    # check & prepare repos and build conf
    if not args.noinit:
        cmd += prepare_repos_and_build_conf(args, buildarch, profile)
    else:
        cmd += ['--noinit']

    cmd += ['--path=%s' % workdir]

    if args.ccache:
        cmd += ['--ccache']

    if args.extra_packs:
        cmd += ['--extra-packs=%s' % args.extra_packs]

    if hostarch != buildarch and buildarch in CHANGE_PERSONALITY:
        cmd = [CHANGE_PERSONALITY[buildarch]] + cmd

    # Extra depanneur special command options
    cmd += prepare_depanneur_opts(args)

    # Extra options for gbs export
    if args.include_all:
        cmd += ['--include-all']
    if args.commit:
        cmd += ['--commit=%s' % args.commit]

    if args.upstream_branch:
        cmd += ['--upstream-branch=%s' % args.upstream_branch]
    if args.upstream_tag:
        cmd += ['--upstream-tag=%s' % args.upstream_tag]
    if args.squash_patches_until:
        cmd += ['--squash-patches-until=%s' % args.squash_patches_until]
    if args.no_patch_export:
        cmd += ['--no-patch-export']

    if args.define:
        cmd += [('--define="%s"' % i) for i in args.define]
    if args.spec:
        cmd += ['--spec=%s' % args.spec]

    log.debug("running command: %s" % ' '.join(cmd))
    retcode = os.system(' '.join(cmd))
    if retcode != 0:
        raise GbsError('some packages failed to be built')
    else:
        log.info('Done')
