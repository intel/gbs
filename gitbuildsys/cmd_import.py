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

"""Implementation of subcmd: import
"""

import os

# internal modules
import msger
import errors
import git
import srcserver as ss

def do(opts, args):
    if not args or len(args) != 1:
        raise errors.Usage('Must specify the path of tarball and only one')

    tarfp = args[0]
    tarname = os.path.basename(tarfp)

    gitname = os.path.basename(git.config('remote.origin.url'))


    # FIXME "pkg_name" in shell means the obs prj?
    if opts.obsprj:
        obspkg = opts.obsprj
    else:
        obspkg = gitname

    params = {'parameter': [
                {"name": "pkg.tar.bz2", "file": "file0"},
                {"name": "pkg", "value": tarname}
             ]}

    msger.info('Uploading tarball %s to the source server...' % tarfp)
    ss.upload(params, tarfp)
    # TODO need to check the result and get the md5sum
    # TODO update sources automatically?
