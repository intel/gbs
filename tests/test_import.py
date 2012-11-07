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

"""Functionality tests of gbs import."""

import os
import shutil
import unittest
import tempfile
import imp

from functools import wraps

from nose.tools import eq_, raises

from gbp.git.repository import GitRepository

GBS = imp.load_source("gbs", "./tools/gbs").main

def with_data(fname):
    """
    Parametrized decorator for testcase methods.
    Gets name of the directory or file in tests/testdata/
    Copies it to the temporary working directory and
    runs testcase method there.
    Adds fname as a parameter for the testcase method

    """
    def decorator(func):
        """Decorator itself."""
        @wraps(func)
        def wrapper(*args, **kwargs):
            """Main functionality is here."""
            obj = args[0] # TestCase object
            # Copy required data(fname) to object temporary directory
            fpath = os.path.join(obj.cdir, "./tests/testdata", fname)
            if os.path.isdir(fpath):
                shutil.copytree(fpath, os.path.join(obj.tmp, fname))
            else:
                shutil.copy(fpath, obj.tmp)
            # Append fname to testcase method parameters
            args = list(args)
            args.append(fpath)
            args = tuple(args)
            return func(*args, **kwargs)
        return wrapper
    return decorator

class TestImport(unittest.TestCase):
    """Test help output of gbs commands"""

    def __init__(self, method):
        super(TestImport, self).__init__(method)

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="test-gbs-import-")
        shutil.copy('.gbs.conf', self.tmp)
        self.cdir = os.getcwd()
        os.chdir(self.tmp)

    def tearDown(self):
        os.chdir(self.cdir)
        shutil.rmtree(self.tmp)

    @with_data("ail-0.2.29-2.3.src.rpm")
    def test_import_srcrpm(self, srcrpm):
        """Test importing from source rpm."""
        eq_(GBS(argv=["gbs", "import", srcrpm]), None)
        repo = GitRepository("./ail")
        eq_(repo.get_local_branches(), ['master', 'pristine-tar', 'upstream'])
        eq_(repo.get_tags(), ['upstream/0.2.29', 'vendor/0.2.29-2.3'])

    @with_data("bluez_unpacked")
    def test_import_spec(self, srcdir):
        """Test importing from spec."""
        eq_(GBS(argv=["gbs", "import",
                      os.path.join(srcdir, 'bluez.spec')]), None)
        repo = GitRepository("./bluez")
        eq_(repo.get_local_branches(), ['master', 'pristine-tar', 'upstream'])
        # No packging tag as patch-import fails
        eq_(repo.get_tags(), ['upstream/4.87'])
        eq_(len(repo.get_commits(until='master')), 2)

        #raise Exception(os.listdir('./bluez'))

    @with_data("ail-0.2.29-2.5.src.rpm")
    def test_running_from_git_tree(self, srcrpm):
        """Test running gbs import from git tree."""
        # Create empty git repo
        repo = GitRepository.create("./repo_dir")
        os.chdir(repo.path)
        eq_(GBS(argv=["gbs", "import", srcrpm]), None)
        eq_(repo.get_local_branches(), ['master', 'pristine-tar', 'upstream'])
        eq_(repo.get_tags(), ['upstream/0.2.29', 'vendor/0.2.29-2.5'])

        #raise Exception(os.listdir('./bluez'))

    @with_data("app-core-1.2-19.3.src.rpm")
    def test_set_author_name_email(self, srcrpm):
        """Test --author-name and --author-email command line options."""
        eq_(GBS(argv=["gbs", "import", "--author-name=test",
                      "--author-email=test@otctools.jf.intel.com",
                      srcrpm]), None)
        repo = GitRepository("./app-core")
        eq_(repo.get_local_branches(), ['master', 'pristine-tar', 'upstream'])
        eq_(repo.get_tags(), ['upstream/1.2', 'vendor/1.2-19.3'])

    @with_data("ail-0.2.29-2.3.src.rpm")
    def test_specify_upstream(self, srcrpm):
        """Test --upstream command line option."""
        eq_(GBS(argv=["gbs", "import", "--upstream=upstream",
                      srcrpm]), None)
        repo = GitRepository("./ail")
        eq_(repo.get_local_branches(), ['master', 'pristine-tar', 'upstream'])
        eq_(repo.get_tags(), ['upstream/0.2.29', 'vendor/0.2.29-2.3'])

    @raises(SystemExit)
    @with_data("bison-1.27.tar.gz")
    def test_is_not_git_repository(self, tarball):
        """Test raising exception when importing tarball outside of git."""
        GBS(argv=["gbs", "import", tarball])

    @raises(SystemExit)
    @with_data("bad.src.rpm")
    def test_error_reading_pkg_header(self, srcrpm):
        """Test raising exception when importing from bad package."""
        GBS(argv=["gbs", "import", srcrpm])

    @raises(SystemExit)
    @with_data("bad.spec")
    def test_cant_parse_specfile(self, spec):
        """Test raising exception when importing from non-parseable spec."""
        GBS(argv=["gbs", "import", spec])

    @raises(SystemExit)
    def test_missing_argument(self):
        """Test raising exception when running gbs without any arguments."""
        GBS(argv=["gbs", "import"])

    @raises(SystemExit)
    def test_too_many_arguments(self):
        """Test raising exception when running gbs with too many arguments."""
        GBS(argv=["gbs", "import", "1", "2"])

    @raises(SystemExit)
    def test_path_doesnt_exist(self):
        """Test raising exception when running gbs with not existing path."""
        GBS(argv=["gbs", "import", "I don't exist!"])
