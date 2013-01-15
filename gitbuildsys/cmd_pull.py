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

"""Implementation of subcmd: pull
"""

from gitbuildsys.conf import configmgr
from gitbuildsys.errors import GbsError
from gitbuildsys.log import LOGGER as log
from gitbuildsys.log import waiting

from gbp.scripts.pull import main as gbp_pull


@waiting
def do_pull(*args, **kwargs):
    """Wrapper for gbp-pull, prints a progress indicator"""
    return gbp_pull(*args, **kwargs)

def main(args):
    """gbs export entry point."""

    # Determine upstream branch
    if args.upstream_branch:
        upstream_branch = args.upstream_branch
    else:
        upstream_branch = configmgr.get('upstream_branch', 'general')

    # Construct GBP cmdline arguments
    gbp_args = ['dummy argv[0]',
                '--color-scheme=magenta:green:yellow:red',
                '--pristine-tar',
                '--upstream-branch=%s' % upstream_branch,
                '--packaging-branch=master']
    if args.depth:
        gbp_args.append('--depth=%s' % args.depth)
    if args.force:
        gbp_args.append('--force=clean')
    if args.all:
        gbp_args.append('--all')
    if args.debug:
        gbp_args.append("--verbose")

    # Clone
    log.info('updating from remote')
    ret = do_pull(gbp_args)
    if ret == 2:
        raise GbsError('Failed to update some of the branches!')
    elif ret:
        raise GbsError('Update failed!')

    log.info('finished')

