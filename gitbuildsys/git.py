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

import runner
import errors

__all__ = ['config', 'branch', 'status', 'ls_files']

def _run_git(cmd, args=[]):
    if not os.path.isdir('.git'):
        raise errors.GitInvalid(os.getcwd())

    return runner.outs(['git', cmd] + args)

def config(*args):
    return _run_git('config', list(args))

def branch(all=False, current=False, *args):
    args = list(args)
    if all:
        args.insert(0, '-a')

    branches = _run_git('branch', args).splitlines()

    curbr = ''
    for br in branches:
        if br.startswith('* '):
            curbr = br[2:].strip()
            br = curbr

    if current:
        return [curbr]
    else:
        if '(no branch)' in branches:
            branches.remove('(no branch)')
        return branches

def status(*args):
    outs = _run_git('status', ['-s'] + list(args))

    sts = {}
    for line in outs.splitlines():
        st = line[:2]
        if st not in sts:
            sts[st] = [line[2:].strip()]
        else:
            sts[st].append(line[2:].strip())

    return sts

def ls_files():
    return _run_git('ls-files').splitlines()

