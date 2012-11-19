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
import urllib2
import M2Crypto
from M2Crypto.SSL.Checker import SSLVerificationError
import ssl

from collections import defaultdict
from urllib import quote_plus, pathname2url

from gitbuildsys import msger
from gitbuildsys.utils import hexdigest
from gitbuildsys.errors import ObsError

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

    def copy_project(self, src, target, rewrite=False):
        """
        Create new OBS project based on existing project.
        Copy config and repositories from src project to target
        """

        if not self.exists(src):
            raise ObsError('base project: %s not exists' % src)

        if self.exists(target):
            msger.warning('target project: %s exists' % target)
            if rewrite:
                msger.warning('rewriting target project %s' % target)
            else:
                return

        # Create target meta
        meta = '<project name="%s"><title></title><description></description>'\
               '<person role="maintainer" userid="%s"/>' % \
               (target, conf.get_apiurl_usr(self.apiurl))

        # Collect source repos
        repos = defaultdict(list)
        for repo in core.get_repos_of_project(self.apiurl, src):
            repos[repo.name].append(repo.arch)

        # Copy repos to target
        for name in repos:
            meta += '<repository name="%s">' % name
            meta += '<path project="%s" repository="%s" />' % (src, name)
            for arch in repos[name]:
                meta += "<arch>%s</arch>\n" % arch
            meta += "</repository>\n"
        meta += "</project>\n"

        try:
            # Create project and set its meta
            core.edit_meta('prj', path_args=quote_plus(target), data=meta)
        except (urllib2.URLError, M2Crypto.m2urllib2.URLError,
                M2Crypto.SSL.SSLError), err:
            raise ObsError("Can't set meta for %s: %s" % (target, str(err)))

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

    def exists(self, prj, pkg=''):
        """Check if project or package exists."""

        metatype = 'prj'
        path_args = [core.quote_plus(prj)]
        if pkg:
            metatype = 'pkg'
            path_args.append(core.quote_plus(pkg))
        err = None
        try:
            core.meta_exists(metatype = metatype, path_args = tuple(path_args),
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
        rfiles = core.meta_get_filelist(self.apiurl, prj, pkg, verbose=True)

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

    @msger.waiting
    def commit_files(self, prj, pkg, files, message):
        """Commits files to OBS."""

        query = {'cmd'    : 'commitfilelist',
                 'user'   : conf.get_apiurl_usr(self.apiurl),
                 'comment': message}
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

    @msger.waiting
    def remove_files(self, prj, pkg, fnames=None):
        """
        Remove file[s] from the package.
        If filenames are not provided remove all files.
        """
        if not fnames:
            url = core.makeurl(self.apiurl, ['source', prj, pkg])
            for i in (1, 2, 3):
                try:
                    response = self.core_http(core.http_GET, url).read()
                    entries = core.ET.fromstring(response)
                    break
                except OSCError, err:
                    raise ObsError("can't get list of sources from"\
                                   " %s/%s: %s" % (prj, pkg, err))
                except core.ET.ParseError, err:
                    if i == 3:
                        raise ObsError("Error parsing OBS response: %s" \
                                       % str(err))
                    continue

            fnames = [entry.get('name') for entry in entries]

        for fname in fnames:
            if fname is None:
                continue
            query = 'rev=upload'
            url = core.makeurl(self.apiurl,
                               ['source', prj, pkg, pathname2url(fname)],
                               query=query)
            try:
                self.core_http(core.http_DELETE, url)
            except OSCError, err:
                raise ObsError("can\'t remove file %s/%s/%s: %s" \
                               % (prj, pkg, fname, err))

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
            repo, arch, status = res.split()
            results[repo][arch] = status
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
