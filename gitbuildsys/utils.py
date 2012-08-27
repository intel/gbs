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
import signal
from collections import defaultdict

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


class URLGrabber(object):
    '''grab an url and save to local file'''

    def __init__(self, connect_timeout=30):
        '''create Curl object and set one-time options'''
        curl = pycurl.Curl()
        curl.setopt(pycurl.FAILONERROR, True)
        curl.setopt(pycurl.FOLLOWLOCATION, True)
        curl.setopt(pycurl.SSL_VERIFYPEER, False)
        curl.setopt(pycurl.SSL_VERIFYHOST, False)
        curl.setopt(pycurl.CONNECTTIMEOUT, connect_timeout)
        #curl.setopt(pycurl.VERBOSE, 1)
        self.curl = curl

    def change_url(self, url, outfile, user, passwd):
        '''change options for individual url'''

        curl = self.curl
        curl.url = url
        curl.setopt(pycurl.URL, url)
        curl.setopt(pycurl.WRITEDATA, outfile)
        if user:
            userpwd = user
            if passwd:
                userpwd = '%s:%s' % (user, passwd)
            curl.setopt(pycurl.USERPWD, userpwd)

    def perform(self):
        '''do the real Curl perform work'''

        curl = self.curl

        stop = [False]
        def progressing(*_args):
            '''Returning a non-zero value from this callback will cause libcurl
            to abort the transfer and return CURLE_ABORTED_BY_CALLBACK.'''
            return -1 if stop[0] else 0

        def handler(_signum, _frame):
            '''set stop flag if catch SIGINT,
            if not catch SIGINT, pycurl will print traceback'''
            stop[0] = True

        curl.setopt(pycurl.PROGRESSFUNCTION, progressing)
        curl.setopt(pycurl.NOPROGRESS, False)
        original_handler = signal.signal(signal.SIGINT, handler)

        try:
            curl.perform()
        except pycurl.error, err:
            errcode = err.args[0]
            if errcode == pycurl.E_OPERATION_TIMEOUTED:
                raise errors.UrlError('timeout on %s: %s' % (curl.url, err))
            elif errcode == pycurl.E_FILESIZE_EXCEEDED:
                raise errors.UrlError('max download size exceeded on %s'\
                                           % curl.url)
            elif errcode == pycurl.E_ABORTED_BY_CALLBACK:
                # callback aborted means SIGINT had been received, raising
                # KeyboardInterrupt can stop all downloads
                raise KeyboardInterrupt(err)
            else:
                errmsg = 'pycurl error %s - "%s"' % (errcode, str(err.args[1]))
                raise errors.UrlError(errmsg)
        finally:
            signal.signal(signal.SIGINT, original_handler)

    def __del__(self):
        '''close Curl object'''
        self.curl.close()
        self.curl = None

    def grab(self, url, filename, user=None, passwd=None):
        '''grab url to filename'''

        with open(filename, 'w') as outfile:
            self.change_url(url, outfile, user, passwd)
            self.perform()


class RepoParser(object):
    """ Repository parser for generate real repourl and build config
    """

    def __init__(self, repos, cachedir):
        self.cachedir = cachedir
        self.repourls  = defaultdict(list)
        self.buildconf = None
        self.standardrepos = []
        self.urlgrabber = URLGrabber()

        self.localrepos, remotes = self.split_out_local_repo(repos)
        self.parse(remotes)

    @staticmethod
    def get_buildconf(buildmeta):
        '''parse build.xml and get build.conf fname it contains'''

        etree = ET.parse(buildmeta)
        buildelem = etree.getroot().find('buildconf')
        if buildelem is None:
            return None
        return buildelem.text.strip()

    def build_repos_from_buildmeta(self, baseurl, buildmeta):
        '''parse build.xml and pickup standard repos it contains'''

        if not (buildmeta and os.path.exists(buildmeta)):
            return

        etree = ET.parse(buildmeta)
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
            for repo in repos:
                repourl = os.path.join(baseurl, 'repos', repo, arch, 'packages')
                if self.is_standard_repo(repourl):
                    self.repourls[arch].append(repourl)

    def fetch(self, url):
        '''return file name if fetch url success, else None'''
        fname = os.path.join(self.cachedir, os.path.basename(url))

        try:
            self.urlgrabber.grab(url, fname)
        except errors.UrlError:
            return

        return fname

    def is_standard_repo(self, repo):
        '''Check if repo is standard repo with repodata/repomd.xml exist'''

        repomd_url = os.path.join(repo, 'repodata/repomd.xml')
        return not not self.fetch(repomd_url)

    def parse(self, remotes):
        '''parse each remote repo, try to fetch build.xml and build.conf'''

        for repo in remotes:
            if self.is_standard_repo(repo):
                self.standardrepos.append(repo)

                if self.buildconf:
                    continue

                buildxml_url = urlparse.urljoin(repo.rstrip('/') + '/',
                    '../../../../builddata/build.xml')
                buildmeta = self.fetch(buildxml_url)
                if not buildmeta:
                    continue

                build_conf = self.get_buildconf(buildmeta)
                buildconf_url = buildxml_url.replace(os.path.basename    \
                                                (buildxml_url), build_conf)
                fname = self.fetch(buildconf_url)
                if fname:
                    self.buildconf = fname
                continue

            # Check if it's repo with builddata/build.xml exist
            buildxml_url = os.path.join(repo, 'builddata/build.xml')
            buildmeta = self.fetch(buildxml_url)
            if not buildmeta:
                continue

            # Generate repos from build.xml
            self.build_repos_from_buildmeta(repo, buildmeta)

            if self.buildconf:
                continue

            build_conf = self.get_buildconf(buildmeta)
            buildconf_url = urlparse.urljoin(repo.rstrip('/') + '/', \
                'builddata/%s' % build_conf)

            fname = self.fetch(buildconf_url)
            if fname:
                self.buildconf = fname

    @staticmethod
    def split_out_local_repo(repos):
        '''divide repos into two parts, local and remote'''
        local_repos = []
        remotes = []

        for repo in repos:
            if repo.startswith('/') and os.path.exists(repo):
                local_repos.append(repo)
            else:
                remotes.append(repo)

        return local_repos, remotes

    def get_repos_by_arch(self, arch):
        '''get repos by arch'''

        repos = self.localrepos + self.standardrepos # local repos first

        if arch in ['ia32', 'i686', 'i586']:
            arch = 'ia32'
        if self.repourls and arch in self.repourls:
            repos.extend(self.repourls[arch])

        return repos


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

