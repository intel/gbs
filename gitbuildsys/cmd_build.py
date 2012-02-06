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
from conf import configmgr
import git
import buildservice

OSCRC_TEMPLATE = """[general]
apiurl = %(api)s
[%(apiurl)s]
user=%(user)s
passx=%(passwdx)s
"""

#SRCSERVER = configmgr.get('src_server')
#USER = configmgr.get('user')
#PASSWDX = configmgr.get('passwdx')

SRCSERVER = 'https://api.saobs.jf.intel.com'
USER = 'xiaoqiang'
PASSWDX = 'QlpoOTFBWSZTWVyCeo8AAAKIAHJAIAAhhoGaAlNOLuSKcKEguQT1Hg=='

def do(opts, args):

    if not os.path.isdir('.git'):
        msger.error('You must run this command under a git tree')

    GIT = git.Git('.')
    if GIT.get_branches()[0] != 'master':
        msger.error('You must run this command under the master branch')

    # get temp dir from opts
    #tmpdir = opts.tmpdir

    tmpdir = '/var/tmp/%s' % USER
    if not os.path.exists(tmpdir):
        os.makedirs(tmpdir)

    oscrc = OSCRC_TEMPLATE % {"api": SRCSERVER, "apiurl": SRCSERVER, "user": USER, "passwdx": PASSWDX}
    (fd, oscrcpath) = tempfile.mkstemp(dir=tmpdir,prefix='.oscrc')
    os.close(fd)
    f = file(oscrcpath, 'w+')
    f.write(oscrc)
    f.close()
    
    specs = glob.glob('./packaging/*.spec')
    if not specs:
        msger.error('No spec file found, please add spec file to packaging directory')

    specfile = specs[0]
    ret, out = runner.runtool(['grep', '^Name', specfile])
    name = out.split()[-1]
    ret, out = runner.runtool(['grep', '^Version', specfile])
    version = out.split()[-1]

    bs = buildservice.BuildService(apiurl = SRCSERVER, oscrc = oscrcpath)

    #obspkg = ObsPackage(tmpdir, SRCSERVER, "home:%s:branches:gbs:Trunk" % USER, name, oscrcpath)
    #workdir = obspkg.get_workdir()
    workdir = os.getcwd()
    #obspkg.remove_all()

    srcdir = "%s-%s" % (name, version)
    os.mkdir(srcdir)
    tarfp = '%s/%s-%s.tizen.tar.bz2' % (workdir, name, version)
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

    #obspkg.add_all()
    #obspkg.commit ()
    os.unlink(oscrcpath)
