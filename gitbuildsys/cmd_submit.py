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

"""Implementation of subcmd: submit
"""

import os
import time
from collections import namedtuple
from gitbuildsys.cmd_changelog import do as gbs_changelog

import gbp.rpm as rpm
from gbp.rpm.git import GitRepositoryError, RpmGitRepository
import msger
import utils

def do(opts, args):

    workdir = os.path.abspath(os.getcwd())
    if len(args) > 1:
        msger.error('only one work directory can be specified in args.')
    if len(args) == 1:
        workdir = os.path.abspath(args[0])

    specfile = utils.guess_spec(workdir, None)
    try:
        spec = rpm.parse_spec(specfile)
    except GbpError, err:
         msger.error('%s' % err)

    if not spec.name or not spec.version:
        msger.error('can\'t get correct name or version from spec file.')

    try:
        repo = RpmGitRepository(workdir)
    except GitRepositoryError:
        msger.error('%s is not a git dir' % workdir)

    # Create log info from commits
    if opts.changelog:
        try:
            gbs_changelog(namedtuple('Opts', 'since')(None), None)
        except SystemExit:
            msger.error("Failed to update changelog")

    changesfile = os.path.join(workdir, 'packaging', '%s.changes' % spec.name)
    if not os.path.exists(changesfile):
        msger.info('No changelog file, so not be allowed to submit')

    file_list = []
    try:
        file_list = repo.list_files(types=['modified'])
    except GitRepositoryError, err:
        msger.error('failed to list package files using git ls-files: %s' % err)

    chlogfile = changesfile.replace('%s/' % workdir, '')
    if chlogfile not in file_list:
        # changelog file has not been modified, then
        # Check if the latest commit contains changelog file's update
        try:
            commit_info = repo.get_commit_info('HEAD')
            changed_files = commit_info['files']
            if not ('M' in changed_files and chlogfile in changed_files['M'] or \
                    'A' in changed_files and chlogfile in changed_files['A']):
                msger.error('changelog file must be updated, use --changelog '\
                            'opts or update manually')
        except GitRepositoryError, err:
            msger.error('failed to get latest commit info: %s' % err)
    else:
        # Changelog file have been modified, so commit at local first
        try:
            if not opts.msg:
                msger.error('commit message must be specified using -m')
            repo.add_files([changesfile])
            repo.commit_files([changesfile], opts.msg)
        except GitRepositoryError:
            msger.error('git commit changelog error, please check manually '\
                        'maybe not changed or not exist')

    try:
        repo.push('origin', 'HEAD', 'refs/for/%s' % opts.target_branch)
        tagmsg = ''
        if opts.tag:
            tagmsg = 'build/%s' % time.strftime('%Y%m%d.%H%M%S', time.gmtime())
            repo.create_tag(tagmsg)
            repo.push_tag('origin',tagmsg)
    except GitRepositoryError:
        msger.error('failed to submit local changes to server')

    msger.info('done.')
