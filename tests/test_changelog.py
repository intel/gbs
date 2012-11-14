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

"""Functionality tests for gbs changelog."""

import os
import shutil
import unittest
import tempfile
import imp
import datetime
import time

from nose.tools import eq_, raises

from gbp.git.repository import GitRepository

from gitbuildsys.errors import GbsError

GBS = imp.load_source("gbs", "./tools/gbs").main
ENV = {}

def set_editor(editor):
    '''set editor'''
    os.environ['EDITOR'] = editor

def setup_module():
    """One setup for all tests."""

    ENV["cwd"] = os.getcwd()
    tmp = tempfile.mkdtemp(prefix="test-gbs-changelog-")
    shutil.copy('.gbs.conf', tmp)
    os.chdir(tmp)
    ENV["dir"] = tmp

    # Create git repo
    repo = GitRepository.create('.')
    author = repo.get_author_info()
    ENV["repo"] = repo
    ENV["name"] = author.name
    ENV["email"] = author.email

    # Make 3 commits
    for num in (1, 2, 3):
        with open("file", "w") as fobj:
            fobj.write("content %d" % num)
        time.sleep(1) # Sleep to make commit timestamps differ
        repo.add_files(repo.path, untracked=True)
        repo.commit_files(files="file", msg="change %d" % num)

    ENV["date"] = datetime.datetime.now().strftime("%a %b %d %Y")
    commits = sorted(repo.get_commits(options=['--pretty=format:%at %H']),
                     reverse=True)

    ENV["commits"] = [item.split()[-1] for item in commits]

def teardown_module():
    """Cleanup test directory."""
    shutil.rmtree(ENV["dir"])
    os.chdir(ENV["cwd"])


class TestChangelog(unittest.TestCase):
    """Test help output of gbs commands"""

    def __init__(self, method):
        super(TestChangelog, self).__init__(method)
        self.changes = 'packaging/test.changes'
        self.spec = 'packaging/test.spec'

    def setUp(self):
        os.chdir(ENV["dir"])

        # [Re]create packaging/test.spec
        shutil.rmtree('packaging', ignore_errors=True)
        os.mkdir('packaging')
        open("packaging/test.spec", "w").close()

        set_editor("sleep 1 && touch")

    def test_new_changes(self):
        """Test generating new .changes."""
        eq_(GBS(argv=["gbs", "changelog"]), None)
        eq_(open(self.changes).read(),
            "* %s %s <%s> %s\n- change 3\n- change 2\n- change 1\n\n" % \
            (ENV["date"], ENV["name"], ENV["email"], ENV["commits"][0][:7]))

    def test_new_changes_with_content(self):
        """Test generating new .changes with specific content."""
        eq_(GBS(argv=["gbs", "changelog", "-m", "new .changes"]), None)
        eq_(open(self.changes).read(),
            "* %s %s <%s> %s\n- new .changes\n\n" % \
            (ENV["date"], ENV["name"], ENV["email"], ENV["commits"][0][:7]))

    def test_update_changes(self):
        """Test updating existing .changes."""
        # create test.changes
        init = "* %s name <email@some.domain> %s\n- init\n\n" % \
               (ENV["date"], ENV["commits"][-1][:7])
        with open(self.changes, "w") as changes:
            changes.write(init)

        eq_(GBS(argv=["gbs", "changelog"]), None)
        expected = "* %s %s <%s> %s\n- change 3\n- change 2\n\n" % \
                   (ENV["date"], ENV["name"], ENV["email"],
                    ENV["commits"][0][:7])
        eq_(open(self.changes).read(), expected+init)

    def test_since(self):
        """Test --since command line option."""
        eq_(GBS(argv=["gbs", "changelog", "--since", ENV["commits"][1]]), None)
        eq_(open(self.changes).read(),
            "* %s %s <%s> %s\n- change 3\n\n" % \
            (ENV["date"], ENV["name"], ENV["email"], ENV["commits"][0][:7]))

    @staticmethod
    def test_not_updated():
        """Test normal exit when changelog is not updated."""
        set_editor("true")
        eq_(GBS(argv=["gbs ", "changelog"]), None)

    @staticmethod
    @raises(GbsError)
    def test_no_new_changes():
        """Test failure when no new changes can be generated."""
        eq_(GBS(argv=["gbs", "changelog"]), None)
        GBS(argv=["gbs", "changelog"])

    @staticmethod
    @raises(GbsError)
    def test_wrong_since():
        """Test failure with wrong --since value."""
        GBS(argv=["gbs", "changelog", "--since", "bla"])

    @raises(GbsError)
    def test_non_existent_commit(self):
        """Test failure with wrong commit id in the changelog."""
        with open(self.changes, "w") as changes:
            changes.write("* Wed Aug 22 2012 test <test@otctools.jf.intel.com> "
                          "xxxxxx\n- change 3\n\n")
        GBS(argv=["gbs", "changelog"])

    @staticmethod
    @raises(GbsError)
    def test_not_in_git_repository():
        """Test failure when run not in git repo."""
        os.chdir('..')
        GBS(argv=["gbs", "changelog"])

    @raises(GbsError)
    def test_no_spec(self):
        """Test failure when there is not spec in packaging dir."""
        os.unlink(self.spec)
        GBS(argv=["gbs", "changelog"])
