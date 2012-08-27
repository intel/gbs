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

"""
This module provides a class SafeURL which can contain url/user/password read
from config file, and hide plain user and password when it print to screen
"""

import urllib
import urlparse


class SafeURL(str):

    '''SafeURL can hide user info when it's printed to console.
    Use property full to get url with user info
    '''

    def __new__(cls, url, user=None, passwd=None):
        safe_url, inline_user, inline_passwd = SafeURL._extract_userinfo(url)

        inst = super(SafeURL, cls).__new__(cls, safe_url)

        inst.user, inst.passwd = SafeURL._check_userinfo(inline_user,
                                                         inline_passwd,
                                                         user, passwd)
        inst.components = urlparse.urlsplit(safe_url)
        return inst

    @property
    def full(self):
        '''return the full url with user and password'''
        userinfo = self._get_userinfo()
        hostport = self._get_hostport(self.components)

        if userinfo:
            login = '%s@%s' % (userinfo, hostport)
        else:
            login = hostport

        new_components = list(self.components)
        new_components[1] = login
        return urlparse.urlunsplit(new_components)

    def pathjoin(self, *args):
        '''treat self as path and urljoin'''
        new = urlparse.urljoin(self.rstrip('/') + '/', *args)
        return SafeURL(new, self.user, self.passwd)

    def urljoin(self, *args):
        '''join by urlparse.urljoin'''
        return SafeURL(urlparse.urljoin(self, *args), self.user, self.passwd)

    def _get_userinfo(self):
        '''return userinfo component of url'''
        if not self.user:
            return ''

        escape = lambda raw: urllib.quote(raw, safe='')
        return '%s:%s' % (escape(self.user), escape(self.passwd)) \
            if self.passwd else escape(self.user)

    @staticmethod
    def _extract_userinfo(url):
        '''strip inline user/password from url'''
        results = urlparse.urlsplit(url)
        hostport = SafeURL._get_hostport(results)

        components = list(results)
        components[1] = hostport
        safe_url = urlparse.urlunsplit(components)

        return safe_url, results.username, results.password

    @staticmethod
    def _get_hostport(components):
        '''return hostport component from urlsplit result'''
        if components.port:
            return '%s:%d' % (components.hostname, components.port)
        return components.hostname

    @staticmethod
    def _check_userinfo(user_inline, passwd_inline, user, passwd):
        '''returns the valid user and passwd'''

        if user_inline and user or passwd_inline and passwd:
            raise ValueError('Auth info specified twice')

        user = user or user_inline
        passwd = passwd or passwd_inline

        if not user and passwd:
            raise ValueError('No user is specified only password')
        return user, passwd
