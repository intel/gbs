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
import glob
import subprocess
import urlparse

import msger
import utils
import errors
from conf import configmgr

from gbp.scripts.buildpackage_rpm import git_archive, guess_comp_type
from gbp.rpm.git import GitRepositoryError, RpmGitRepository
import gbp.rpm as rpm
from gbp.errors import GbpError

change_personality = {
            'i686':  'linux32',
            'i586':  'linux32',
            'i386':  'linux32',
            'ppc':   'powerpc32',
            's390':  's390',
            'sparc': 'linux32',
            'sparcv8': 'linux32',
          }

obsarchmap = {
            'i686':     'i586',
            'i586':     'i586',
          }

buildarchmap = {
            'i686':     'i686',
            'i586':     'i686',
            'i386':     'i686',
          }

supportedarchs = [
            'x86_64',
            'i686',
            'i586',
            'armv7hl',
            'armv7el',
            'armv7tnhl',
            'armv7nhl',
            'armv7l',
          ]

def do(opts, args):

    if os.geteuid() != 0:
        msger.error('Root permission is required, please try again with sudo')

    workdir = os.getcwd()
    if len(args) > 1:
        msger.error('only one work directory can be specified in args.')
    if len(args) == 1:
        workdir = args[0]

    hostarch = utils.get_hostarch()
    buildarch = hostarch
    if opts.arch:
        if opts.arch in buildarchmap:
            buildarch = buildarchmap[opts.arch]
        else:
            buildarch = opts.arch
    if not buildarch in supportedarchs:
        msger.error('arch %s not supported, supported archs are: %s ' % \
                   (buildarch, ','.join(supportedarchs)))

    specs = glob.glob('%s/packaging/*.spec' % workdir)
    if not specs:
        msger.error('no spec file found under /packaging sub-directory')

    specfile = utils.guess_spec(workdir, opts.spec)
    distconf = configmgr.get('distconf', 'build')
    if opts.dist:
        distconf = opts.dist

    build_cmd  = configmgr.get('build_cmd', 'build')
    build_root = configmgr.get('build_root', 'build')
    if opts.buildroot:
        build_root = opts.buildroot
    cmd = [ build_cmd,
            '--root='+build_root,
            '--dist='+distconf,
            '--arch='+buildarch ]
    build_jobs = utils.get_processors()
    if build_jobs > 1:
        cmd += ['--jobs=%s' % build_jobs]
    if opts.clean:
        cmd += ['--clean']
    if opts.debuginfo:
        cmd += ['--debug']

    if opts.repositories:
        for repo in opts.repositories:
            cmd += ['--repository='+repo]
    else:
        msger.error('No package repository specified.')

    if opts.noinit:
        cmd += ['--no-init']
    if opts.ccache:
        cmd += ['--ccache']
    cmd += [specfile]

    if hostarch != buildarch and buildarch in change_personality:
        cmd = [ change_personality[buildarch] ] + cmd

    if buildarch.startswith('arm'):
        try:
            utils.setup_qemu_emulator()
        except errors.QemuError, exc:
            msger.error('%s' % exc)

    spec = rpm.parse_spec(specfile)
    if not spec.name or not spec.version:
        msger.error('can\'t get correct name or version from spec file.')

    urlres = urlparse.urlparse(spec.orig_file)

    tarball = 'packaging/%s' % os.path.basename(urlres.path)
    msger.info('generate tar ball: %s' % tarball)
    try:
        repo = RpmGitRepository(workdir)
    except GitRepositoryError:
        msger.error("%s is not a git repository" % (os.path.curdir))

    try:
        comp_type = guess_comp_type(spec)
        if not git_archive(repo, spec, "%s/packaging" % workdir, 'HEAD',
                           comp_type, comp_level=9, with_submodules=True):
            msger.error("Cannot create source tarball %s" % tarball)
    except GbpError, exc:
        msger.error(str(exc))
 
    if opts.incremental:
        cmd += ['--rsync-src=%s' % os.path.abspath(workdir)]
        cmd += ['--rsync-dest=/home/abuild/rpmbuild/BUILD/%s-%s' % \
                (spec.name, spec.version)]

    msger.info(' '.join(cmd))

    # runner.show() can't support interactive mode, so use subprocess insterad.
    try:
        rc = subprocess.call(cmd)
        if rc:
            msger.error('rpmbuild fails')
        else:
            msger.info('The buildroot was: %s' % build_root)
            msger.info('Done')
    except KeyboardInterrupt, i:
        msger.info('keyboard interrupt, killing build ...')
        subprocess.call(cmd + ["--kill"])
        msger.error('interrrupt from keyboard')
    finally:
        os.unlink("%s/%s" % (workdir, tarball))
