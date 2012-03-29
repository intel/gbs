# vim: set fileencoding=utf-8 :
#
# check if --help works

import os
import unittest
from gitbuildsys import utils

class TestParseSpec(unittest.TestCase):
    """Test utils.parse_spec of gbs function"""
    spec_path = 'tests/testdata/bluez.spec'
    def testParseSpecGoodInput(self):
        valid_keys = ('Name', 'Version', 'Release', 'Summary', 'Description', 'License',
			'Group', 'Url', 'Os', 'Arch', 'Requireflags', 'Requirename', 'Requireversion',
			'Platform', 'build', 'buildRoot', 'clean', 'install', 'prep','source0', 'patch0')
	valid_keys2 = (100, 1000, 1001, 1002, 1004, 1005, 1014, 1016, 1020, 1021, 1022, 1048, 1049, 1050, 1132)
        for s in valid_keys:
            ret = utils.parse_spec(self.spec_path, s)
            self.assertNotEqual(ret, '')
        for s in valid_keys2:
            ret = utils.parse_spec(self.spec_path, s)
            self.assertNotEqual(ret, '')
    def testParseSpecBadInput(self):
        invalid_keys = ('names', 'versions', 'test', 'source1000', 'source', 'patch1000', 'patchs','patch-source0',
			'', [], {}, 101, 1003)
	for s in invalid_keys:
	    self.assertRaises(Exception, utils.parse_spec, self.spec_path, s)
