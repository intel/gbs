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
import re
import subprocess
import shutil
import pwd

from gitbuildsys import msger, utils, errors
from gitbuildsys.conf import configmgr
from gitbuildsys.safe_url import SafeURL

from gbp.rpm.git import GitRepositoryError, RpmGitRepository
from gitbuildsys.cmd_build import get_hostarch, setup_qemu_emulator

CHANGE_PERSONALITY = {
            'i686':  'linux32',
            'i586':  'linux32',
            'i386':  'linux32',
            'ppc':   'powerpc32',
            's390':  's390',
            'sparc': 'linux32',
            'sparcv8': 'linux32',
          }

BUILDARCHMAP = {
            'ia32':     'i586',
            'i686':     'i586',
            'i586':     'i586',
            'i386':     'i586',
          }

SUPPORTEDARCHS = [
            'ia32',
            'i686',
            'i586',
            'armv7hl',
            'armv7el',
            'armv7tnhl',
            'armv7nhl',
            'armv7l',
          ]

def prepare_repos_and_build_conf(opts, arch):
    '''generate repos and build conf options for depanneur'''

    cmd_opts = []
    userid     = pwd.getpwuid(os.getuid())[0]
    tmpdir     = os.path.join(configmgr.get('tmpdir', 'general'),
                              '%s-gbs' % userid)
    cache = utils.Temp(prefix=os.path.join(tmpdir, 'gbscache'),
                       directory=True)
    cachedir  = cache.path
    if not os.path.exists(cachedir):
        os.makedirs(cachedir)
    msger.info('generate repositories ...')

    if opts.skip_conf_repos:
        repos = []
    else:
        repos = [i.url for i in configmgr.get_current_profile().repos]

    if opts.repositories:
        repos.extend([ SafeURL(i) for i in opts.repositories ])
    if not repos:
        msger.error('No package repository specified.')

    repoparser = utils.RepoParser(repos, cachedir)
    repourls = repoparser.get_repos_by_arch(arch)
    if not repourls:
        msger.error('no repositories found for arch: %s under the '\
                    'following repos:\n      %s' % \
                    (arch, '\n'.join(repos)))
    for url in repourls:
        if not  re.match('https?://.*', url) and \
           not (url.startswith('/') and os.path.exists(url)):
            msger.error("Invalid repo url: %s" % url)
        cmd_opts += ['--repository=%s' % url.full]

    if opts.dist:
        distconf = opts.dist
    else:
        if repoparser.buildconf is None:
            msger.warning('failed to get build conf, use default')
            distconf = configmgr.get('distconf', 'build')
        else:
            shutil.copy(repoparser.buildconf, tmpdir)
            distconf = os.path.join(tmpdir, os.path.basename(\
                                    repoparser.buildconf))
            msger.info('build conf has been downloaded at:\n      %s' \
                       % distconf)

    if distconf is None:
        msger.error('No build config file specified, please specify in '\
                    '~/.gbs.conf or command line using -D')
    target_conf = os.path.basename(distconf).replace('-', '')
    os.rename(distconf, os.path.join(os.path.dirname(distconf), target_conf))
    dist = target_conf.rsplit('.', 1)[0]
    cmd_opts += ['--dist=%s' % dist]
    cmd_opts += ['--configdir=%s' % os.path.dirname(distconf)]

    return cmd_opts

def prepare_depanneur_opts(opts):
    '''generate extra options for depanneur'''

    cmd_opts = []
    if opts.exclude:
        cmd_opts += ['--exclude=%s' % i for i in opts.exclude]
    if opts.exclude_from_file:
        cmd_opts += ['--exclude-from-file=%s' % opts.exclude_from_file]
    if opts.overwrite:
        cmd_opts += ['--overwrite']
    if opts.clean_once:
        cmd_opts += ['--clean-once']
    if opts.debug:
        cmd_opts += ['--debug']
    if opts.incremental:
        cmd_opts += ['--incremental']
    if opts.keepgoing:
        cmd_opts += ['--keepgoing']
    if opts.no_configure:
        cmd_opts += ['--no-configure']
    if opts.binary_list:
        if not os.path.exists(opts.binary_list):
            msger.error('specified binary list file %s not exists' %\
                        opts.binary_list)
        cmd_opts += ['--binary=%s' % opts.binary_list]
    cmd_opts += ['--threads=%s' % opts.threads]

    return cmd_opts

def do(opts, args):

    workdir = os.getcwd()
    if len(args) > 1:
        msger.error('only one work directory can be specified in args.')
    if len(args) == 1:
        workdir = os.path.abspath(args[0])

    if opts.commit and opts.include_all:
        raise errors.Usage('--commit can\'t be specified together with '\
                           '--include-all')

    try:
        repo = RpmGitRepository(workdir)
        workdir = repo.path
    except GitRepositoryError:
        pass

    hostarch = get_hostarch()
    if opts.arch:
        buildarch = opts.arch
    else:
        buildarch = hostarch
        msger.info('No arch specified, using system arch: %s' % hostarch)
    if buildarch in BUILDARCHMAP:
        buildarch = BUILDARCHMAP[buildarch]

    if not buildarch in SUPPORTEDARCHS:
        msger.error('arch %s not supported, supported archs are: %s ' % \
                   (buildarch, ','.join(SUPPORTEDARCHS)))

    build_root = os.path.expanduser('~/GBS-ROOT/')
    if opts.buildroot:
        build_root = opts.buildroot

    # get virtual env from system env first
    if 'VIRTUAL_ENV' not in os.environ:
        os.environ['VIRTUAL_ENV'] = '/'

    if 'TIZEN_BUILD_ROOT' not in os.environ:
        os.environ['TIZEN_BUILD_ROOT'] = build_root

    cmd = ['%s/usr/bin/depanneur' % os.environ['VIRTUAL_ENV']]
    cmd += ['--arch=%s' % buildarch]

    if opts.clean:
        cmd += ['--clean']

    # check & prepare repos and build conf
    cmd += prepare_repos_and_build_conf(opts, buildarch)

    cmd += ['--path=%s' % workdir]

    if opts.ccache:
        cmd += ['--ccache']

    if opts.extra_packs:
        cmd += ['--extra-packs=%s' % opts.extra_packs]

    if hostarch != buildarch and buildarch in CHANGE_PERSONALITY:
        cmd = [ CHANGE_PERSONALITY[buildarch] ] + cmd

    if buildarch.startswith('arm'):
        try:
            setup_qemu_emulator()
        except errors.QemuError, exc:
            msger.error('%s' % exc)

    # Extra depanneur special command options
    cmd += prepare_depanneur_opts(opts)

    # Extra options for gbs export
    if opts.include_all:
        cmd += ['--include-all']
    if opts.commit:
        cmd += ['--commit=%s' % opts.commit]

    msger.debug("running command: %s" % ' '.join(cmd))
    if subprocess.call(cmd):
        msger.error('rpmbuild fails')
    else:
        dist = [opt[len('--dist='):] for opt in cmd \
                                     if opt.startswith('--dist=')][0]
        repodir = os.path.join(build_root, 'local', 'repos', dist)
        msger.info('generated RPM packages can be found from local repo:'\
                   '\n     %s' % repodir)
        msger.info('build roots located in:\n     %s' % \
                   os.path.join(build_root, 'local', 'scratch.{arch}.*'))
        msger.info('Done')
