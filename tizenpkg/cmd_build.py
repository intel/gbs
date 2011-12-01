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

"""Implementation of subcmd: build
"""

raise ImportError('skip me')

import os
import tarfile

import git
import runner
import msger
import srcserver as ss
from conf import configmgr

def do(opts, args):

    if not os.path.isdir('.git'):
        msger.error('must run this command under a git tree')

    if git.branch(all=False, current=True)[0] != 'release':
        msger.error('must run this command under release branch')

    gitsts = git.status()
    if 'M ' in gitsts or ' M' in gitsts:
        msger.warning('local changes not committed')

    params = {'parameter': []}

    # pkg:prjname
    giturl = git.config('remote.origin.url')
    prjname = os.path.basename(giturl)
    params['parameter'].append({"name": "pkg",
                                "value": prjname})

    # obsproject:obsprj
    passwdx = configmgr.get('passwdx')
    params['parameter'].append({"name": "parameters",
                                "value": "obsproject='%s';passwdx='%s'" %(opts.obsprj, passwdx)})

    # prepare package.tar.bz2
    tarfp = 'package.tar.bz2'
    tar = tarfile.open(tarfp, 'w:bz2')
    for f in git.ls_files():
        tar.add(f)
    tar.close()

    params['parameter'].append({"name": tarfp,
                                "file": "file0"})

    msger.info("Submiting your changes to build server ...")
    ss.build_trigger(params, tarfp)

    time.sleep(0.5)
    result = ss.build_mylastresult()

    if result['result'] != 'SUCCESS':
        msger.error('remote server exception')

    os.remove(tarfp)
    msger.info('your local changes has been submitted to build server.')

