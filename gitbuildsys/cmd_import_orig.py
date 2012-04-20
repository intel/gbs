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
import msger

from gbp.scripts.import_orig_rpm import main as gbp_import_orig

def do(opts, args):

    if len(args) != 1:
        msger.error('missing argument, please run gbs import-orig --help.')

    if not opts.author_name:
        msger.error('commit user name must be specified')
    if not opts.author_email:
        msger.error('commit user email must be specified')

    if gbp_import_orig(['argv[0] placeholder', args[0]]):
        msger.error('Failed to import %s' % args[0])

    msger.info('done.')
