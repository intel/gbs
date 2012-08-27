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

"""Unit tests for class SafeURL"""

import unittest

from gitbuildsys.safe_url import SafeURL


class SafeURLTest(unittest.TestCase):
    '''Test SafeURL class'''

    def test_duplicated_user(self):
        '''raise ValueError if specify user twice'''
        self.assertRaises(ValueError, SafeURL, 'http://Alice@server', 'Bob')

    def test_duplicated_password(self):
        '''raise ValueError if specify passwd twice'''
        self.assertRaises(ValueError, SafeURL,
                          'http://Alice:pp@server', None, 'password')

    def test_passwd_no_user(self):
        '''raise ValueError if only given password'''
        self.assertRaises(ValueError, SafeURL, 'http://:password@server')

    def test_password_no_user2(self):
        '''raise ValueError if only given password'''
        self.assertRaises(ValueError, SafeURL, 'http://server', None, 'passwd')

    def test_both_user_and_password(self):
        '''both user and passwd are given'''
        url = SafeURL('http://server', 'Alice', 'password')

        self.assertEqual('http://server', url)
        self.assertEqual('http://Alice:password@server', url.full)

    def test_only_user_no_password(self):
        '''only user no password'''
        url = SafeURL('http://Alice@server')

        self.assertEqual('http://server', url)
        self.assertEqual('http://Alice@server', url.full)

    def test_no_user_and_no_password(self):
        '''no user and no passwd'''
        url = SafeURL('http://server')

        self.assertEqual('http://server', url)
        self.assertEqual(url, url.full)

    def test_port(self):
        '''port given'''
        url = SafeURL('http://Alice:password@server:8080')

        self.assertEqual('http://server:8080', str(url))
        self.assertEqual('http://Alice:password@server:8080', url.full)

    def test_escape_userinfo(self):
        '''user and passwd should be escape'''
        url = SafeURL('http://server', 'Alice', 'a;/?:@&=+$,b')

        self.assertEqual('http://Alice:a%3B%2F%3F%3A%40%26%3D%2B%24%2Cb@server',
                         url.full)

    def test_join_double_dot(self):
        '''reduce double dot in path'''
        url = SafeURL('https://download.tz.otcshare.org/snapshots/trunk/'
                      'common/latest/repos/non-oss/armv7l/packages')

        self.assertEqual('https://download.tz.otcshare.org/snapshots/trunk/'
                         'common/latest/builddata/build.xml',
                         url.pathjoin('../../../../builddata/build.xml'))

    def test_join_build_conf(self):
        '''get build conf'''
        url = SafeURL('https://download.tz.otcshare.org/snapshots/trunk/'
                      'common/latest')

        self.assertEqual('https://download.tz.otcshare.org/snapshots/trunk/'
                         'common/latest/builddata/test.conf',
                         url.pathjoin('builddata/test.conf'))

    def test_join_build_conf2(self):
        '''get build conf'''
        url = SafeURL('https://download.tz.otcshare.org/snapshots/trunk/'
                      'common/latest/builddata/build.xml')

        self.assertEqual('https://download.tz.otcshare.org/snapshots/trunk/'
                         'common/latest/builddata/test.conf',
                         url.urljoin('test.conf'))

    def test_join_build_xml(self):
        '''get build xml'''
        url = SafeURL('https://download.tz.otcshare.org/snapshots/trunk/'
                      'common/latest')

        self.assertEqual('https://download.tz.otcshare.org/snapshots/trunk/'
                         'common/latest/builddata/build.xml',
                         url.pathjoin('builddata/build.xml'))

    def test_join_repo(self):
        '''get repo and arch repo'''
        url = SafeURL('https://download.tz.otcshare.org/snapshots/trunk/'
                      'common/latest')

        self.assertEqual('https://download.tz.otcshare.org/snapshots/trunk/'
                         'common/latest/repos/non-oss/armv7l/packages',
                         url.pathjoin('repos/non-oss/armv7l/packages'))

    def test_local_path(self):
        '''local path should not change'''
        url = SafeURL('/local/path')

        self.assertEqual('/local/path', url)
        self.assertEqual(url, url.full)