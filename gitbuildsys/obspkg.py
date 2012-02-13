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

from __future__ import with_statement
import os
import shutil
import buildservice
import runner
import msger
import errors
from utils import Workdir

class ObsPackage(object):
    """ Wrapper class of local package dir of OBS
    """

    def __init__(self, basedir, prj, pkg, apiurl=None, oscrc=None):
        """Arguments:
          basedir: the base local dir to store obs packages
          prj: obs project
          pkg: obs package
          apiurl: optional, the api url of obs service
                 if not specified, the one from oscrc will be used
          oscrc: optional, the path of customized oscrc
                 if not specified, ~/.oscrc will be used
        """

        if oscrc:
            self._oscrc = oscrc
        else:
            self._oscrc = os.path.expanduser('~/.oscrc')

        self._bs = msger.PrintBufWrapper(buildservice.BuildService, #class
                                         msger.verbose, # func_for_stdout
                                         msger.warning, # func_for_stderr
                                         apiurl, oscrc) # original args

        self._apiurl = self._bs.apiurl

        self._bdir = os.path.abspath(os.path.expanduser(basedir))
        self._prj = prj
        self._pkg = pkg
        self._pkgpath = os.path.join(self._bdir, prj, pkg)

        if not os.path.exists(self._bdir):
            os.makedirs(self._bdir)

        with Workdir(self._bdir):
            shutil.rmtree(prj, ignore_errors = True)

        if self._bs.isNewPackage(prj, pkg):
            # to init new package in local dir
            self._mkpac()
        else:
            # to checkout server stuff
            self._checkout_latest()

    def _mkpac(self):
        with Workdir(self._bdir):
            self._bs.mkPac(self._prj, self._pkg)

    @msger.waiting
    def _checkout_latest(self):
        """ checkout the 'latest' revision of package with link expanded
        """

        with Workdir(self._bdir):
            self._bs.checkout(self._prj, self._pkg)

    def get_workdir(self):
        return self._pkgpath

    def remove_all(self):
        """Remove all files under pkg dir
        """

        with Workdir(self._pkgpath):
            runner.quiet('/bin/rm -f *')

    def update_local(self):
        """Do the similar work of 'osc addremove',
          remove all deleted files and added all new files
        """

        with Workdir(self._pkgpath):
            pac = self._bs.findPac()
            # FIXME, if pac.to_be_added are needed to be considered.
            pac.todo = list(set(pac.filenamelist + pac.filenamelist_unvers))
            for filename in pac.todo:
                if os.path.isdir(filename):
                    continue
                # ignore foo.rXX, foo.mine for files which are in 'C' state
                if os.path.splitext(filename)[0] in pac.in_conflict:
                    continue
                state = pac.status(filename)
                if state == '?':
                    pac.addfile(filename)
                elif state == '!':
                    pac.delete_file(filename)

    def add_file(self, fpath):
        # copy the file in
        runner.quiet('/bin/cp -f %s %s' % (fpath, self._pkgpath))

        # add it into local pac
        with Workdir(self._pkgpath):
            pac = self._bs.findPac()
            if pac:
                pac.addfile(os.path.basename(fpath))
            else:
                msger.warning('Invalid pac working dir, skip')

    @msger.waiting
    def commit(self, msg):
        with Workdir(self._pkgpath):
            self._bs.submit(msg)

class ObsProject(object):
    """ Wrapper class of project in OBS
    """

    def __init__(self, prj, apiurl=None, oscrc=None):
        """Arguments:
          prj: name of obs project
          apiurl: optional, the api url of obs service
                 if not specified, the one from oscrc will be used
          oscrc: optional, the path of customized oscrc
                 if not specified, ~/.oscrc will be used
        """

        if oscrc:
            self._oscrc = oscrc
        else:
            self._oscrc = os.path.expanduser('~/.oscrc')

        self._bs = buildservice.BuildService(apiurl, oscrc)
        self._apiurl = self._bs.apiurl
        self._prj = prj

    @msger.waiting
    def is_new(self):
        return self._bs.isNewProject(self._prj)

    def create(self):
        """Create an empty project"""
        # TODO
        pass

    def branch_from(self, src_prj):
        """Create a new branch project of `src_prj`
        """

        if self._bs.isNewProject(src_prj):
            raise errors.ObsError('project: %s do not exists' % src_prj)

        if not self.is_new():
            msger.warning('branched project: %s exists' % self._prj)
            return

        # pick the 1st valid package inside src prj FIXME
        dumb_pkg = self._bs.getPackageList(src_prj)[0]

        # branch out the new one
        target_prj, target_pkg = self._bs.branchPkg(src_prj, dumb_pkg,
                                                    target_project = self._prj,
                                                    target_package = 'dumb_pkg')

        if target_prj != self._prj:
            raise ObsError('branched prj: %s is not the expected %s' \
                           % (target_prj, self._prj))

        # remove the dumb pkg
        self._bs.deletePackage(target_prj, target_pkg)
