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
"""Functional tests for profile style of config"""
import unittest

from mock import patch, MagicMock, Mock

import gitbuildsys.conf
from test_config import Fixture
from test_passwdx import FakeFile


def get_profile():
    '''get current profile to test'''
    reload(gitbuildsys.conf)
    return gitbuildsys.conf.configmgr.get_current_profile()


class ProfileStyleTest(unittest.TestCase):
    '''Test for profile oriented config'''

    @Fixture(home='profile.ini')
    def test_profile_api(self):
        'test get obs api'
        self.assertEquals('https://api.tz/path', get_profile().obs.url)

    @Fixture(home='profile.ini')
    def test_api_inherit_auth(self):
        'test api can inherit auto from parent profile section'
        self.assertEquals('https://Alice:secret@api.tz/path',
                          get_profile().obs.url.full)

    @Fixture(home='profile_only_has_api.ini')
    def test_api_auth_can_be_overwrite(self):
        'test api auth can be overwrite'
        self.assertEquals('https://Bob:classified@api.tz/path',
                          get_profile().obs.url.full)

    @Fixture(home='profile.ini')
    def test_profile_repos_in_order(self):
        'repos must be in same order as they are write in config'
        self.assertEquals(['https://repo/ia32/main',
                           'https://repo/ia32/non-oss',
                           'https://repo/ia32/base',
                           '/local/path'],
                          [i.url for i in get_profile().repos])

    @Fixture(home='profile.ini')
    def test_repo_inherit_auth(self):
        'test repo can inherit auth from parent section'
        self.assertEquals('https://Alice:secret@repo/ia32/main',
                          get_profile().repos[0].url.full)

    @Fixture(home='profile.ini')
    def test_repo_overwrite_auth(self):
        'test repo auth can be overwrite'
        self.assertEquals('https://Bob:classified@repo/ia32/base',
                          get_profile().repos[2].url.full)

    @Fixture(home='no_such_profile_section_name.ini')
    def test_no_such_profile(self):
        'test get a empty profile when name does not exist'
        profile = get_profile()
        self.assertEquals(None, profile.obs)
        self.assertEquals([], profile.repos)

    @Fixture(home='profile.ini')
    def test_local_repo_need_not_auth(self):
        '''test local path needn't auth info'''
        self.assertEquals('/local/path', get_profile().repos[3].url.full)

    @Fixture(home='profile.ini')
    def test_obs_base_project(self):
        'test read base project from conf'
        self.assertEquals('base', get_profile().obs.base)

    @Fixture(home='profile.ini')
    def test_obs_target_project(self):
        'test read target project from conf'
        self.assertEquals('target', get_profile().obs.target)


@patch('gitbuildsys.conf.open', MagicMock(), create=True)
@patch('gitbuildsys.conf.os.rename', Mock())
class SubcommandStyleTest(unittest.TestCase):
    '''test for subcommand oriented config'''

    @Fixture(home='subcommand.ini')
    def test_api(self):
        'test obs api'
        self.assertEquals('https://api/build/server', get_profile().obs.url)

    @Fixture(home='subcommand.ini')
    def test_api_auth(self):
        'test api auth'
        self.assertEquals('https://Alice:secret@api/build/server',
                          get_profile().obs.url.full)

    @Fixture(home='subcommand.ini')
    def test_repos_in_order(self):
        'repos list must be in the same order as they are write in config'
        self.assertEquals(['https://repo1/path',
                           'https://repo2/path',
                           '/local/path/repo'],
                          [i.url for i in get_profile().repos])

    @Fixture(home='subcommand.ini')
    def test_repo_auth(self):
        'test repo auth'
        self.assertEquals('https://Alice:secret@repo1/path',
                          get_profile().repos[0].url.full)



@patch('gitbuildsys.conf.open', create=True)
class ConvertTest(unittest.TestCase):
    'Test convert subcommand to profile'

    @Fixture(home='subcommand.ini')
    def test_convert(self, fake_open):
        'test convert'
        conf = FakeFile()
        fake_open.return_value = conf

        get_profile()

        self.assertEquals(conf.getvalue(), '''[general]
profile = profile.current

[obs.remotebuild]
url = https://api/build/server
user = Alice
passwdx = QlpoOTFBWSZTWYfNdxYAAAIBgAoAHAAgADDNAMNEA24u5IpwoSEPmu4s
base_prj = Main
target_prj = Target

[repo.repo1]
url = https://repo1/path
user = Alice
passwdx = QlpoOTFBWSZTWYfNdxYAAAIBgAoAHAAgADDNAMNEA24u5IpwoSEPmu4s

[repo.repo2]
url = https://repo2/path
user = Alice
passwdx = QlpoOTFBWSZTWYfNdxYAAAIBgAoAHAAgADDNAMNEA24u5IpwoSEPmu4s

[repo.repo3]
url = /local/path/repo

[profile.current]
obs = obs.remotebuild
repos = repo.repo1, repo.repo2, repo.repo3

''')





if __name__ == '__main__':
    unittest.main()