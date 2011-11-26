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
import re

# internal modules
import runner
import errors
import msger
from utils import Workdir, strip_end

class Git:
    def __init__(self, path):
        if not os.path.isdir(os.path.join(path, '.git')):
            raise errors.GitInvalid(path)

        self.path = os.path.abspath(path)
        self._git_dir = os.path.join(path, '.git')

        # as cache
        self.cur_branch = None
        self.branches = None

    def _is_sha1(self, val):
        sha1_re = re.compile(r'[0-9a-f]{40}$')
        return True if sha1_re.match(val) else False

    def _exec_git(self, command, args=[]):
        """Exec a git command and return the output
        """

        cmd = ['git', command] + args

        cmdln = ' '.join(cmd)
        msger.debug('run command: %s' % cmdln)

        with Workdir(self.path):
            ret, out = runner.runtool(cmd)

        if ret:
            raise errors.GitError("command error for: %s" % cmdln)

        return out

    def status(self, *args):
        outs = self._exec_git('status', ['-s'] + list(args))

        sts = {}
        for line in outs.splitlines():
            st = line[:2]
            if st not in sts:
                sts[st] = [line[2:].strip()]
            else:
                sts[st].append(line[2:].strip())

        return sts

    def ls_files(self):
        """Return the files list
        """
        return filter(None, self._exec_git('ls-files').splitlines())

    def rev_parse(self, name):
        """ Find the SHA1 of a given name commit id"""
        options = [ "--quiet", "--verify", name ]
        cmd = ['git', 'rev-parse']
        ret, commit = runner.runtool(' '.join(cmd + options))
        if ret == 0:
            return commit.strip()
        else:
            return None

    def create_branch(self, branch, rev=None):
        if rev and not self._is_sha1(rev):
            rev = self.rev_parse(rev)
        if not branch:
            raise errors.GitError('Branch name should not be None')

        options = [branch, rev, '-f']
        self._exec_git('branch', options)

    def _get_branches(self):
        """Return the branches list, current working branch is the first
        element.
        """
        branches = []
        for line in self._exec_git('branch', ['--no-color']).splitlines():
            br = line.strip().split()[-1]

            if line.startswith('*'):
                current_branch = br

            branches.append(br)

        return (current_branch, branches)

    def get_branches(self):
        if not self.cur_branch or not self.branches:
            self.cur_branch, self.branches = \
                self._get_branches()

        return (self.cur_branch, self.branches)

    def is_clean(self):
        """does the repository contain any uncommitted modifications"""

        gitsts = self.status()
        if 'M ' in gitsts or ' M' in gitsts or \
           'A ' in gitsts or ' A ' in gitsts:
            return False
        else:
            return True

    def has_branch(self, br, remote=False):
        """Check if the repository has branch 'br'
          @param remote: only liste remote branches
        """

        if remote:
            options = [ '--no-color', '-r' ]

            for line in self._exec_git('branch', options).splitlines():
                rbr = line.strip().split()[-1]
                if br == rbr:
                    return True

            return False

        else:
            return (br in self.get_branches()[1])

    def checkout_branch(self, br):
        """checkout repository branch 'br'
        """
        options = [br]
        with Workdir(self.path):
            self._exec_git('checkout', options)

    def clean_branch(self, br):
        """Clean up repository branch 'br'
        """

        options = ['-dfx']
        with Workdir(self.path):
            self.checkout_branch(br)
            runner.quiet('rm .git/index')
            self._exec_git('clean', options)

    def commit_dir(self, unpack_dir, msg, branch = 'master', other_parents=None,
                   author={}, committer={}, create_missing_branch=False):

        for key, val in author.items():
            if val:
                os.environ['GIT_AUTHOR_%s' % key.upper()] = val
        for key, val in committer.items():
            if val:
                os.environ['GIT_COMMITTER_%s' % key.upper()] = val

        os.environ['GIT_WORK_TREE'] = unpack_dir
        options = ['.', '-f']
        self._exec_git("add", options)

        if self.is_clean():
            return None

        options = ['--quiet','-a', '-m %s' % msg,]
        self._exec_git("commit", options)

        commit_id = self._exec_git('log', ['--oneline', '-1']).split()[0]

        del os.environ['GIT_WORK_TREE']
        for key, val in author.items():
            if val:
                del os.environ['GIT_AUTHOR_%s' % key.upper()]
        for key, val in committer.items():
            if val:
                del os.environ['GIT_COMMITTER_%s' % key.upper()]

        self._exec_git('reset', ['--hard', commit_id])

        return commit_id

    def find_tag(self, tag):
        """find the specify version from the repository"""
        args = ['-l', tag]
        ret = self._exec_git('tag', args)
        if ret:
            return True
        return False

    def create_tag(self, name, msg, commit):
        """Creat a tag with name at commit""" 
        if self.rev_parse(commit) is None:
            raise errors.GitError('%s is invalid commit ID' % commit)
        options = [name, '-m %s' % msg, commit]
        self._exec_git('tag', options)

    def merge(self, commit):
        """ merge the git tree specified by commit to current branch"""
        if self.rev_parse(commit) is None or not self.find_tag(commit):
            raise errors.GitError('%s is invalid commit ID or tag' % commit)

        options = [commit]
        self._exec_git('merge', options)

    def archive(self, prefix, tarfname, treeish='HEAD'):
        """Archive git tree from 'treeish', detect archive type
        from the extname of output filename.

          @prefix: tarball topdir
          @tarfname: output tarball name
          @treeish: commit ID archive from
        """

        filetypes = {
                '.tar.gz': ('tar', 'gz'),
                '.tgz': ('tar', 'gz'),
                '.tar.bz2': ('tar', 'bz2'),
                '.tbz2': ('tar', 'bz2'),
                '.zip': ('zip', ''),
        }

        zipcmds = {
                'gz': 'gzip',
                'bz2': 'bzip2 -f',
        }

        for extname in filetypes:
           if tarfname.endswith(extname):
               fmt, compress = filetypes[extname]

               barename = strip_end(tarfname, extname)
               tarname = '%s.%s' % (barename, fmt)

               if compress:
                   zipcmd = zipcmds[compress]
                   finalname = '%s.%s' % (tarname, compress)
               else:
                   zipcmd = None
                   finalname = tarname

               break

        else:
            raise errors.GitError("Cannot detect archive type from filename, "\
                                  "supported ext-names: %s" \
                                  % ', '.join(filetypes.keys()))

        options = [ treeish,
                    '--format=%s' % fmt,
                    '--output=%s' % tarname,
                    '--prefix=%s' % prefix
                  ]
        with Workdir(self.path):
            self._exec_git('archive', options)
            if zipcmd:
                runner.quiet('%s %s' % (zipcmd, tarname))

            if finalname != tarfname:
                os.rename(finalname, tarfname)

    @staticmethod
    def _formatlize(version):
        return version.replace('~', '_').replace(':', '%')

    @staticmethod
    def version_to_tag(format, version):
        return format % dict(version=Git._formatlize(version))

    @classmethod
    def create(klass, path, description=None, bare=False):
        """
        Create a repository at path
        @path: where to create the repository
        """
        abspath = os.path.abspath(path)
        options = []
        if bare:
            options = [ '--bare' ]
            git_dir = ''
        else:
            options = []
            git_dir = '.git'

        try:
            if not os.path.exists(abspath):
                os.makedirs(abspath)

            with Workdir(abspath):
                cmd = ['git', 'init'] + options;
                runner.quiet(' '.join(cmd))
            if description:
                with file(os.path.join(abspath, git_dir, "description"), 'w') as f:
                    description += '\n' if description[-1] != '\n' else ''
                    f.write(description)
            return klass(abspath)
        except OSError, err:
            raise errors.GitError("Cannot create Git repository at '%s': %s"
                                     % (abspath, err[1]))
        return None
