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

"""
This module provides wrapper class around OSC API.
Only APIs which are required by cmd_remotebuild present here.

"""

import os
import re
import urllib2
import M2Crypto
from M2Crypto.SSL.Checker import SSLVerificationError
import ssl

from collections import defaultdict
from urllib import quote_plus, pathname2url

from xml.etree import cElementTree as ET

from gitbuildsys.utils import hexdigest
from gitbuildsys.errors import ObsError
from gitbuildsys.log import waiting
from gitbuildsys.log import LOGGER as logger

from osc import conf, core

class OSCError(Exception):
    """Local exception class."""
    pass


class OSC(object):
    """Interface to OSC API"""

    def __init__(self, apiurl=None, oscrc=None):
        if oscrc:
            try:
                conf.get_config(override_conffile = oscrc)
            except OSError, err:
                if err.errno == 1:
                    # permission problem, should be the chmod(0600) issue
                    raise ObsError('Current user has no write permission '\
                                   'for specified oscrc: %s' % oscrc)

                raise # else
            except urllib2.URLError:
                raise ObsError("invalid service apiurl: %s" % apiurl)
        else:
            conf.get_config()

        if apiurl:
            self.apiurl = apiurl
        else:
            self.apiurl = conf.config['apiurl']

    @staticmethod
    def core_http(method, url, data=None, filep=None):
        """Wrapper above core.<http_METHOD> to catch exceptions."""

        # Workarounded osc bug. http_GET sometimes returns empty response
        # Usually next try succeeds, so let's try 3 times
        for count in (1, 2, 3):
            try:
                return method(url, data=data, file=filep)
            except (urllib2.URLError, M2Crypto.m2urllib2.URLError,
                    M2Crypto.SSL.SSLError, ssl.SSLError), err:
                if count == 3:
                    raise OSCError(str(err))

        raise OSCError('Got empty response from %s %s' % \
                       (method.func_name.split('_')[-1], url))

    def get_repos_of_project(self, project):
        """Get dictionary name: list of archs for project repos"""
        repos = defaultdict(list)
        for repo in core.get_repos_of_project(self.apiurl, project):
            repos[repo.name].append(repo.arch)
        return repos

    def create_project(self, target, src=None, rewrite=False,
                       description='', linkto='', linkedbuild=''):
        """
        Create new OBS project based on existing project.
        Copy config and repositories from src project to target
        if src exists.
        """

        if src and not self.exists(src):
            raise ObsError('base project: %s not exists' % src)

        if self.exists(target):
            logger.warning('target project: %s exists' % target)
            if rewrite:
                logger.warning('rewriting target project %s' % target)
            else:
                return

        # Create target meta
        meta = '<project name="%s"><title></title>'\
	       '<description>%s</description>'\
               '<person role="maintainer" userid="%s"/>' % \
               (target, description, conf.get_apiurl_usr(self.apiurl))
        if linkto:
            meta += '<link project="%s"/>' % linkto

        # Collect source repos if src project exist
        if src:
            # Copy repos to target
            repos = self.get_repos_of_project(src)
            for name in repos:
                if linkedbuild:
                    meta += '<repository name="%s" linkedbuild="%s">' % \
                                (name, linkedbuild)
                else:
                    meta += '<repository name="%s">' % name
                meta += '<path project="%s" repository="%s" />' % (src, name)
                for arch in repos[name]:
                    meta += "<arch>%s</arch>\n" % arch
                meta += "</repository>\n"
        else:
            logger.warning('no project repos in target project, please add '
                'repos from OBS webUI manually, or specify base project '
                'with -B <base_prj>, then gbs can help to set repos '
                'using the settings of the specified base project.')
        meta += "</project>\n"

        try:
            # Create project and set its meta
            core.edit_meta('prj', path_args=quote_plus(target), data=meta)
        except (urllib2.URLError, M2Crypto.m2urllib2.URLError,
                M2Crypto.SSL.SSLError), err:
            raise ObsError("Can't set meta for %s: %s" % (target, str(err)))

        # don't need set project config if no src project
        if not src:
            return

        # copy project config
        try:
            config = core.show_project_conf(self.apiurl, src)
        except (urllib2.URLError, M2Crypto.m2urllib2.URLError,
                M2Crypto.SSL.SSLError), err:
            raise ObsError("Can't get config from project %s: %s" \
                           % (src, str(err)))

        url = core.make_meta_url("prjconf", quote_plus(target),
                                 self.apiurl, False)
        try:
            self.core_http(core.http_PUT, url, data=''.join(config))
        except OSCError, err:
            raise ObsError("can't copy config from %s to %s: %s" \
                           % (src, target, err))

    def delete_project(self, prj, force=False, msg=None):
        """Delete OBS project."""
        query = {}
        if force:
            query['force'] = "1"
        if msg:
            query['comment'] = msg
        url = core.makeurl(self.apiurl, ['source', prj], query)
        try:
            self.core_http(core.http_DELETE, url)
        except OSCError, err:
            raise ObsError("can't delete project %s: %s" % (prj, err))

    def exists(self, prj, pkg=''):
        """Check if project or package exists."""
        metatype, path_args = self.get_path(prj, pkg)
        err = None
        try:
            core.meta_exists(metatype = metatype, path_args = path_args,
                             create_new = False, apiurl = self.apiurl)
        except urllib2.HTTPError, err:
            if err.code == 404:
                return False
        except (urllib2.URLError, M2Crypto.m2urllib2.URLError, \
                                  M2Crypto.SSL.SSLError), err:
            pass
        except SSLVerificationError:
            raise ObsError("SSL verification error.")
        if err:
            raise ObsError("can't check if %s/%s exists: %s" % (prj, pkg, err))

        return True

    def rebuild(self, prj, pkg, arch):
        """Rebuild package."""
        try:
            return core.rebuild(self.apiurl, prj, pkg, repo=None, arch=arch)
        except (urllib2.URLError, M2Crypto.m2urllib2.URLError, \
                M2Crypto.SSL.SSLError), err:
            raise ObsError("Can't trigger rebuild for %s/%s: %s" % \
                           (prj, pkg, str(err)))
        except SSLVerificationError:
            raise ObsError("SSL verification error.")

    def diff_files(self, prj, pkg, paths):
        """
        Find difference between local and remote filelists
        Return 4 lists: (old, not changed, changed, new)
        where:
           old - present only remotely
           changed - present remotely and locally and differ
           not changed - present remotely and locally and does not not differ
           new - present only locally
        old is a list of remote filenames
        changed, not changed and new are lists of local filepaths
        """
        # Get list of files from the OBS
        rfiles = core.meta_get_filelist(self.apiurl, prj, pkg, verbose=True,\
                                        expand=True)

        old, not_changed, changed, new = [], [], [], []

        if not rfiles:
            # no remote files - all local files are new
            return old, not_changed, changed, paths[:]

        # Helper dictionary helps to avoid looping over remote files
        rdict = dict((fobj.name, (fobj.size, fobj.md5)) for fobj in rfiles)

        for lpath in paths:
            lname = os.path.basename(lpath)
            if lname in rdict:
                lsize = os.path.getsize(lpath)
                rsize, rmd5 = rdict[lname]
                if rsize == lsize and rmd5 == core.dgst(lpath):
                    not_changed.append(lpath)
                else:
                    changed.append(lpath)
                # remove processed files from the remote dict
                # after processing only old files will be letf there
                rdict.pop(lname)
            else:
                new.append(lpath)

        return rdict.keys(), not_changed, changed, new

    @waiting
    def commit_files(self, prj, pkg, files, message):
        """Commits files to OBS."""

        query = {'cmd'    : 'commitfilelist',
                 'user'   : conf.get_apiurl_usr(self.apiurl),
                 'comment': message,
                 'keeplink': 1}
        url = core.makeurl(self.apiurl, ['source', prj, pkg], query=query)

        xml = "<directory>"
        for fpath, _ in files:
            with open(fpath) as fhandle:
                xml += '<entry name="%s" md5="%s"/>' % \
                       (os.path.basename(fpath), hexdigest(fhandle))
        xml += "</directory>"

        try:
            self.core_http(core.http_POST, url, data=xml)
            for fpath, commit_flag in files:
                if commit_flag:
                    put_url = core.makeurl(
                        self.apiurl, ['source', prj, pkg,
                                      pathname2url(os.path.basename(fpath))],
                        query="rev=repository")
                    self.core_http(core.http_PUT, put_url, filep=fpath)
            self.core_http(core.http_POST, url, data=xml)
        except OSCError, err:
            raise ObsError("can't commit files to %s/%s: %s" % (prj, pkg, err))

    def create_package(self, prj, pkg):
        """Create package in the project."""

        meta = '<package project="%s" name="%s">'\
               '<title/><description/></package>' % (prj, pkg)
        url = core.make_meta_url("pkg", (quote_plus(prj), quote_plus(pkg)),
                                 self.apiurl, False)
        try:
            self.core_http(core.http_PUT, url, data=meta)
        except OSCError, err:
            raise ObsError("can't create %s/%s: %s" % (prj, pkg, err))

    def get_results(self, prj, pkg):
        """Get package build results."""
        results = defaultdict(dict)
        try:
            build_status = core.get_results(self.apiurl, prj, pkg)
        except (urllib2.URLError, M2Crypto.m2urllib2.URLError,
                M2Crypto.SSL.SSLError), err:
            raise ObsError("can't get %s/%s build results: %s" \
                           % (prj, pkg, str(err)))

        for res in build_status:
            # This regular expression is created for parsing the
            # results of of core.get_results()
            stat_re = re.compile(r'^(?P<repo>\S+)\s+(?P<arch>\S+)\s+'
                                  '(?P<status>\S*)$')
            mo = stat_re.match(res)
            if mo:
                results[mo.group('repo')][mo.group('arch')] = mo.group('status')
            else:
                logger.warning('not valid build status received: %s' % res)

        return results

    def get_buildlog(self, prj, pkg, repo, arch):
        """Get package build log from OBS."""

        url = core.makeurl(self.apiurl, ['build', prj, repo, arch, pkg,
                                         '_log?nostream=1&start=0'])
        try:
            log = self.core_http(core.http_GET, url).read()
        except OSCError, err:
            raise ObsError("can't get %s/%s build log: %s" % (prj, pkg, err))

        return log.translate(None, "".join([chr(i) \
                                            for i in range(10) + range(11,32)]))

    @staticmethod
    def get_path(prj, pkg=None):
        """Helper to get path_args out of prj and pkg."""
        metatype = 'prj'
        path_args = [quote_plus(prj)]
        if pkg:
            metatype = 'pkg'
            path_args.append(quote_plus(pkg))
        return metatype, tuple(path_args)

    def get_meta(self, prj, pkg=None):
        """Get project/package meta."""
        metatype, path_args = self.get_meta(prj, pkg)
        url = core.make_meta_url(metatype, path_args, self.apiurl)
        return self.core_http(core.http_GET, url)

    def set_meta(self, meta, prj, pkg=None):
        """Set project/package meta."""
        metatype, path_args = self.get_path(prj, pkg)
        url = core.make_meta_url(metatype, path_args, self.apiurl)
        return self.core_http(core.http_PUT, url, data=meta)

    def get_description(self, prj, pkg=None):
        """Get project/package description."""
        meta = self.get_meta(prj, pkg)
        result = ET.fromstring(meta).find('description')
        return result or result.text

    def set_description(self, description, prj, pkg=None):
        """Set project/package description."""
        meta = ET.fromstring(self.get_meta(prj, pkg))
        dsc = meta.find('description')
        dsc.text = description
        self.set_meta(ET.tostring(meta), prj, pkg)
