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

import os
import glob
import tempfile
import shutil

import msger

class Workdir(object):
    def __init__(self, path):
        self._newdir = path
        self._cwd = os.getcwd()

    def __enter__(self):
        os.chdir(self._newdir)

    def __exit__(self, _type, _value, _tb):
        os.chdir(self._cwd)

def guess_spec(workdir, default_spec):
    if default_spec:
        if not os.path.exists(default_spec):
            msger.error('%s does not exit' % default_spec)
        return default_spec
    git_project =  os.path.basename(workdir)
    specfile = '%s/packaging/%s.spec' % (workdir, git_project)
    if not os.path.exists(specfile):
        specs = glob.glob('%s/packaging/*.spec' % workdir)
        if not specs:
            msger.error('no spec file found under %s/packaging' % workdir)

        if len(specs) > 1:
            msger.error("Can't decide which spec file to use.")
        else:
            specfile = specs[0]
    return specfile

class TempCopy(object):
    """Copy original file to temporary file in the same directory as
       original. Creates empty termporary file if original doesn't exist.
       Deletes termporary file when object is destroyed.
    """

    def __init__(self, orig_fpath):
        self.orig_fpath = orig_fpath

        # create temp file
        tmpffd, self.name = tempfile.mkstemp(dir=os.path.dirname(orig_fpath))
        os.close(tmpffd)

        # copy original file to temp
        if os.path.exists(orig_fpath):
            shutil.copy2(orig_fpath, self.name)

        self.stat = os.stat(self.name)

    def update_stat(self):
        """Updates stat info."""
        self.stat = os.stat(self.name)

    def is_changed(self):
        """Check if temporary file has been changed."""
        return os.stat(self.name) != self.stat

    def __del__(self):
        if os.path.exists(self.name):
            os.unlink(self.name)
