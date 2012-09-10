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
"""Functional tests for setting passwdx back to config"""
import unittest
from StringIO import StringIO

from mock import patch

from test_config import Fixture
import gitbuildsys.conf
from gitbuildsys.errors import ConfigError


class FakeFile(object):
    'Fake file used to get updated config file'

    def __init__(self):
        self.buffer = StringIO()

    def write(self, data):
        'write data into fake file'
        self.buffer.write(data)

    def close(self):
        'do not close buffer, then call getvalue() to retrieve the content'

    def getvalue(self):
        'get content of fake file'
        return self.buffer.getvalue()


@patch('gitbuildsys.conf.open', create=True)
class PasswdxTest(unittest.TestCase):
    'Test for setting passwdx'

    @Fixture(home='plain_passwd.ini')
    def test_one_file(self, fake_open):
        'test passwdx set back to one file'
        conf = FakeFile()
        fake_open.return_value = conf

        reload(gitbuildsys.conf)

        self.assertEquals('''[remotebuild]
build_server = https://api
passwdx = QlpoOTFBWSZTWYfNdxYAAAIBgAoAHAAgADDNAMNEA24u5IpwoSEPmu4s

[build]
repo1.url = https://repo1
repo1.passwdx = QlpoOTFBWSZTWYfNdxYAAAIBgAoAHAAgADDNAMNEA24u5IpwoSEPmu4s
''', conf.getvalue())


    @Fixture(home='plain_passwd.ini', project='plain_passwd2.ini')
    def test_two_files(self, fake_open):
        'test passwdx set back to two files'
        confs = [FakeFile(), FakeFile()]
        bak = confs[:]
        fake_open.side_effect = lambda *args, **kw: bak.pop()

        reload(gitbuildsys.conf)

        self.assertEquals('''[remotebuild]
build_server = https://api
passwdx = QlpoOTFBWSZTWYfNdxYAAAIBgAoAHAAgADDNAMNEA24u5IpwoSEPmu4s

[build]
repo1.url = https://repo1
repo1.passwdx = QlpoOTFBWSZTWYfNdxYAAAIBgAoAHAAgADDNAMNEA24u5IpwoSEPmu4s
''', confs[0].getvalue())

        self.assertEquals('''[remotebuild]
build_server = https://api
user = test
passwdx = QlpoOTFBWSZTWYfNdxYAAAIBgAoAHAAgADDNAMNEA24u5IpwoSEPmu4s

[build]
repo1.url = https://repo1
repo1.user = test
repo1.passwdx = QlpoOTFBWSZTWYfNdxYAAAIBgAoAHAAgADDNAMNEA24u5IpwoSEPmu4s
''', confs[1].getvalue())


    @Fixture(home='normal_passwdx.ini')
    def test_get_passwdx(self, _fake_open):
        'test get decode passwd'
        reload(gitbuildsys.conf)

        pwd = gitbuildsys.conf.configmgr.get('passwd', 'remotebuild')
        self.assertEquals('secret', pwd)

    @Fixture(home='plain_passwd.ini')
    def test_get_passwd(self, _fake_open):
        'test get decode passwd'
        reload(gitbuildsys.conf)

        pwd = gitbuildsys.conf.configmgr.get('passwd', 'remotebuild')
        self.assertEquals('secret', pwd)

    @Fixture(home='bad_passwdx.ini')
    def test_bad_passwdx(self, _fake_open):
        'test bad passwdx'
        reload(gitbuildsys.conf)

        self.assertRaises(ConfigError, gitbuildsys.conf.configmgr.get,
                          'passwd', 'remotebuild')

    @Fixture(home='empty_passwdx.ini')
    def test_empty_passwdx(self, _fake_open):
        'test empty passwdx'
        reload(gitbuildsys.conf)

        pwd = gitbuildsys.conf.configmgr.get('passwd', 'remotebuild')
        self.assertEquals('', pwd)


if __name__ == '__main__':
    unittest.main()