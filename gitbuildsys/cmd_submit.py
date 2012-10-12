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

"""Implementation of subcmd: submit"""

import os
import time

from gitbuildsys import msger, errors

from gbp.rpm.git import GitRepositoryError, RpmGitRepository


def main(args):
    """gbs submit entry point."""

    workdir = args.gitdir

    if not args.msg:
        msger.error("argument for -m option can't be empty")

    try:
        repo = RpmGitRepository(workdir)
        commit = repo.rev_parse(args.commit)
        if args.target:
            target_branch = args.target
        else:
            target_branch = repo.get_branch()
    except GitRepositoryError, err:
        msger.error(str(err))

    if not args.target:
        try:
            upstream = repo.get_upstream_branch(target_branch)
            if upstream and upstream.startswith(args.remote):
                target_branch = os.path.basename(upstream)
            else:
                msger.warning('can\'t find upstream branch for current branch '\
                              '%s. Gbs will try to find it by name. Please '\
                              'consider to use git-branch --set-upstream to '\
                              'set upstream remote branch.' % target_branch)
        except GitRepositoryError:
            pass

    try:
        if target_branch == 'master':
            target_branch = 'trunk'
        tagname = 'submit/%s/%s' % (target_branch, time.strftime( \
                                    '%Y%m%d.%H%M%S', time.gmtime()))
        msger.info('creating tag: %s' % tagname)
        repo.create_tag(tagname, msg=args.msg, commit=commit, sign=args.sign,
                                                 keyid=args.user_key)
    except GitRepositoryError, err:
        msger.error('failed to create tag %s: %s ' % (tagname, str(err)))

    try:
        msger.info('pushing tag to remote server')
        repo.push_tag(args.remote, tagname)
    except GitRepositoryError, err:
        repo.delete_tag(tagname)
        msger.error('failed to push tag %s :%s' % (tagname, str(err)))

    msger.info('done.')
