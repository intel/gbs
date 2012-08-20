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
import hashlib

# cElementTree can be standard or 3rd-party depending on python version
try:
    from xml.etree import cElementTree as ET
except ImportError:
    import cElementTree as ET

from gitbuildsys import errors, msger

from gbp.rpm.git import GitRepositoryError
from gbp.errors import GbpError


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
        default_spec = os.path.abspath(default_spec)
        if not os.path.exists(default_spec):
            msger.error('%s does not exit' % default_spec)
        return default_spec

    workdir = os.path.abspath(workdir)
    git_project =  os.path.basename(workdir)
    specfile = os.path.join(workdir, 'packaging', '%s.spec' % git_project)
    if not os.path.exists(specfile):
        specs = glob.glob(os.path.join(workdir, 'packaging', '*.spec'))
        if not specs:
            msger.error('no spec file found under %s/packaging' % workdir)

        if len(specs) > 1:
            msger.error("Can't decide which spec file to use.")
        else:
            specfile = specs[0]
    return specfile

class Temp(object):
    """
    Create temporary file or directory.
    Delete it automatically when object is destroyed.

    """

    def __init__(self, suffix='', prefix='tmp', dirn=None,
                 directory=False, content=None):
        """
        Create file or directory using tempfile.mk[sd]temp.
        If content is provided write it to the file.

        """
        self.directory = directory
        self.path = None

        try:
            if dirn:
                target_dir = os.path.abspath(os.path.join(dirn, prefix))
            else:
                target_dir = os.path.abspath(prefix)
            target_dir = os.path.dirname(target_dir)

            if not os.path.exists(target_dir):
                os.makedirs(target_dir)

            if directory:
                path = tempfile.mkdtemp(suffix, prefix, dirn)
            else:
                (fds, path) = tempfile.mkstemp(suffix, prefix, dirn)
                os.close(fds)
                if content:
                    with file(path, 'w+') as fobj:
                        fobj.write(content)
        except OSError, (e, msg):
            raise errors.GbsError("Failed to create dir or file on %s: %s" % \
                            (target_dir, msg))
        self.path = path

    def __del__(self):
        """Remove it when object is destroyed."""
        if self.path and os.path.exists(self.path):
            if self.directory:
                shutil.rmtree(self.path, True)
            else:
                os.unlink(self.path)

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
    except pycurl.error, err:
        errcode = err.args[0]
        if errcode == pycurl.E_OPERATION_TIMEOUTED:
            raise errors.UrlError('timeout on %s: %s' % (url, err))
        elif errcode == pycurl.E_FILESIZE_EXCEEDED:
            raise errors.UrlError('max download size exceeded on %s'\
                                       % url)
        else:
            errmsg = 'pycurl error %s - "%s"' % (errcode, str(err.args[1]))
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
        self.standardrepos = []
        self.parse()

    def get_buildconf(self):
        etree = ET.parse(self.buildmeta)
        buildelem = etree.getroot().find('buildconf')
        if buildelem is None:
            return None
        return buildelem.text.strip()

    def build_repos_from_buildmeta(self, baseurl):
        if not (self.buildmeta and os.path.exists(self.buildmeta)):
            return

        etree = ET.parse(self.buildmeta)
        root = etree.getroot()
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
            validrepos = []
            for repo in repourls:
                # Check if repo is valid standard repo
                repomd_url = os.path.join(repo, 'repodata/repomd.xml')
                repomd_file = os.path.join(self.cachedir, 'repomd.xml')
                try:
                    urlgrab(repomd_url, repomd_file)
                    validrepos.append(repo)
                except errors.UrlError:
                    pass
            if arch in self.repourls:
                self.repourls[arch] += validrepos
            else:
                self.repourls[arch] = validrepos
        self.archs = archs

    def parse(self):
        for repo in self.repos:

            # Check if repo is standard repo with repodata/repomd.xml exist
            repomd_url = os.path.join(repo, 'repodata/repomd.xml')
            repomd_file = os.path.join(self.cachedir, 'repomd.xml')

            try:
                urlgrab(repomd_url, repomd_file)
                self.standardrepos.append(repo)
                # Try to download build.xml
                buildxml_url = urlparse.urljoin(repo.rstrip('/') + '/',      \
                                          '../../../../builddata/build.xml')
                self.buildmeta = os.path.join(self.cachedir,                 \
                                            os.path.basename(buildxml_url))

                # Try to download build conf
                if self.buildconf is None:
                    urlgrab(buildxml_url, self.buildmeta)
                    build_conf = self.get_buildconf()
                    buildconf_url = buildxml_url.replace(os.path.basename    \
                                                    (buildxml_url), build_conf)
                    self.buildconf = os.path.join(self.cachedir,        \
                                          os.path.basename(buildconf_url))
                    urlgrab(buildconf_url, self.buildconf)
                # standard repo
                continue
            except errors.UrlError:
                # if it's standard repo, that means buildconf fails to be
                # downloaded, so reset buildconf and continue
                if self.buildmeta:
                    self.buildconf = None
                    continue
                pass

            # Check if it's repo with builddata/build.xml exist
            buildxml_url = os.path.join(repo, 'builddata/build.xml')
            self.buildmeta = os.path.join(self.cachedir, 'build.xml')
            try:
                urlgrab(buildxml_url, self.buildmeta)
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
                urlgrab(buildconf_url, self.buildconf)

            except errors.UrlError:
                self.buildconf = None

            # reset buildmeta
            self.buildmeta = None

        # Split out local repo
        for repo in self.repos:
            if repo.startswith('/') and os.path.exists(repo):
                self.localrepos.append(repo)

    def get_repos_by_arch(self, arch):
        #  return directly for standard repos
        if not self.repourls:
            return self.localrepos + self.standardrepos

        if arch in ['ia32', 'i686', 'i586']:
            arch = 'ia32'

        if arch in self.repourls:
            return self.repourls[arch] + self.localrepos + self.standardrepos

        return None

def git_status_checker(git, opts):
    try:
        if opts.commit:
            git.rev_parse(opts.commit)
        is_clean = git.is_clean()[0]
        status = git.status()
    except (GbpError, GitRepositoryError), err:
        msger.error(str(err))

    untracked_files = status['??']
    uncommitted_files = []
    for stat in status:
        if stat == '??':
            continue
        uncommitted_files.extend(status[stat])

    if not is_clean and not opts.include_all:
        if untracked_files:
            msger.warning('the following untracked files would NOT be '\
                       'included:\n   %s' % '\n   '.join(untracked_files))
        if uncommitted_files:
            msger.warning('the following uncommitted changes would NOT be '\
                       'included:\n   %s' % '\n   '.join(uncommitted_files))
        msger.warning('you can specify \'--include-all\' option to '\
                      'include these uncommitted and untracked files.')
    if not is_clean and opts.include_all:
        if untracked_files:
            msger.info('the following untracked files would be included'  \
                       ':\n   %s' % '\n   '.join(untracked_files))
        if uncommitted_files:
            msger.info('the following uncommitted changes would be included'\
                       ':\n   %s' % '\n   '.join(uncommitted_files))

def hexdigest(fhandle, block_size=4096):
    """Calculates hexdigest of file content."""
    md5obj = hashlib.new('md5')
    while True:
        data = fhandle.read(block_size)
        if not data:
            break
        md5obj.update(data)
    return md5obj.hexdigest()

