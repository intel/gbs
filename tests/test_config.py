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

"""Functional tests for GBS config"""

import os
import unittest

from mock import patch

from gitbuildsys.errors import ConfigError
import gitbuildsys.conf


FILE_DIRNAME = os.path.dirname(os.path.abspath(__file__))


class Fixture(object):
    '''test fixture for testing config'''

    PATH = os.path.join(FILE_DIRNAME, 'testdata', 'ini')

    ETC = '/etc/gbs.conf'
    HOME = '~/.gbs.conf'
    PROJECT = '.gbs.conf'

    def __init__(self, etc=None, home=None, project=None):
        self.fake_files = {self.ETC: etc,
                           self.HOME: home,
                           self.PROJECT: project,
                           }

        self.real_exists = os.path.exists
        self.real_abspath = os.path.abspath
        self.real_expanduser = os.path.expanduser

    def fake_exists(self, path):
        '''return True if corresponding fixture specified'''
        return bool(self.fake_files[path]) if path in self.fake_files \
            else self.real_exists(path)

    def fake_abspath(self, path):
        '''return itself if it's match fixture name'''
        return path if path in self.fake_files else self.real_abspath(path)

    def fake_expanduser(self, path):
        '''return itself if it's match fixture name'''
        return path if path in self.fake_files else self.real_expanduser(path)

    def fake_open(self, name, *args):
        '''open corresponding fixture file and return'''
        return open(os.path.join(self.PATH, self.fake_files[name])) \
                    if name in self.fake_files \
                    else open(name, *args)

    def __call__(self, func):
        '''decorator to setup fixtures'''
        patchers = [
            patch('gitbuildsys.conf.os.path.exists', self.fake_exists),
            patch('gitbuildsys.conf.os.path.expanduser', self.fake_expanduser),
            patch('gitbuildsys.conf.os.path.abspath', self.fake_abspath),
            patch('ConfigParser.open', self.fake_open, create=True),
            ]
        for patcher in patchers:
            func = patcher(func)
        return func


class ConfigGettingTest(unittest.TestCase):
    '''TestCase for config'''

    @staticmethod
    def get(section, option):
        '''get section.option from config'''
        # configmgr is a global variable, reload to recreate it
        # otherwise fixtures only take effect in the first time
        reload(gitbuildsys.conf)
        return gitbuildsys.conf.configmgr.get(option, section)

    @staticmethod
    def add_conf(fpath):
        '''get section.option from config'''
        # configmgr is a global variable, reload to recreate it
        # otherwise fixtures only take effect in the first time
        reload(gitbuildsys.conf)
        return gitbuildsys.conf.configmgr.add_conf(fpath)


    @Fixture(project='project1.ini')
    def test_no_such_section(self):
        '''test no such section'''
        self.assertRaises(ConfigError,
                          self.get, 'not_exists_section', 'key')

    @Fixture(project='project1.ini')
    def test_no_such_option(self):
        '''test no such option'''
        self.assertRaises(ConfigError,
                          self.get, 'section', 'not_exists_option')

    @Fixture(project='project1.ini')
    def test_simple_get(self):
        '''get value when one config file provides'''
        self.assertEqual('projv2', self.get('section', 'proj_only_key'))

    @Fixture(home='home1.ini', project='project1.ini')
    def test_inherit(self):
        '''value can be inherit from two levels'''
        self.assertEqual('homev2', self.get('section', 'home_only_key'))

    @Fixture(home='home1.ini', project='project1.ini')
    def test_overwrite(self):
        '''value can be overwrite if name is the same'''
        self.assertEqual('projv1', self.get('section', 'common_key'))

    @Fixture(home='home1.ini')
    def test_default_value(self):
        'test get hardcode default value '
        self.assertEquals('/var/tmp', self.get('general', 'tmpdir'))

    @Fixture(home='without_section_header.ini')
    def test_invalid_ini(self):
        'test invalid ini'
        self.assertRaises(ConfigError, reload, gitbuildsys.conf)

    @Fixture(home='invalid_continuation_line.ini')
    def test_invalid_continuation_line(self):
        'test invalid cointinuation line'
        self.assertRaises(ConfigError, reload, gitbuildsys.conf)

    @Fixture(home='interpolation.ini')
    def test_interpolation(self):
        'test interpolation is supported'
        self.assertEquals('abc/def', self.get('remote', 'target'))

    @Fixture(home='home1.ini')
    def test_addconf(self):
        '''value can be inherit from two levels'''
        self.add_conf(os.path.join(FILE_DIRNAME, 'testdata', 'ini', 'project1.ini'))
        self.assertEqual('homev2', self.get('section', 'home_only_key'))


if __name__ == '__main__':
    unittest.main()
