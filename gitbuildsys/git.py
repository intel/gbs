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
import subprocess
import signal
import runner
import errors
import msger as log


class Command(object):
    """
    Wraps a shell command, so we don't have to store any kind of command line options in 
    one of the git-buildpackage commands
    """
    def __init__(self, cmd, args=[], shell=False, extra_env=None):
        self.cmd = cmd
        self.args = args
        self.run_error = "Couldn't run '%s'" % (" ".join([self.cmd] + self.args))
        self.shell = shell
        self.retcode = 1
        if extra_env is not None:
            self.env = os.environ.copy()
            self.env.update(extra_env)
        else:
            self.env = None
        print cmd, args
    def __call(self, args):
        """wraps subprocess.call so we can be verbose and fix python's SIGPIPE handling"""
        def default_sigpipe():
            "restore default signal handler (http://bugs.python.org/issue1652)"
            signal.signal(signal.SIGPIPE, signal.SIG_DFL)

        log.debug("%s %s %s" % (self.cmd, self.args, args))
        cmd = [ self.cmd ] + self.args + args
        if self.shell: # subprocess.call only cares about the first argument if shell=True
            cmd = " ".join(cmd)
        return subprocess.call(cmd, shell=self.shell, env=self.env, preexec_fn=default_sigpipe)

    def __run(self, args):
        """
        run self.cmd adding args as additional arguments

        Be verbose about errors and encode them in the return value, don't pass
        on exceptions.
        """
        try:
            retcode = self.__call(args)
            if retcode < 0:
                log.err("%s was terminated by signal %d" % (self.cmd,  -retcode))
            elif retcode > 0:
                log.err("%s returned %d" % (self.cmd,  retcode))
        except OSError, e:
            log.err("Execution failed: " + e.__str__())
            retcode = 1
        if retcode:
            log.err(self.run_error)
        self.retcode = retcode
        return retcode

    def __call__(self, args=[]):
        """Run the command, convert all errors into CommandExecFailed, assumes
        that the lower levels printed an error message - only useful if you
        only expect 0 as result
        >>> Command("/bin/true")(["foo", "bar"])
        >>> Command("/foo/bar")()
        Traceback (most recent call last):
        ...
        CommandExecFailed
        """
        if self.__run(args):
            raise CommandExecFailed

    def call(self, args):
        """like __call__ but don't use stderr and let the caller handle the return status
        >>> Command("/bin/true").call(["foo", "bar"])
        0
        >>> Command("/foo/bar").call(["foo", "bar"]) # doctest:+ELLIPSIS
        Traceback (most recent call last):
        ...
        CommandExecFailed: Execution failed: ...
        """
        try:
            ret = self.__call(args)
        except OSError, e:
            raise CommandExecFailed, "Execution failed: %s" % e
        return ret

class GitCommand(Command):
    "Mother/Father of all git commands"
    def __init__(self, cmd, args=[], **kwargs):
        Command.__init__(self, 'git', [cmd] + args, **kwargs)
        self.run_error = "Couldn't run git %s" % cmd

class GitError(Exception):
    """Exception thrown by Git"""
    keyword = ''

    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return self.keyword + str(self.msg)

class Git:
    def __init__(self, path):
        try:
            os.stat(os.path.join(path,'.git'))
        except:
            raise GitError, "Path %s is not a valid git repositroy." %(path)
        self.path = os.path.abspath(path)
        os.chdir(self.path)

    def __check_path(self):
        if os.getcwd() != self.path:
            raise GitRepositoryError

    def __build_env(self, extra_env):
        """Prepare environment for subprocess calls"""
        env = None
        if extra_env is not None:
            env = os.environ.copy()
            env.update(extra_env)
        return env

    def __git_getoutput(self, command, args=[], extra_env=None, cwd=None):
        """exec a git command and return the output"""
        output = []

        env = self.__build_env(extra_env)
        cmd = ['git', command] + args
        log.debug(cmd)
        popen = subprocess.Popen(cmd, stdout=subprocess.PIPE, env=env, cwd=cwd)
        while popen.poll() == None:
            output += popen.stdout.readlines()
        ret = popen.poll()
        output += popen.stdout.readlines()
        return output, ret

    def __git_inout(self, command, args, input, extra_env=None):
        """Send input and return output (stdout)"""
        env = self.__build_env(extra_env)
        cmd = ['git', command] + args
        log.debug(cmd)
        popen = subprocess.Popen(cmd,
                                 stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE,
                                 env=env)
        (stdout, stderr) = popen.communicate(input)
        return stdout, stderr, popen.returncode

        
    def status(self):
        print self.__git_getoutput('status')

    def get_files(self):
        """return the files list"""
        out, ret = self.__git_getoutput('ls-files', ['-z'])
        if ret:
            raise GitRepositoryError, "Error listing files %d" % ret
        if out:
            return [ file for file in out[0].split('\0') if file ]
        else:
            return []

    def get_branches(self):
        """
        return the branches list, current working
        branch is the first element
        """
        self.__check_path()
        branches = []
        for line in self.__git_getoutput('branch', [ '--no-color' ])[0]:
            if line.startswith('*'):
                current_branch=line.split(' ', 1)[1].strip()
            else:
                branches.append(line.strip())

        return [current_branch] + branches

    def is_clean(self):
        """does the repository contain any uncommitted modifications"""
        self.__check_path()
        clean_msg = 'nothing to commit'
        out = self.__git_getoutput('status')[0]
        ret = False
        for line in out:
            if line.startswith('#'):
                continue
            if line.startswith(clean_msg):
                    ret = True
            break
        return (ret, "".join(out))

    def has_branch(self, branch, remote=False):
        """
        check if the repository has branch 'branch'
        @param remote: only liste remote branches
        """
        self.__check_path()
        options = [ '--no-color' ]
        if remote:
            options += [ '-r' ]

        for line in self.__git_getoutput('branch', options)[0]:
            if line.split(' ', 1)[1].strip() == branch:
                return True
        return False
        
        #
#__all__ = ['config', 'branch', 'status', 'ls_files']
#
#def _run_git(cmd, args=[]):
#    if not os.path.isdir('.git'):
#        raise errors.GitInvalid(os.getcwd())
#
#    return runner.outs(['git', cmd] + args)
#
#def config(*args):
#    return _run_git('config', list(args))
#
#def branch(all=False, current=False, *args):
#    args = list(args)
#    if all:
#        args.insert(0, '-a')
#
#    branches = _run_git('branch', args).splitlines()
#
#    curbr = ''
#    for br in branches:
#        if br.startswith('* '):
#            curbr = br[2:].strip()
#            br = curbr
#
#    if current:
#        return [curbr]
#    else:
#        if '(no branch)' in branches:
#            branches.remove('(no branch)')
#        return branches
#
#def status(*args):
#    outs = _run_git('status', ['-s'] + list(args))
#
#    sts = {}
#    for line in outs.splitlines():
#        st = line[:2]
#        if st not in sts:
#            sts[st] = [line[2:].strip()]
#        else:
#            sts[st].append(line[2:].strip())
#
#    return sts
#
#def ls_files():
#    return _run_git('ls-files').splitlines()
#
