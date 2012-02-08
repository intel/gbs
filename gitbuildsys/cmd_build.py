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

import os
import time
import tarfile
import tempfile
import glob
import shutil

import msger
import runner
import utils
from conf import configmgr
import git
import obspkg

OSCRC_TEMPLATE = """[general]
apiurl = %(apiurl)s
plaintext_passwd=0
[%(apiurl)s]
user=%(user)s
passx=%(passwdx)s
"""

SRCSERVER   = configmgr.get('build_server', 'build')
USER        = configmgr.get('user', 'build')
PASSWDX     = configmgr.get('passwdx', 'build')
TMPDIR      = configmgr.get('tmpdir')

def do(opts, args):

    if not os.path.isdir('.git'):
        msger.error('You must run this command under a git tree')

    GIT = git.Git('.')
    if GIT.get_branches()[0] != 'master':
        msger.error('You must run this command under the master branch')

    tmpdir = '%s/%s' % (TMPDIR, USER)
    if not os.path.exists(tmpdir):
        os.makedirs(tmpdir)

    oscrc = OSCRC_TEMPLATE % {"apiurl": SRCSERVER, "user": USER, "passwdx": PASSWDX}
    (fd, oscrcpath) = tempfile.mkstemp(dir=tmpdir,prefix='.oscrc')
    os.close(fd)
    f = file(oscrcpath, 'w+')
    f.write(oscrc)
    f.close()
    
    specs = glob.glob('./packaging/*.spec')
    if not specs:
        msger.error('no spec file found, please add spec file to packaging directory')

    specfile = specs[0] #TODO:
    if len(specs) > 1:
        msger.warning('multiple specfiles found.')

    # get 'name' and 'version' from spec file
    name = utils.parse_spec(specfile, 'name')
    version = utils.parse_spec(specfile, 'version')

    if opts.base_obsprj is None:
        # TODO, get current branch of git to determine it
        base_prj = 'Trunk'
    else:
        base_prj = opts.base_obsprj

    if opts.target_obsprj is None:
        target_prj = "home:%s:gbs:%s" % (USER, base_prj)
    else:
        target_prj = opts.target_obsprj

    prj = obspkg.ObsProject(target_prj, apiurl = SRCSERVER, oscrc = oscrcpath)
    msger.info('checking status of obs project: %s ...' % target_prj)
    if prj.is_new():
        msger.info('creating %s for package build ...' % target_prj)
        prj.branch_from(base_prj)

    msger.info('checking out %s/%s to %s ...' % (target_prj, name, tmpdir))
    localpkg = obspkg.ObsPackage(tmpdir, target_prj, name, SRCSERVER, oscrcpath)
    workdir = localpkg.get_workdir()
    localpkg.remove_all()

    srcdir = "%s-%s" % (name, version)
    os.mkdir(srcdir)

    tarball = '%s-%s.tizen.tar.bz2' % (name, version)
    msger.info('archive git tree to tar ball: %s' % tarball)
    tarfp = '%s/%s' % (workdir, tarball)
    tar = tarfile.open(tarfp, 'w:bz2')
    for f in GIT.get_files():
        if f.startswith('packaging'):
            continue
        dirname = "%s/%s" % (srcdir, os.path.dirname(f))
        if not os.path.exists(dirname):
            os.makedirs(dirname)
        shutil.copy(f, dirname)
        tar.add("%s/%s" % (srcdir, f))
    tar.close()
    shutil.rmtree(srcdir, ignore_errors = True)

    for f in glob.glob('packaging/*'):
        shutil.copy(f, workdir)

    localpkg.update_local()

    msger.info('commit packaging files to build server ...')
    localpkg.commit ('submit packaging files to obs for OBS building')

    os.unlink(oscrcpath)
    msger.info('local changes submitted to build server successfully')
    msger.info('follow the link to monitor the build progress: ')
    msger.info('%s/project/show?project=%s' % (SRCSERVER.replace('api', 'build'), target_prj))
