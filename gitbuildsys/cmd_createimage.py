#!/usr/bin/python -tt
# vim: ai ts=4 sts=4 et sw=4
#
# Copyright (c) 2013 Intel, Inc.
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

"""Implementation of subcmd: createimage
"""

import os

from gitbuildsys.errors import GbsError
from gitbuildsys.log import LOGGER as log

def createimage(args, ks_file):
    '''create image using mic'''
    extra_mic_opts = []
    if args.outdir:
        extra_mic_opts = ['--outdir=%s' % args.outdir]
    if args.tmpfs:
        extra_mic_opts += ['--tmpfs']
    extra_mic_opts += ['--record-pkgs=name']
    mic_cmd = 'sudo mic create auto %s %s' % (ks_file, ' '.join(extra_mic_opts))
    log.debug(mic_cmd)
    os.system(mic_cmd)

def main(args):
    '''main entrance for createimage'''

    if args.ks_file:
        if not os.path.exists(args.ks_file):
            raise GbsError('specified ks file %s does not exist' % args.ks_file)
        log.info('creating image for ks file: %s' % args.ks_file)
        createimage(args, args.ks_file)
