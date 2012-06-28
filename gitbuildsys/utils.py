#!/usr/bin/python -tt
# vim: ai ts=4 sts=4 et sw=4
#
# Copyright (c) 2011 Intel, Inc.
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

import os
import glob
import tempfile
import shutil
import pycurl
import urlparse

# cElementTree can be standard or 3rd-party depending on python version
try:
    from xml.etree import cElementTree as ET
except ImportError:
    import cElementTree as ET

import errors
import msger

class Workdir(object):
    def __init__(self, path):
        self._newdir = path
        self._cwd = os.getcwd()

    def __enter__(self):
        os.chdir(self._newdir)

    def __exit__(self, _type, _value, _tb):
        os.chdir(self._cwd)

def guess_spec(workdir, default_spec):
    if default_spec:
        if not os.path.exists(default_spec):
            msger.error('%s does not exit' % default_spec)
        return default_spec
    git_project =  os.path.basename(workdir)
    specfile = '%s/packaging/%s.spec' % (workdir, git_project)
    if not os.path.exists(specfile):
        specs = glob.glob('%s/packaging/*.spec' % workdir)
        if not specs:
            msger.error('no spec file found under %s/packaging' % workdir)

        if len(specs) > 1:
            msger.error("Can't decide which spec file to use.")
        else:
            specfile = specs[0]
    return specfile

class TempCopy(object):
    """Copy original file to temporary file in the same directory as
       original. Creates empty termporary file if original doesn't exist.
       Deletes termporary file when object is destroyed.
    """

    def __init__(self, orig_fpath):
        self.orig_fpath = orig_fpath

        # create temp file
        tmpffd, self.name = tempfile.mkstemp(dir=os.path.dirname(orig_fpath))
        os.close(tmpffd)

        # copy original file to temp
        if os.path.exists(orig_fpath):
            shutil.copy2(orig_fpath, self.name)

        self.stat = os.stat(self.name)

    def update_stat(self):
        """Updates stat info."""
        self.stat = os.stat(self.name)

    def is_changed(self):
        """Check if temporary file has been changed."""
        return os.stat(self.name) != self.stat

    def __del__(self):
        if os.path.exists(self.name):
            os.unlink(self.name)

def urlgrab(url, filename, user = None, passwd = None):

    outfile = open(filename, 'w')
    curl = pycurl.Curl()
    curl.setopt(pycurl.URL, url)
    curl.setopt(pycurl.WRITEDATA, outfile)
    curl.setopt(pycurl.FAILONERROR, True)
    curl.setopt(pycurl.FOLLOWLOCATION, True)
    curl.setopt(pycurl.SSL_VERIFYPEER, False)
    curl.setopt(pycurl.SSL_VERIFYHOST, False)
    curl.setopt(pycurl.CONNECTTIMEOUT, 30)
    if user:
        userpwd = user
        if passwd:
            userpwd = '%s:%s' % (user, passwd)
        curl.setopt(pycurl.USERPWD, userpwd)

    try:
        curl.perform()
    except pycurl.error, e:
        errcode = e.args[0]
        if errcode == pycurl.E_OPERATION_TIMEOUTED:
            raise errors.UrlError('timeout on %s: %s' % (url, e))
        elif errcode == pycurl.E_FILESIZE_EXCEEDED:
            raise errors.UrlError('max download size exceeded on %s'\
                                       % self.url)
        else:
            errmsg = 'pycurl error %s - "%s"' % (errcode, str(e.args[1]))
            raise errors.UrlError(errmsg)
    finally:
        outfile.close()
        curl.close()

    return filename

