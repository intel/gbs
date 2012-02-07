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
import buildservice
import runner

class _Workdir(object):
    def __init__(self, path):
        self._newdir = path
        self._cwd = os.getcwd()

    def __enter__(self):
        os.chdir(self._newdir)

    def __exit__(self, type, value, tb):
        os.chdir(self._cwd)

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

        self._bs = buildservice.BuildService(apiurl, oscrc)
        self._apiurl = self._bs.apiurl

        self._bdir = os.path.abspath(os.path.expanduser(basedir))
        self._prj = prj
        self._pkg = pkg
        self._pkgpath = os.path.join(self._bdir, prj, pkg)

        if not os.path.exists(self._bdir):
            os.makedirs(self._bdir)

        if self._bs.isNewPackage(prj, pkg):
            # to init new package in local dir
            self._mkpac()
        else:
            # to checkout server stuff
            self._checkout_latest()

    def _mkpac(self):
        with _Workdir(self._bdir):
            self._bs.mk_pac(os.path.join(self._prj, self._pkg))

    def _checkout_latest():
        """ checkout the 'latest' revision of package with link expanded
        """

        with _Workdir(self._bdir):
            self._bs.checkout(self._prj, self._pkg)

    def get_workdir(self):
        return self._pkgpath

    def remove_all(self):
        """Remove all files under pkg dir
        """

        with _Workdir(self._pkgpath):
            runner.quiet('/bin/rm -f *')

    def update_local(self):
        """Do the similar work of 'osc addremove',
          remove all deleted files and added all new files
        """
        with _Workdir(self._pkgpath):
            pac = self._bs.find_pac()
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
        with _Workdir(self._pkgpath):
            pac = self._bs.find_pac()
            if pac:
                pac.addfile(os.path.basename(fpath))
            else:
                msger.warning('Invalid pac working dir, skip')

    def commit(self, msg):
        with _Workdir(self._pkgpath):
            self._bs.submit(msg)
