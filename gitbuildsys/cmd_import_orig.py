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
import time
import tempfile
import glob
import shutil

import msger
import runner
import utils
from conf import configmgr
import git
import errors

USER        = configmgr.get('user', 'build')
TMPDIR      = configmgr.get('tmpdir')
COMM_NAME   = configmgr.get('commit_name', 'import')
COMM_EMAIL  = configmgr.get('commit_email', 'import')

def do(opts, args):

    workdir = os.getcwd()
    tmpdir = '%s/%s' % (TMPDIR, USER)
    if not os.path.exists(tmpdir):
        os.makedirs(tmpdir)

    if len(args) != 1:
        msger.error('missing argument, please reference gbs import-orig --help.')
    else:
        tarball = args[0]

    try:
        repo = git.Git('.')
    except errors.GitInvalid:
        msger.error("No git repository found.")

    tardir = tempfile.mkdtemp(prefix='%s/' % (tmpdir))
    upstream = utils.UpstreamTarball(tarball)
    (pkgname, pkgversion) = upstream.guess_version() or ('', '')
    if not ( pkgname and pkgversion ):
        msger.error('can\'t parse the package name or version! Please check the tarball.' )


    try:
        msger.info('unpack upstream tar ball ...')
        upstream.unpack(tardir)
    except errors.UnpackError:
        msger.error('Unpacking %s failed' % tarball)
    except errors.FormatError, e:
        msger.error(e.msg)

    tag = repo.version_to_tag("%(version)s", pkgversion)
    msg = "Upstream version %s" % (pkgversion)

    if opts.upstream_branch:
        upstream_branch = opts.upstream_branch
    else:
        upstream_branch = 'upstream'
    if not repo.has_branch(upstream_branch):
        msger.error('upstream branch not exists, please create one manually')

    os.chdir(repo.path)
    repo.clean_branch(upstream_branch)
    if repo.find_tag(tag):
        msger.error('don\'t need to import, already in version %s' % tag)

    msger.info('submit the upstream data')
    commit = repo.commit_dir(upstream.unpacked, msg,
                             author = {'name':COMM_NAME,
                                         'email':COMM_EMAIL
                                      }
                            )
    if commit and opts.tag:
        msger.info('create tag named: %s' % tag)
        repo.create_tag(tag, msg, commit)

    if commit is None:
        msger.info('don\'t need import, already in version %s' % tag)

    repo.checkout_branch('master')
    
    if commit and not opts.no_merge:
        try:
            msger.info('merge imported upstream branch to master branch')
            repo.merge(commit)
        except:
            msger.error('Merge failed, please resolve')

    msger.info('done.')