class RepoParser(object):
    """ Repository parser for generate real repourl and build config
    """
    def __init__(self, repos, cachedir):
        self.repos = repos
        self.cachedir = cachedir
        self.archs = []
        self.localrepos = []
        self.repourls  = {}
        self.buildmeta = None
        self.buildconf = None
        self.parse()

    def get_buildconf(self):
        elementTree = ET.parse(self.buildmeta)
        root = elementTree.getroot()
        buildElem = root.find('buildconf')
        if buildElem is None:
            return None
        buildconf = buildElem.text.strip()

        return buildconf

    def build_repos_from_buildmeta(self, baseurl):
        if not (self.buildmeta and os.path.exists(self.buildmeta)):
            return

        elementTree = ET.parse(self.buildmeta)
        root = elementTree.getroot()
        archs = []
        repos = []
        repo_items = root.find('repos')
        if repo_items:
            for repo in repo_items.findall('repo'):
                repos.append(repo.text.strip())
        arch_items = root.find('archs')
        if arch_items:
            for arch in arch_items.findall('arch'):
                archs.append(arch.text.strip())
        for arch in archs:
            repourls = [os.path.join(baseurl, 'repos', repo, arch, 'packages') \
                        for repo in repos]
            self.repourls[arch] = repourls
        self.archs = archs

    def parse(self):
        for repo in self.repos:
            # Check if repo is standard repo with repodata/repomd.xml exist
            repomd_url = os.path.join(repo, 'repodata/repomd.xml')
            repomd_file = os.path.join(self.cachedir, 'repomd.xml')
            try:
                urlgrab(repomd_url, repomd_file, self.repos[repo]['user'],   \
                                                 self.repos[repo]['passwd'])
                # Try to download build.xml
                buildxml_url = urlparse.urljoin(repo.rstrip('/') + '/',      \
                                          '../../../../builddata/build.xml')
                self.buildmeta = os.path.join(self.cachedir,                 \
                                            os.path.basename(buildxml_url))
                urlgrab(buildxml_url, self.buildmeta,                        \
                                                    self.repos[repo]['user'], \
                                                    self.repos[repo]['passwd'])
                # Try to download build conf
                if self.buildconf is None:
                    build_conf = self.get_buildconf()
                    buildconf_url = buildxml_url.replace(os.path.basename    \
                                                    (buildxml_url), build_conf)
                    self.buildconf = os.path.join(self.cachedir,        \
                                          os.path.basename(buildconf_url))
                    urlgrab(buildconf_url, self.buildconf,              \
                                                    self.repos[repo]['user'],\
                                                    self.repos[repo]['passwd'])
                    # buildconf downloaded succeed, break!
                    break
            except errors.UrlError:
                # if it's standard repo, that means buildconf fails to be
                # downloaded, so reset buildconf and break
                if self.buildmeta:
                    self.buildconf = None
                    break
                pass

            # Check if it's repo with builddata/build.xml exist
            buildxml_url = os.path.join(repo, 'builddata/build.xml')
            self.buildmeta = os.path.join(self.cachedir, 'build.xml')
            try:
                urlgrab(buildxml_url, self.buildmeta, self.repos[repo]['user'],\
                                                     self.repos[repo]['passwd'])
            except errors.UrlError:
                self.buildmeta = None
                continue

            # Generate repos from build.xml
            self.build_repos_from_buildmeta(repo)

            try:
                # download build conf
                build_conf = self.get_buildconf()
                buildconf_url = urlparse.urljoin(repo.rstrip('/') + '/',    \
                                                'builddata/%s' % build_conf)
                self.buildconf = os.path.join(self.cachedir,                \
                                             os.path.basename(buildconf_url))
                urlgrab(buildconf_url, self.buildconf,                      \
                                                self.repos[repo]['user'],   \
                                                self.repos[repo]['passwd'])
            except errors.UrlError:
                self.buildconf = None

        # Split out local repo
        for repo in self.repos:
            if repo.startswith('/') and os.path.exists(repo):
                self.localrepos.append(repo)

    def get_repos_by_arch(self, arch):
        #  return directly for standard repos
        if not self.repourls:
            return self.repos.keys() + self.localrepos

        if arch in ['ia32', 'i686', 'i586']:
            arch = 'ia32'

        if arch in self.repourls:
            return self.repourls[arch] + self.localrepos

        return None
