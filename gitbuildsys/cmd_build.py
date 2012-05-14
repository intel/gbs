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

"""Implementation of subcmd: build
"""

import os
import sys
import time
import tempfile
import glob
import shutil
import subprocess
import urlparse

import msger
import runner
import utils
import errors
from conf import configmgr
import git
import buildservice

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
        msger.error('Root permission is required, please use sudo and try again')

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

    specfile = specs[0] #TODO:
    if len(specs) > 1:
        msger.warning('multiple specfiles found.')

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
        cmd = [ change_personality[buildarch] ] + cmd;

    if buildarch.startswith('arm'):
        try:
            utils.setup_qemu_emulator()
        except errors.QemuError, e:
            msger.error('%s' % e)

    name = utils.parse_spec(specfile, 'name')
    version = utils.parse_spec(specfile, 'version')
    if not name or not version:
        msger.error('can\'t get correct name or version from spec file.')

    source = utils.parse_spec(specfile, 'SOURCE0')
    urlres = urlparse.urlparse(source)

    tarball = 'packaging/%s' % os.path.basename(urlres.path)
    msger.info('generate tar ball: %s' % tarball)
    mygit = git.Git(workdir)
    mygit.archive("%s-%s/" % (name, version), tarball)

    if opts.incremental:
        cmd += ['--rsync-src=%s' % os.path.abspath(workdir)]
        cmd += ['--rsync-dest=/home/abuild/rpmbuild/BUILD/%s-%s' % (name, version)]

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
