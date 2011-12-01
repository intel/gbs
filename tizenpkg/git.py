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

import runner

__all__ = ['config', 'branch', 'status', 'ls_files']

def config(*args):
    return runner.outs(['git', 'config'] + list(args))

def branch(all=False, current=False, *args):
    cmdln = ['git', 'branch']
    if all:
        cmdln.append('-a')
    cmdln += list(args)

    branches = runner.outs(cmdln).splitlines()

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
    outs = runner.outs(['git', 'status', '-s'] + list(args))

    sts = {}
    for line in outs.splitlines():
        st = line[:2]
        if st not in sts:
            sts[st] = [line[2:].strip()]
        else:
            sts[st].append(line[2:].strip())

    return sts

def ls_files():
    return runner.outs('git ls-files').splitlines()
