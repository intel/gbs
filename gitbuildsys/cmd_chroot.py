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

"""Implementation of subcmd: chroot
"""

import os
import subprocess

import msger
from conf import configmgr

def do(opts, args):

    if opts.arch in ['ia32', 'i686', 'i586', 'i386']:
        arch = 'i686'
    else:
        arch = opts.arch
    userid     = configmgr.get('user', 'remotebuild')
    tmpdir     = configmgr.get('tmpdir', 'general')
    build_root = os.path.join(tmpdir, userid, 'gbs-buildroot.%s' % arch)
    running_lock = '%s/not-ready' % build_root
    if os.path.exists(running_lock) or not os.path.exists(build_root):
        msger.error('build root %s is not ready' % build_root)

    msger.info('chroot %s' % build_root)
    user = 'abuild'
    if opts.root:
        user = 'root'
    cmd = ['sudo', 'chroot', build_root, 'su', user]
    try:
        subprocess.call(['sudo', 'cp', '/etc/resolv.conf', build_root + \
                         '/etc/resolv.conf'])
    except:
        msger.warning('failed to setup /etc/resolv.conf')

    try:
        build_env = os.environ
        build_env['PS1']="(tizen-build-env)@\h \W]\$ "
        subprocess.call(cmd, env=build_env)
    except OSError, err:
        msger.error('failed to chroot to %s: %s' % (build_root, err))
    except KeyboardInterrupt:
        msger.info('keyboard interrupt ...')
