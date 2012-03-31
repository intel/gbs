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

    if opts.author_name:
        COMM_NAME = opts.author_name
    if opts.author_email:
        COMM_EMAIL = opts.author_email

    specfile = None
    if len(args) < 1:
        msger.error('missing argument, please reference gbs import --help.')
    if len(args) > 1:
        msger.error('too many arguments! Please reference gbs import --help.')
    if args[0].endswith('.src.rpm'):
        srcrpmdir = tempfile.mkdtemp(prefix='%s/%s' % (tmpdir, 'src.rpm'))

        msger.info('unpack source rpm package: %s' % args[0])
        cmd = "rpm -i --define '_topdir %s' %s" % (srcrpmdir, args[0])
        if utils.linux_distribution()[0] == 'Ubuntu':
            cmd = "%s --force-debian" % cmd
        ret = runner.quiet(cmd)
        if ret != 0:
            msger.error('source rpm %s unpack failed' % args[0])
        specfile = glob.glob("%s/SPECS/*" % srcrpmdir)[0]
        for f in glob.glob("%s/SOURCES/*" % srcrpmdir):
            shutil.move(f, "%s/SPECS/" % srcrpmdir)
    elif args[0].endswith('.spec'):
        specfile = args[0]
    else:
        msger.error('gbs import only support importing specfile or source rpm')

    if not os.path.exists(tmpdir):
        os.makedirs(tmpdir)

    basedir = os.path.abspath(os.path.dirname(specfile))
    tarball = os.path.join(basedir, utils.parse_spec(specfile, 'SOURCE0'))
    if not os.path.exists(tarball):
        msger.error('tarball %s not exist, please check that' % tarball)
    pkgname = utils.parse_spec(specfile, 'name')
    pkgversion = utils.parse_spec(specfile, 'version')

    try:
        repo = git.Git('.')
    except errors.GitInvalid:
        try:
            repo = git.Git(pkgname)
        except errors.GitInvalid:
            msger.info("no git repository found, creating one.")
            repo = git.Git.create(pkgname)

    tardir = tempfile.mkdtemp(prefix='%s/%s' % (tmpdir, pkgname))

    msger.info('unpack upstream tar ball ...')
    upstream = utils.UpstreamTarball(tarball)
    try:
        upstream.unpack(tardir)
    except errors.UnpackError:
        msger.error('unpacking %s failed' % tarball)
    except errors.FormatError, e:
        msger.error(e.msg)

    tag = repo.version_to_tag("%(version)s", pkgversion)
    msg = "Upstream version %s" % (pkgversion)

    os.chdir(repo.path)

    commit = repo.commit_dir(upstream.unpacked, msg,
                             author = {'name':COMM_NAME,
                                       'email':COMM_EMAIL
                                      }
                            )
    if commit:
        msger.info('submitted the upstream data as first commit')
        if opts.tag:
            msger.info('create tag named: %s' % tag)
            repo.create_tag(tag, msg, commit)
        msger.info('create upstream branch')
        repo.create_branch('upstream', commit)
    else:
        msger.info('no changes between currentlly git repo and tar ball')

    packagingdir = '%s/packaging' % upstream.unpacked
    if not os.path.exists(packagingdir):
        os.makedirs(packagingdir)

    packagingfiles = glob.glob('%s/*' % basedir)
    for f in  packagingfiles:
        if f.endswith(os.path.basename(tarball)) or not os.path.isfile(f):
            continue
        shutil.copy(f, packagingdir)

    commit = repo.commit_dir(upstream.unpacked, 'packaging files for tizen',
                             author = {'name':COMM_NAME,
                                       'email':COMM_EMAIL
                                      }
                            )
    if commit:
        msger.info('submit packaging files as second commit')
    shutil.rmtree(tardir)
    if args[0].endswith('.src.rpm'):
        shutil.rmtree(srcrpmdir)
    msger.info('done.')
