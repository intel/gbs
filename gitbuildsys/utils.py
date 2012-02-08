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

from __future__ import with_statement
import os

import msger
import runner

class Workdir(object):
    def __init__(self, path):
        self._newdir = path
        self._cwd = os.getcwd()

    def __enter__(self):
        os.chdir(self._newdir)

    def __exit__(self, type, value, tb):
        os.chdir(self._cwd)

def which(cmd):
    def is_exe(fpath):
        return os.path.exists(fpath) and os.access(fpath, os.X_OK)

    fpath, fname = os.path.split(cmd)
    if fpath:
        if is_exe(cmd):
            return cmd
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            exe_file = os.path.join(path, cmd)
            if is_exe(exe_file):
                return exe_file

    return None

def lookfor_cmds(cmds):
    for cmd in cmds:
        if not which(cmd):
            msger.error('Could not find required executable: %s' % cmd)

def strip_end(text, suffix):
    if not text.endswith(suffix):
        return text
    return text[:-len(suffix)]

def get_share_dir():
    # TODO need to be better
    return '/usr/share/gbs/'

def parse_spec(spec_path, macro):
    """Parse the spec file to get the specified `macro`
    """

    rpmb_cmd = 'rpmbuild'

    if which(rpmb_cmd):
        # rpmbuild has been installed in system, use it
        rpmb_cmdline = ("%s -bp --nodeps --force "
                        "tmp.spec --define '_topdir .' "
                        "--define '_builddir .' "
                        "--define '_sourcedir .' "
                        "--define '_rpmdir .' "
                        "--define '_specdir .' "
                        "--define '_srcrpmdir .'") % rpmb_cmd

        wf = open('tmp.spec', 'w')
        with file(spec_path) as f:
            for line in f:
                if line.startswith('%prep'):
                    line ='%%prep\necho %%{%s}\nexit\n' % macro
                wf.write(line)
        wf.close()

        outs = runner.outs(rpmb_cmdline, catch=3)

        # clean up
        os.unlink('tmp.spec')
        if os.path.isdir('BUILDROOT'):
            import shutil
            shutil.rmtree('BUILDROOT', ignore_errors=True)

        for line in outs.splitlines():
            if line.startswith('+ echo '):
                return line[7:].rstrip()

        msger.warning('invalid spec file, cannot get the value of macro %s' \
                      % macro)
        return ''

    else:
        # TBD parse it directly
        msger.warning('cannot support parsing spec without rpmbuild command')
        return ''
