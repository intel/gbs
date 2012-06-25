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
import tempfile
import glob

import msger
from conf import configmgr
import obspkg
import errors
import utils

import gbp.rpm
from gbp.scripts.buildpackage_rpm import main as gbp_build
from gbp.git import repository, GitRepositoryError
from gbp.errors import GbpError

OSCRC_TEMPLATE = """[general]
apiurl = %(apiurl)s
plaintext_passwd=0
use_keyring=0
http_debug = %(http_debug)s
debug = %(debug)s
gnome_keyring=0
[%(apiurl)s]
user=%(user)s
passx=%(passwdx)s
"""

APISERVER   = configmgr.get('build_server', 'remotebuild')
USER        = configmgr.get('user', 'remotebuild')
PASSWDX     = configmgr.get('passwdx', 'remotebuild')
TMPDIR      = configmgr.get('tmpdir')

def do(opts, args):

    workdir = os.getcwd()
    if len(args) > 1:
        msger.error('only one work directory can be specified in args.')
    if len(args) == 1:
        workdir = os.path.abspath(args[0])
    try:
        repo = repository.GitRepository(workdir)
    except repository.GitRepositoryError:
        msger.error('%s is not a git dir' % workdir)

    workdir = repo.path

    tmpdir = '%s/%s' % (TMPDIR, USER)
    if not os.path.exists(tmpdir):
        os.makedirs(tmpdir)

    if not os.access(tmpdir, os.W_OK|os.R_OK|os.X_OK):
        msger.error('No access permission to %s, please check' % tmpdir)

    oscrc = OSCRC_TEMPLATE % {
                "http_debug": 1 if msger.get_loglevel() == 'debug' else 0,
                "debug": 1 if msger.get_loglevel() == 'verbose' else 0,
                "apiurl": APISERVER,
                "user": USER,
                "passwdx": PASSWDX,
            }
    (fds, oscrcpath) = tempfile.mkstemp(dir=tmpdir, prefix='.oscrc')
    os.close(fds)
    with file(oscrcpath, 'w+') as foscrc:
        foscrc.write(oscrc)

    # TODO: check ./packaging dir at first
    specs = glob.glob('%s/packaging/*.spec' % workdir)
    if not specs:
        msger.error('no spec file found under /packaging sub-directory')

    specfile = utils.guess_spec(workdir, opts.spec)
    # get 'name' and 'version' from spec file
    try:
        spec = gbp.rpm.parse_spec(specfile)
    except GbpError, err:
        msger.error('%s' % err)

    if not spec.name or not spec.version:
        msger.error('can\'t get correct name or version from spec file.')

    if opts.base_obsprj is None:
        # TODO, get current branch of git to determine it
        base_prj = 'Tizen:Main'
    else:
        base_prj = opts.base_obsprj

    if opts.target_obsprj is None:
        target_prj = "home:%s:gbs:%s" % (USER, base_prj)
    else:
        target_prj = opts.target_obsprj

    prj = obspkg.ObsProject(target_prj, apiurl = APISERVER, oscrc = oscrcpath)
    msger.info('checking status of obs project: %s ...' % target_prj)
    if prj.is_new():
        if opts.target_obsprj and not target_prj.startswith('home:%s:' % USER):
            msger.error('no permission to create project %s, only subpackage '\
                    'of home:%s is allowed ' % (target_prj, USER))
        msger.info('creating %s for package build ...' % target_prj)
        prj.branch_from(base_prj)

    msger.info('checking out %s/%s to %s ...' % (target_prj, spec.name, tmpdir))

    target_prj_path = os.path.join(tmpdir, target_prj)
    if os.path.exists(target_prj_path) and \
       not os.access(target_prj_path, os.W_OK|os.R_OK|os.X_OK):
        msger.error('No access permission to %s, please check' % target_prj_path)

    localpkg = obspkg.ObsPackage(tmpdir, target_prj, spec.name,
                                 APISERVER, oscrcpath)
    oscworkdir = localpkg.get_workdir()
    localpkg.remove_all()

    with utils.Workdir(workdir):
        commit = opts.commit or 'HEAD'
        relative_spec = specfile.replace('%s/' % workdir, '')
        try:
            if gbp_build(["argv[0] placeholder", "--git-export-only",
                          "--git-ignore-new", "--git-builder=osc",
                          "--git-export-dir=%s" % oscworkdir,
                          "--git-packaging-dir=packaging",
                          "--git-specfile=%s" % relative_spec,
                          "--git-export=%s" % commit]):
                msger.error("Failed to get packaging info from git tree")
        except GitRepositoryError, excobj:
            msger.error("Repository error: %s" % excobj)

    localpkg.update_local()

    try:
        msger.info('commit packaging files to build server ...')
        localpkg.commit ('submit packaging files to obs for OBS building')
    except errors.ObsError, e:
        msger.error('commit packages fail: %s, please check the permission '\
                    'of target project:%s' % (e,target_prj))

    os.unlink(oscrcpath)
    msger.info('local changes submitted to build server successfully')
    msger.info('follow the link to monitor the build progress:\n'
               '  %s/package/show?package=%s&project=%s' \
               % (APISERVER.replace('api', 'build'), spec.name, target_prj))
