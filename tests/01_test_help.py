# vim: set fileencoding=utf-8 :
#
# check if --help works

import os
import unittest

class TestHelp(unittest.TestCase):
    """Test help output of gbs commands"""

    def testSubCommandHelp(self):
        for prog in [ "build", "remotebuild"]:
            ret = os.system("gbs help %s > /dev/null"  % prog)
            self.assertEqual(ret, 0)

            ret = os.system("gbs %s --help > /dev/null"  % prog)
            self.assertEqual(ret, 0)

    def testHelp(self):
        ret = os.system("gbs --help > /dev/null")
        self.assertEqual(ret, 0)

        ret = os.system("gbs help > /dev/null")
        self.assertEqual(ret, 0)
