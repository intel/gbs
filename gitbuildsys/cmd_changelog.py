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

"""Implementation of subcmd: changelog
"""

import os, datetime
import tempfile, glob
import subprocess, shutil

import msger
import runner
import errors

from conf import configmgr

from gbp.rpm.git import GitRepositoryError, RpmGitRepository

EDITOR=configmgr.get('editor') or 'vi'

class Changes():
    import re

    log_entries = []

    entry_res = [
        re.compile(r'^\*\s+(\w{3} \w{3} \d{2} \d{4})\s+([\w\s<.]+@[\w.]+>)[\s-]+([\w.-]+)'),
        re.compile(r'^\*\s+(\w{3} \w{3} \d{2} \d{4})\s+([\w\s<.]+@[\w.]+>)()')
        ]

    def __init__(self, filename):
        if not os.path.isfile(filename):
            raise errors.GBSError("%s is not a general file" %filename)

        self.changesfile = filename
        with open(filename) as changes:
            l = changes.readline()
            while l:
                entry = []
                if l.startswith('*'):
                    entry.append(l)
                    while l:
                        l = changes.readline()
                        if l.startswith('*'):
                            break
                        entry.append(l)
                self.log_entries.append(entry)

    def get_entry(self, index=0):
        if not self.log_entries:
            return None
        return self.log_entries[index]

    def parse_entry(self, entry):
        import datetime
        if not entry:
            return None
        for re in self.entry_res:
            match = re.match(entry[0])
            if match:
                date = match.group(1)
                author = match.group(2)
                version = match.group(3)

                body = ''.join(entry[1:])
                return datetime.datetime.strptime(date, "%a %b %d %Y"), author, version, body
        return None

    def add_entry(self, author, version, date, body):
        date_str = date.strftime("%a %b %d %Y")
        """ first line start with '*'  """
        if version:
            top_entry = ["* %s %s - %s\n" %(date_str, author, version)]
        else:
            top_entry = ["* %s %s\n" %(date_str, author)]
        """ every body line start with '-' """
        for line in body:
            top_entry.append("- %s\n" %line)
        top_entry.append('\n')

        """ add the new entry to the top of changelog """
        with open(self.changesfile, 'r+') as f:
            lines = f.readlines()
            lines = top_entry + lines
            f.seek(0)
            for l in lines:
                f.write(l)
            f.flush()
"""
convert commits to log entry message
"""
def commits_to_log_entry_body(commits, git_repo):
    """ itemized by author """
    author_contribution = {}
    for c in commits:
        commit_info =  git_repo.get_commit_info(c)
        if author_contribution.has_key(commit_info['author']):
            author_contribution[commit_info['author']].append(commit_info['subject'])
        else:
            author_contribution[commit_info['author']] = []
            author_contribution[commit_info['author']].append(commit_info['subject'])

    entry_body = []
    author_list = author_contribution.keys()
    author_list.sort()
    for author in author_list:
        entry_body.append("[ %s ]" %author)
        entry_body.extend(author_contribution[author])

    return entry_body

def do(opts, args):

    opts_full_msg = opts.full_msg
    opts_author = opts.author

    project_root_dir = '.'

    try:
        repo = RpmGitRepository(project_root_dir)
    except GitRepositoryError:
        msger.error("No git repository found.")

    if not repo.is_clean():
        msger.error("Git tree is not clean")

    changes_file_list = glob.glob("%s/packaging/*.changes" %(project_root_dir))

    if len(changes_file_list) > 1:
        msger.warning("Found more than one changes files, %s is taken " %(changes_file_list[0]))

    elif len(changes_file_list) == 0:
        msger.error("Found no changes file under packaging dir")

    origin_changes = changes_file_list[0]

    """ save to a temp file
    """
    fd, fn_changes = tempfile.mkstemp()
    f = os.fdopen(fd, 'w')
    f.write(''.join(open(origin_changes).readlines()))
    f.close()

    changes = Changes(fn_changes)

    """ get the commit start from the opts.sinece
    """
    if opts.since:
        commitid_since = repo.rev_parse(opts.since)
        if not commitid_since:
            mesger.error("Invalid since commit object name: %s" %(opts.since))
    else:
        dummy1, dummy2, version, dummy4 = changes.parse_entry(changes.get_entry())
        commitid_since = repo.rev_parse(version)
        if not commitid_since:
            msger.error("Can't get last commit ID in log, please specify it by '--since'")

    commits = repo.get_commits(commitid_since, 'HEAD')
    if not commits:
        msger.error("Nothing found between %s and HEAD" %commitid_since)

    log_entry_body = commits_to_log_entry_body(commits, repo)

    if opts.author:
        log_author = opts.author
    else:
        log_author = "%s <%s>" %(repo.get_config('user.name'), repo.get_config('user.email'))

    if opts.version:
        log_version = opts.version
    else:
        try:
            log_version = repo.find_tag('HEAD')
        except GitRepositoryError:
            log_version = repo.rev_parse('HEAD', '--short')

    log_date = datetime.datetime.today()

    changes.add_entry(log_author, log_version, log_date, log_entry_body)

    subprocess.call("%s %s" %(EDITOR, fn_changes), shell=True)

    shutil.move(fn_changes, origin_changes)
    msger.info("Change log file updated.")
