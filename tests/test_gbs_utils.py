import unittest
#import os
from gitbuildsys import utils

class TestUpsteramTarball(unittest.TestCase):
    """test class UpstreamTarBall in utils"""

    def setUp(self):
        """Init a tarball base name"""
        self.pkgname, self.version = ('osc-perm', '5.1.1')

    def _testTarballFormat(self, postfix):
        """test the sepecified tarball format is supported or not"""
        obj = utils.UpstreamTarball(self.pkgname+'-'+self.version+postfix)
        pkg, ver = obj.guess_version() or ('', '')
        self.assertEqual(pkg, self.pkgname)
        self.assertEqual(ver, self.version)

    def testGZ(self):

        self._testTarballFormat('.tar.gz')

    def testBZ2(self):

        self._testTarballFormat('.tar.bz2')

    def testTizen(self):

        self._testTarballFormat('-tizen.tar.bz2')
        
    def testZIP(self):

        self._testTarballFormat('.zip')

    def testTGZ(self):

        self._testTarballFormat('.tgz')

    def testNegative(self):

        self._testTarballFormat('.src.rpm')
        self._testTarballFormat('.orig.tar.gz')
#if __name__ = '__main__'
#    unittest.main()
