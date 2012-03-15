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
import glob

import msger
import runner

compressor_opts = { 'gzip'  : [ '-n', 'gz' ],
                    'bzip2' : [ '', 'bz2' ],
                    'lzma'  : [ '', 'lzma' ],
                    'xz'    : [ '', 'xz' ] }

# Map frequently used names of compression types to the internal ones:
compressor_aliases = { 'bz2' : 'bzip2',
                       'gz'  : 'gzip', }

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

def get_processors():
    """
    get number of processors (online) based on
    SC_NPROCESSORS_ONLN (returns 1 if config name does not exist).
    """
    try:
        return os.sysconf('SC_NPROCESSORS_ONLN')
    except ValueError:
        return 1

def get_hostarch():
    hostarch = os.uname()[4]
    if hostarch == 'i686':
        hostarch = 'i586'
    return hostarch

class UnpackTarArchive(object):
    """Wrap tar to unpack a compressed tar archive"""
    def __init__(self, archive, dir, filters=[], compression=None):
        self.archive = archive
        self.dir = dir
        exclude = [("--exclude=%s" % filter) for filter in filters]

        if not compression:
            compression = '-a'

        cmd = ' '.join(['tar']+ exclude + ['-C', dir, compression, '-xf', archive ])
        runner.quiet(cmd)

class UnpackZipArchive(object):
    """Wrap zip to Unpack a zip file"""
    def __init__(self, archive, dir):
        self.archive = archive
        self.dir = dir

        cmd = ' '.join(['unzip'] + [ "-q", archive, '-d', dir ])
        msger.info(cmd)
        runner.quiet(cmd)

class UpstreamTarball(object):
    def __init__(self, name, unpacked=None):
        self._orig = False
        self._path = name
        self.unpacked = unpacked

    @property
    def path(self):
        return self._path.rstrip('/')

    def unpack(self, dir, filters=[]):
        """
        Unpack packed upstream sources into a given directory
        and determine the toplevel of the source tree.
        """
        if not filters:
            filters = []

        if type(filters) != type([]):
            raise GbpError, "Filters must be a list"

        self._unpack_archive(dir, filters)
        self.unpacked = self._unpacked_toplevel(dir)

    def _unpack_archive(self, dir, filters):
        """
        Unpack packed upstream sources into a given directory.
        """
        ext = os.path.splitext(self.path)[1]
        if ext in [ ".zip", ".xpi" ]:
            self._unpack_zip(dir)
        else:
            self._unpack_tar(dir, filters)

    def _unpack_zip(self, dir):
        try:
            UnpackZipArchive(self.path, dir)
        except CmdError:
            raise CmdError, "Unpacking of %s failed" % self.path

    def _unpacked_toplevel(self, dir):
        """unpacked archives can contain a leading directory or not"""
        unpacked = glob.glob('%s/*' % dir)
        unpacked.extend(glob.glob("%s/.*" % dir))

        # Check that dir contains nothing but a single folder:
        if len(unpacked) == 1 and os.path.isdir(unpacked[0]):
            return unpacked[0]
        else:
            return dir

    def _unpack_tar(self, dir, filters):
        """
        Unpack a tarball to dir applying a list of filters.
        """
        try:
            unpackArchive = UnpackTarArchive(self.path, dir, filters)
        except gbpc.CommandExecFailed:
            raise GbpError
