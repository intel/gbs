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

"""Unit tests for class BuildData"""

import os
import unittest
from collections import OrderedDict

from gitbuildsys.builddata import BuildData, BuildDataError


TEST_XML = """<?xml version="1.0"?>
<build version="1.0">
  <archs>
    <arch>i586</arch>
    <arch>armv7l</arch>
  </archs>
  <repos>
    <repo>exynos</repo>
    <repo>atom</repo>
  </repos>
  <buildtargets>
    <buildtarget name="atom">
      <buildconf>
        <location href="3bd64bd5fa862d99dbc363ccb1557d137b5685bc3bfe9a86bcbf50767da5e2e8-build.conf"/>
        <checksum type="sh256">3bd64bd5fa862d99dbc363ccb1557d137b5685bc3bfe9a86bcbf50767da5e2e8</checksum>
      </buildconf>
      <arch default="yes" name="i586">
        <repo type="binary">repos/atom/i586/packages</repo>
        <repo type="debug">repos/atom/i586/debug</repo>
        <repo type="source">repos/atom/i586/sources</repo>
      </arch>
      <arch name="x86_64">
        <repo type="binary">repos/atom/x86_64/packages</repo>
        <repo type="debug">repos/atom/x86_64/debug</repo>
        <repo type="source">repos/atom/x86_64/sources</repo>
      </arch>
    </buildtarget>
    <buildtarget name="exynos">
      <buildconf>
        <location href="3bd64bd5fa862d99dbc363ccb1557d137b5685bc3bfe9a86bcbf50767da5e2e8-build.conf"/>
        <checksum type="sh256">3bd64bd5fa862d99dbc363ccb1557d137b5685bc3bfe9a86bcbf50767da5e2e8</checksum>
      </buildconf>
      <arch default="yes" name="armv7l">
        <repo type="binary">repos/exynos/armv7l/packages</repo>
        <repo type="debug">repos/exynos/armv7l/debug</repo>
        <repo type="source">repos/exynos/armv7l/sources</repo>
      </arch>
    </buildtarget>
  </buildtargets>
  <id>tizen-2.1_20130326.13</id>
</build>
"""

class BuildDataTest(unittest.TestCase):
    '''Tests for BuildData functionality.'''

    def test_load(self):
        bdata = BuildData(build_id='test.id')
        bdata.load(TEST_XML)
        self.assertEqual(bdata.targets, OrderedDict(
            [(u'atom', {'buildconf':
               {'checksum': {'type': u'sh256',
                             'value': u'3bd64bd5fa862d99dbc363ccb1557d137b5685bc3bfe9a86bcbf50767da5e2e8'},
                'location':  u'3bd64bd5fa862d99dbc363ccb1557d137b5685bc3bfe9a86bcbf50767da5e2e8-build.conf'},
               'name': u'atom', 'archs': [u'i586', u'x86_64']}),
             (u'exynos', {'buildconf':
               {'checksum': {'type': u'sh256',
                             'value': u'3bd64bd5fa862d99dbc363ccb1557d137b5685bc3bfe9a86bcbf50767da5e2e8'},
                'location': u'3bd64bd5fa862d99dbc363ccb1557d137b5685bc3bfe9a86bcbf50767da5e2e8-build.conf'},
               'name': u'exynos', 'archs': [u'armv7l']})]))

    def test_load_error(self):
        """Test rasing BuildDataError."""
        bdata = BuildData(1)
        self.assertRaises(BuildDataError, bdata.load, '<test/>')


    def test_add_target(self):
        """Test adding new target."""
        bdata = BuildData(1)
        target = {"name": "test_target",
                  "archs": ['i586'],
                  "buildconf": {
                      "checksum": {
                          "type": "md5",
                          "value": "45c5fb8bd2b9065bd7eb961cf3663b8c"
                       },
                      "location": 'build.conf'
                   }
                 }

        bdata.add_target(target)
        self.assertTrue(target["name"] in bdata.targets)


    def test_to_xml(self):
        """Test xml output."""
        bdata = BuildData(build_id='test.id')
        bdata.load(TEST_XML)
        self.assertEqual(len(bdata.to_xml()), 964)
        self.assertEqual(len(bdata.to_xml(hreadable=False)), 809)


    def test_save(self):
        bdata = BuildData(build_id='test.id')
        bdata.load(TEST_XML)
        fname = 'test_save.tmp'
        bdata.save(fname)
        self.assertEqual(len(open(fname).read()), 964)
        os.unlink(fname)
