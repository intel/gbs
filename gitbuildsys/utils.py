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
import runner
import errors


class Workdir(object):
    def __init__(self, path):
        self._newdir = path
        self._cwd = os.getcwd()

    def __enter__(self):
        os.chdir(self._newdir)

    def __exit__(self, _type, _value, _tb):
        os.chdir(self._cwd)

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

def find_binary_path(binary):
    if os.environ.has_key("PATH"):
        paths = os.environ["PATH"].split(":")
    else:
        paths = []
        if os.environ.has_key("HOME"):
            paths += [os.environ["HOME"] + "/bin"]
        paths += ["/usr/local/sbin", "/usr/local/bin", "/usr/sbin",
                  "/usr/bin", "/sbin", "/bin"]

    for path in paths:
        bin_path = "%s/%s" % (path, binary)
        if os.path.exists(bin_path):
            return bin_path
    return None

def is_statically_linked(binary):
    return ", statically linked, " in runner.outs(['file', binary])

def setup_qemu_emulator():
    # mount binfmt_misc if it doesn't exist
    if not os.path.exists("/proc/sys/fs/binfmt_misc"):
        modprobecmd = find_binary_path("modprobe")
        runner.show([modprobecmd, "binfmt_misc"])
    if not os.path.exists("/proc/sys/fs/binfmt_misc/register"):
        mountcmd = find_binary_path("mount")
        runner.show([mountcmd, "-t", "binfmt_misc", "none",
                     "/proc/sys/fs/binfmt_misc"])

    # qemu_emulator is a special case, we can't use find_binary_path
    # qemu emulator should be a statically-linked executable file
    qemu_emulator = "/usr/bin/qemu-arm"
    if not os.path.exists(qemu_emulator) or \
           not is_statically_linked(qemu_emulator):
        qemu_emulator = "/usr/bin/qemu-arm-static"
    if not os.path.exists(qemu_emulator):
        raise errors.QemuError("Please install a statically-linked qemu-arm")

    # disable selinux, selinux will block qemu emulator to run
    if os.path.exists("/usr/sbin/setenforce"):
        msger.info('Try to disable selinux')
        runner.show(["/usr/sbin/setenforce", "0"])

    node = "/proc/sys/fs/binfmt_misc/arm"
    if is_statically_linked(qemu_emulator) and os.path.exists(node):
        return qemu_emulator

    # unregister it if it has been registered and
    # is a dynamically-linked executable
    if not is_statically_linked(qemu_emulator) and os.path.exists(node):
        qemu_unregister_string = "-1\n"
        fds = open("/proc/sys/fs/binfmt_misc/arm", "w")
        fds.write(qemu_unregister_string)
        fds.close()

    # register qemu emulator for interpreting other arch executable file
    if not os.path.exists(node):
        qemu_arm_string = ":arm:M::\\x7fELF\\x01\\x01\\x01\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x02\\x00\\x28\\x00:\\xff\\xff\\xff\\xff\\xff\\xff\\xff\\x00\\xff\\xff\\xff\\xff\\xff\\xff\\xff\\xff\\xfa\\xff\\xff\\xff:%s:\n" % qemu_emulator
        fds = open("/proc/sys/fs/binfmt_misc/register", "w")
        fds.write(qemu_arm_string)
        fds.close()

    return qemu_emulator

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
