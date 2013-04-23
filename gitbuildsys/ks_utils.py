#!/usr/bin/python -tt
# vim: ai ts=4 sts=4 et sw=4
#
# Copyright (c) 2013 Intel, Inc.
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

"""Helpers, convenience utils, common APIs for ks file"""

import os
import urlparse

from gitbuildsys.safe_url import SafeURL
from argparse import ArgumentParser
from gitbuildsys.log import LOGGER as log

class KSRepoUpdater(object):
    '''util class for updating repos in ks file'''
    def __init__(self, ksfile):
        self.ksfile = ksfile
        with open(self.ksfile) as fobj:
            self.kstext = fobj.read()

    @staticmethod
    def _parse_repo(repo_str):
        ''' parse repo lines into optparser strcuture'''
        repoparser = ArgumentParser()
        repoparser.add_argument('--baseurl')
        return repoparser.parse_known_args(repo_str.split())

    @staticmethod
    def _build_repo(name, url, priority=None, user=None, passwd=None,
                    save=False, ssl_verify=None):
        '''build repo str with specified repo options'''
        repo_args = ['repo']
        if url.startswith('/'):
            url = 'file:///' + url.lstrip('/')
        if user and passwd:
            url = SafeURL(url, user, passwd).full
        repo_args.append('--name=%s'  % name)
        repo_args.append('--baseurl=%s' % url)
        if priority:
            repo_args.append('--priority=%s' % priority)
        if save:
            repo_args.append('--save')
        if ssl_verify:
            repo_args.append('--ssl_verify=no')
        return  ' '.join(repo_args)

    def add_authinfo(self, host, user, passwd):
        '''add user/passwd info for specified host related repo'''
        kslist = self.kstext.splitlines()
        for index, value in enumerate(kslist):
            if value.startswith('repo'):
                repoargs = self._parse_repo(value)
                repo_host = urlparse.urlsplit(repoargs[0].baseurl).hostname
                if repo_host != host:
                    continue
                repoargs[0].baseurl = SafeURL(repoargs[0].baseurl, user, passwd).full
                new_repo =  ' '.join(repoargs[1])
                new_repo = '%s --baseurl=%s' % (new_repo, repoargs[0].baseurl)
                kslist[index] = new_repo
        # update to kstext
        self.kstext = '\n'.join(kslist)

    def add_repo(self, name, url, priority=None, user=None, passwd=None,
                 save=False, ssl_verify=None):
        '''add a new repo to ks file'''
        kslist = self.kstext.splitlines()
        for index, value in enumerate(kslist):
            if value.startswith('repo'):
                kslist.insert(index, self._build_repo(name, url, priority,
                              user, passwd, save, ssl_verify))
                self.kstext = '\n'.join(kslist)
                break
        else:
            log.warning("no repo found, don't know where to insert new repo")

    def update_build_id(self, build_id):
        '''replace @BUILD_ID@ in ks file with specified build_id'''
        if "@BUILD_ID@" in self.kstext:
            self.kstext = self.kstext.replace("@BUILD_ID@", build_id)

    def sync(self):
        '''update changes back to original ks file'''
        with open(self.ksfile, 'w') as fobj:
            fobj.write(self.kstext)
