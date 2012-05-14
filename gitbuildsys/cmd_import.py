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

"""Implementation of subcmd: import
"""
import os

import msger

from gbp.scripts.import_srpm import main as gbp_import_srpm
from gbp.scripts.import_orig_rpm import main as gbp_import_orig

def do(opts, args):

    if opts.author_name:
        os.environ["GIT_AUTHOR_NAME"] = opts.author_name
    if opts.author_email:
        os.environ["GIT_AUTHOR_EMAIL"] = opts.author_email

    if len(args) < 1:
        msger.error('missing argument, please reference gbs import --help.')
    if len(args) > 1:
        msger.error('too many arguments! Please reference gbs import --help.')
    if not os.path.exists(args[0]):
        msger.error('%s not exist' % specfile)

    params = ["argv[0] placeholder", "--packaging-dir=packaging",
              "--upstream-branch=%s" % opts.upstream_branch, args[0]]

    if args[0].endswith('.src.rpm'):
        if gbp_import_srpm(params):
            msger.error("Failed to import %s" % args[0])
    elif args[0].endswith('.spec'):
        params.insert(1, "--unpacked")
        if gbp_import_srpm(params):
            msger.error("Failed to import %s" % args[0])
    else:
        if opts.no_merge:
            params.insert(1, '--no-merge')
        if gbp_import_orig(params):
            msger.error('Failed to import %s' % args[0])

    msger.info('done.')
