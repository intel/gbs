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

"""Functionality tests for gbs help."""

import unittest
import imp

from nose.tools import eq_

GBS = imp.load_source("gbs", "./tools/gbs").main

class TestHelp(unittest.TestCase):
    """Test help output of gbs commands"""

    @staticmethod
    def test_subcommand_help():
        """Test running gbs help with all possible subcommands."""
        for sub in [ "build", "lb", "remotebuild", "rb", "changelog", "ch",
                     "submit", "sr", "export", "ex", "import", "im",
                     "chroot", "chr"]:

            try:
                print '>>>sub', sub
                GBS(argv=["gbs", sub, "--help"])
            except SystemExit, err:
                eq_(err.code, 0)

    @staticmethod
    def test_help():
        """Test running gbs --help and gbs help."""
        try:
            GBS(argv=["gbs", "--help"])
        except SystemExit, err:
            eq_(err.code, 0)
