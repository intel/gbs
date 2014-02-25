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

"""Helpers, convenience utils, common APIs."""

import os
import re
import gzip
import glob
import tempfile
import shutil
import pycurl
import hashlib
import fnmatch
import signal
import subprocess
import argparse
import xml.etree.ElementTree as ET
from collections import defaultdict

from gitbuildsys.errors import UrlError, GbsError
from gitbuildsys.log import LOGGER as log

from gbp.rpm.git import RpmGitRepository, GitRepositoryError
from gbp.errors import GbpError


class Workdir(object):
    """
    Context manager, which makes it easy to enter some directory
    do something and return back.
    Usage example:
        with utils.Workdir(workdir):
            # do something here
        # here you're again in the same dir as before
    """
    def __init__(self, path):
        self._newdir = path
        self._cwd = os.getcwd()

    def __enter__(self):
        os.chdir(self._newdir)

    def __exit__(self, _type, _value, _tb):
        os.chdir(self._cwd)

def guess_spec(git_path, packaging_dir, given_spec, commit_id='WC.UNTRACKED'):
    """Guess spec file from project name if not given."""
    git_path = os.path.abspath(git_path)

    if commit_id == 'WC.UNTRACKED':
        check = lambda fname, dir_only = False: os.path.exists(os.path.join(
                       git_path, fname))
        glob_ = lambda pattern: [ name.replace(git_path+'/', '')
            for name in reversed(glob.glob(os.path.join(git_path, pattern))) ]
        msg = 'No such spec file %s'
    else:
        check = lambda fname, dir_only = False : file_exists_in_rev(git_path,
                       fname, commit_id, dir_only=dir_only)
        glob_ = lambda pattern: glob_in_rev(git_path, pattern, commit_id)
        msg = "No such spec file %%s in %s" % commit_id

    spec = None
    if given_spec:
        spec = os.path.join(packaging_dir, given_spec)
        if not check(spec):
            raise GbsError(msg % spec)

    specs = glob_(os.path.join(packaging_dir, '*.spec'))
    if not specs:
        raise GbsError("can't find any spec file under packaging dir: "
                       "%s" % packaging_dir)

    project_name =  os.path.basename(git_path)
    if not spec:
        spec = os.path.join(packaging_dir, '%s.spec' % project_name)
        spec = spec if spec in specs else specs[0]
    specs.remove(spec)
    return [spec, specs]


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
        except OSError, err:
            raise GbsError("Failed to create dir or file on %s: %s" % \
                          (target_dir, str(err)))
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
       original. Creates empty temporary file if original doesn't exist.
       Deletes temporary file when object is destroyed.
    """

    def __init__(self, content=None):
        tmpffd, self.name = tempfile.mkstemp()
        os.close(tmpffd)

        if content:
            with open(self.name, 'w') as fobj:
                fobj.write(content)

        self.stat = os.stat(self.name)

    def is_changed(self):
        """Check if temporary file has been changed."""
        return os.stat(self.name) != self.stat

    def __del__(self):
        if os.path.exists(self.name):
            os.unlink(self.name)


class PageNotFound(Exception):
    """Custom exception to handle HTTP 404 error."""

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

    def change_url(self, url, outfile, user, passwd, no_cache=False):
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
        httpheader = []
        if no_cache:
            httpheader.append('Pragma: no-cache')
            httpheader.append('Cache-Control: no-cache')
            log.debug("disable HTTP caching")
        curl.setopt(pycurl.HTTPHEADER, httpheader)

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
            log.debug('fetching error:%s' % str(err))

            errcode, errmsg = err.args
            http_code = curl.getinfo(pycurl.HTTP_CODE)

            if errcode == pycurl.E_OPERATION_TIMEOUTED or http_code == 503:
                proxies = ['Detected proxies set in system environment:']
                ENV = os.environ
                for key in ['HTTPS_PROXY', 'HTTP_PROXY', 'FTP_PROXY',
                            'https_proxy', 'http_proxy', 'ftp_proxy',
                            'NO_PROXY', 'no_proxy']:
                    proxies.append('%s=%s' % (key, ENV.get(key, '')))
                raise UrlError("connect timeout to %s, maybe it's caused by "
                               "proxy settings, please check. %s" % (curl.url,
                               '\n  '.join(proxies)))
            elif errcode == pycurl.E_ABORTED_BY_CALLBACK:
                raise KeyboardInterrupt(err)
            elif http_code in (401, 403):
                raise UrlError('authenticate failed on: %s' % curl.url)
            elif http_code == 404:
                raise PageNotFound(err)
            else:
                raise UrlError('URL error on %s: (%s: "%s")' %
                               (curl.url, errcode, errmsg))
        finally:
            signal.signal(signal.SIGINT, original_handler)

    def __del__(self):
        """Close curl object."""
        self.curl.close()
        self.curl = None

    def grab(self, url, filename, user=None, passwd=None, no_cache=False):
        """Grab url to file."""

        log.debug("fetching %s => %s" % (url, filename))

        with open(filename, 'w') as outfile:
            self.change_url(url, outfile, user, passwd, no_cache)
            self.perform()


class RepoParser(object):
    """Repository parser for generate real repourl and build config."""

    def __init__(self, repos, cachedir):
        self.cachedir = cachedir
        self.repourls  = defaultdict(list)
        self.buildconf = None
        self.standardrepos = []
        self.urlgrabber = URLGrabber()

        self.localrepos, remotes = self.split_out_local_repo(repos)
        self.parse(remotes)

    @staticmethod
    def _parse_build_xml(build_xml):
        """
        Parse build.xml.
        Returns: dictionary with buildconf, repos and archs.
        """
        if not (build_xml and os.path.exists(build_xml)):
            return

        try:
            etree = ET.parse(build_xml)
        except ET.ParseError:
            log.warning('Not well formed xml: %s' % build_xml)
            return

        meta = {}
        root = etree.getroot()

        # Get version of build.xml
        build_version = root.get('version')
        # It's new format of repo structure if 'version' exists
        if build_version:
            log.warning('new format repo structure has not been supportted '
                        'well, please upgrade your gbs to latest version')
            return None

        buildelem = root.find('buildconf')
        # Must using None here, "if buildelem" is wrong
        # None means item does not exist
        # It's different from bool(buildelem)
        if buildelem is not None:
            meta['buildconf'] = buildelem.text.strip()

        repo_items = root.find('repos')
        if repo_items is not None:
            meta['repos'] = [ repo.text.strip()
                             for repo in repo_items.findall('repo') ]

        arch_items = root.find('archs')
        if arch_items is not None:
            meta['archs'] = [ arch.text.strip()
                             for arch in arch_items.findall('arch') ]
        id_item = root.find('id')
        if id_item is not None:
            meta['id'] = id_item.text.strip()

        return meta

    def build_repos_from_buildmeta(self, baseurl, meta):
        """Parse build.xml and pickup standard repos it contains."""
        archs = meta.get('archs', [])
        repos = meta.get('repos', [])

        for arch in archs:
            for repo in repos:
                repourl = baseurl.pathjoin('repos/%s/%s/packages' % (repo,
                                                                     arch))
                if self.is_standard_repo(repourl):
                    self.repourls[arch].append(repourl)

    def fetch(self, url, no_cache=False):
        """
        Fetch url.
        Returns: file name if fetch succeds, else None.
        """
        fname = os.path.join(self.cachedir, os.path.basename(url))

        try:
            self.urlgrabber.grab(url, fname, url.user, url.passwd, no_cache)
        except PageNotFound:
            return

        return fname

    def is_standard_repo(self, repo):
        """Check if repo is standard repo with repodata/repomd.xml exist."""

        repomd_url = repo.pathjoin('repodata/repomd.xml')
        return not not self.fetch(repomd_url, no_cache=True)

    def _fetch_build_meta(self, latest_repo_url):
        """Fetch and parse build.xml."""
        buildxml_url = latest_repo_url.pathjoin('builddata/build.xml')
        build_xml = self.fetch(buildxml_url)
        if build_xml:
            return self._parse_build_xml(build_xml)

    def _fetch_build_conf(self, latest_repo_url, meta):
        """Get build.conf file name from build.xml and fetch it."""
        if self.buildconf:
            return

        if not meta or \
            'buildconf' not in meta or \
            not meta['buildconf']:
            log.warning("No build.conf in build.xml "
                          "of repo: %s" % latest_repo_url)
            return

        buildconf_url = latest_repo_url.pathjoin('builddata/%s' %
                                                 meta['buildconf'])
        fname = self.fetch(buildconf_url)
        if fname:
            release, _buildid = meta['id'].split('_')
            release = release.replace('-','')
            target_conf = os.path.join(os.path.dirname(fname),
                                       '%s.conf' % release)
            os.rename(fname, target_conf)
            self.buildconf = target_conf

    def _fetch_build_conf_new(self, baseurl):
        """ fetch build conf from standard repo"""
        repomd_url = baseurl.pathjoin('repodata/repomd.xml')
        repomd_file = self.fetch(repomd_url)
        if not repomd_file:
            return

        try:
            etree = ET.parse(repomd_file)
        except ET.ParseError:
            log.warning('Not well formed xml: %s' % repomd_file)
            return
        root = etree.getroot()

        # get namespace of repomd element
        xmlns = re.sub('repomd$', '', root.tag)
        location_elem = None
        for elem in root.findall('%sdata' % xmlns):
            if elem.attrib['type'] == 'build':
                location_elem = elem.find('%slocation' % xmlns)
                break
        if location_elem is not None and 'href' in location_elem.attrib:
            buildconf_url = baseurl.pathjoin(location_elem.attrib['href'])
            fname = self.fetch(buildconf_url)
            if fname:
                if fname[-3:] == '.gz':
                    fh_gz = gzip.open(fname, 'r')
                else:
                    fh_gz = open(fname, 'r')
                buildconf_file = os.path.join(os.path.dirname(fname),
                                              'build.conf')
                buildconf_fh = open(buildconf_file, 'w')
                buildconf_fh.write(fh_gz.read())
                fh_gz.close()
                buildconf_fh.close()
                self.buildconf = buildconf_file

    def parse(self, remotes):
        """Parse each remote repo, try to fetch build.xml and build.conf"""
        def deal_with_one_repo(repo):
            """Deal with one repo url."""
            if self.is_standard_repo(repo):
                self.standardrepos.append(repo)
                self._fetch_build_conf_new(repo)
                if self.buildconf:
                    return

                latest_repo_url = repo.pathjoin('../../../../')
                if latest_repo_url.find('../') >= 0:
                    return
                meta = self._fetch_build_meta(latest_repo_url)
                if meta:
                    self._fetch_build_conf(latest_repo_url, meta)
                return

            # Check if it's repo with builddata/build.xml exist
            meta = self._fetch_build_meta(repo)
            if meta:
                # Generate repos from build.xml
                self.build_repos_from_buildmeta(repo, meta)
                self._fetch_build_conf(repo, meta)
            else:
                # Check if it's repo with build.xml exist
                buildxml_url = repo.pathjoin('build.xml')
                if self.fetch(buildxml_url):
                    raise GbsError('Maybe you are using new designed repo, '\
                                   'and please specify real RPM repo with '\
                                   'repodata under it.')

        for repo in remotes:
            deal_with_one_repo(repo)

    @staticmethod
    def split_out_local_repo(repos):
        """Divide repos to local and remote parts."""
        local_repos = []
        remotes = []

        for repo in repos:
            if repo.is_local():
                if os.path.exists(repo):
                    local_repos.append(repo)
                else:
                    log.warning('No such repo path:%s' % repo)
            else:
                remotes.append(repo)

        return local_repos, remotes

    def get_repos_by_arch(self, arch):
        """Get repos by arch."""
        repos = self.localrepos + self.standardrepos # local repos first

        if arch in ['ia32', 'i686', 'i586']:
            arch = 'ia32'
        if self.repourls and arch in self.repourls:
            repos.extend(self.repourls[arch])

        def filter_valid_repo(repos):
            'filter valid remote and local repo'
            rets = []
            for url in repos:
                if not url.startswith('http://') and \
                    not url.startswith('https://') and \
                    not (url.startswith('/') and os.path.exists(url)):
                    log.warning('ignore invalid repo url: %s' % url)
                else:
                    rets.append(url)
            return rets

        return filter_valid_repo(repos)


def read_localconf(workdir):
    """Read local configuration file from project directory."""
    from gitbuildsys.conf import configmgr
    prj_conf = os.path.join(workdir, '.gbs.conf')
    if os.path.exists(prj_conf) and workdir != os.getcwd():
        configmgr.add_conf(prj_conf)


class SearchConfAction(argparse.Action):
    """
    Action for gitdir position argument to find project special
    gbs.conf
    """
    def __call__(self, parser, namespace, value, option_string=None):
        workdir = value
        try:
            repo = RpmGitRepository(value)
            workdir = repo.path
        except GitRepositoryError, err:
            pass

        read_localconf(workdir)
        setattr(namespace, self.dest, value)

def git_status_checker(git, opts):
    """
    Perform git repository status check.
    Warn user if repository is not clean or untracked files are found.
    """
    try:
        if opts.commit:
            git.rev_parse(opts.commit)
        is_clean = git.is_clean()[0]
        status = git.status()
    except (GbpError, GitRepositoryError), err:
        raise GbsError(str(err))

    untracked_files = status['??']
    uncommitted_files = []
    for stat in status:
        if stat == '??':
            continue
        uncommitted_files.extend(status[stat])

    if not is_clean and not opts.include_all:
        if untracked_files:
            log.warning('the following untracked files would NOT be '
                        'included:\n   %s' % '\n   '.join(untracked_files))
        if uncommitted_files:
            log.warning('the following uncommitted changes would NOT be '
                        'included:\n   %s' % '\n   '.join(uncommitted_files))
        log.warning('you can specify \'--include-all\' option to '
                    'include these uncommitted and untracked files.')
    if not is_clean and opts.include_all:
        if untracked_files:
            log.info('the following untracked files would be included'
                       ':\n   %s' % '\n   '.join(untracked_files))
        if uncommitted_files:
            log.info('the following uncommitted changes would be included'
                       ':\n   %s' % '\n   '.join(uncommitted_files))

def hexdigest(fhandle, block_size=4096):
    """Calculate hexdigest of file content."""
    md5obj = hashlib.new('md5')
    while True:
        data = fhandle.read(block_size)
        if not data:
            break
        md5obj.update(data)
    return md5obj.hexdigest()


def show_file_from_rev(git_path, relative_path, commit_id):
    """Get a single file content from given git revision."""
    args = ['git', 'show', '%s:%s' % (commit_id, relative_path)]
    try:
        with Workdir(git_path):
            return  subprocess.Popen(args,
                                     stdout=subprocess.PIPE).communicate()[0]
    except (subprocess.CalledProcessError, OSError), err:
        log.debug('failed to checkout %s from %s:%s' % (relative_path,
                                                        commit_id, str(err)))
    return None


def file_exists_in_rev(git_path, relative_path, commit_id, dir_only=False):
    """Check if file exists in given given revision."""
    git_opts = ['--name-only']
    if dir_only:
        git_opts += ['-d']
    args = ['git', 'ls-tree', commit_id, relative_path]
    args.extend(git_opts)

    try:
        with Workdir(git_path):
            output = subprocess.Popen(args,
                                      stdout=subprocess.PIPE).communicate()[0]
    except (subprocess.CalledProcessError, OSError), err:
        raise GbsError('failed to check existence of %s in %s:%s' % (
            relative_path, commit_id, str(err)))

    return output != ''


def glob_in_rev(git_path, pattern, commit_id):
    """Glob pattern in given revision."""

    path = os.path.dirname(pattern)
    args = ['git', 'ls-tree', '--name-only', commit_id, '%s/' % path]

    try:
        with Workdir(git_path):
            output = subprocess.Popen(args,
                                      stdout=subprocess.PIPE).communicate()[0]
    except (subprocess.CalledProcessError, OSError), err:
        raise GbsError('failed to glob %s in %s:%s' % (
            pattern, commit_id, str(err)))

    return fnmatch.filter(output.splitlines(), pattern)


def edit(initial_content=None):
    """
    Launch an editor to get input from user.
    Returns: content of user input.
    """
    from gitbuildsys.conf import configmgr
    editor = configmgr.get('editor') or os.getenv('EDITOR') or 'vi'

    temp = TempCopy(initial_content)
    subprocess.call('%s %s' % (editor, temp.name), shell=True)

    if temp.is_changed():
        with open(temp.name) as fobj:
            return fobj.read()
    return ''


def edit_file(target_fname, initial_content=None):
    """
    Create temporary copy of target_fname with initial_content and  launch
    an editor to edit it. Update content back if user changed it.
    Returns: True if content has been changed.
    """
    changes = edit(initial_content)
    if not changes:
        return False

    try:
        with open(target_fname, 'w') as fobj:
            fobj.write(changes)
    except IOError, err:
        raise GbsError("Can't update %s: %s" % (target_fname, str(err)))
    return True
