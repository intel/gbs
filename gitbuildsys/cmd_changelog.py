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

import os
import datetime
import tempfile
import glob
import subprocess
import shutil

import msger
import errors

from conf import configmgr

from gbp.rpm.git import GitRepositoryError, RpmGitRepository

EDITOR = configmgr.get('editor') or 'vi'

class Changes():
    import re

    log_entries = []

    entry_res = [
        re.compile(r'^\*\s+(\w{3} \w{3} \d{2} \d{4})\s+([\w\s<.-]+@[\w.-]+>)[\s-]+([\w\d.@-]+)'),
        re.compile(r'^\*\s+(\w{3} \w{3} \d{2} \d{4})\s+([\w\s<.-]+@[\w.-]+>)()')
        ]

    def __init__(self, filename):
        if not os.path.isfile(filename):
            raise errors.GBSError("%s is not a general file" % filename)

        self.changesfile = filename
        with open(filename) as changes:
            line = changes.readline()
            while line:
                entry = []
                if line.startswith('*'):
                    entry.append(line)
                    while line:
                        line = changes.readline()
                        if line.startswith('*'):
                            break
                        entry.append(line)
                self.log_entries.append(entry)

    def get_entry(self, index=0):
        if not self.log_entries:
            return None
        return self.log_entries[index]

    def parse_entry(self, entry):
        if not entry:
            return None
        for regexp in self.entry_res:
            match = regexp.match(entry[0])
            if match:
                date = match.group(1)
                author = match.group(2)
                version = match.group(3)

                body = ''.join(entry[1:])
                return datetime.datetime.strptime(date, "%a %b %d %Y"), \
                       author, version, body
        return None

    def add_entries(self, new_entries):
        """Add new entries to the top of changelog."""
        lines = new_entries[:]
        lines.append('\n')
        with open(self.changesfile) as chlog:
            lines.extend(chlog.readlines())
        with open(self.changesfile, 'w') as chlog:
            chlog.writelines(lines)


def make_log_entries(commits, git_repo):
    entries = []
    prevdate = None
    prevauthor = None
    cr = ""
    for commit in commits:
        commit_info =  git_repo.get_commit_info(commit)

        # set version to <tag>@<sha1> or <sha1> if tag is not found
        version = git_repo.rev_parse(commit, ['--short'])
        try:
            version = "%s@%s" % (git_repo.find_tag('HEAD'), version)
        except GitRepositoryError:
            pass

        # Add new entry header if date is changed
        date = datetime.datetime.fromtimestamp(int(commit_info["timestamp"]))
        if not prevdate or (date.year, date.month, date.day) != \
               (prevdate.year, prevdate.month, prevdate.day):
            entries.append("%s* %s %s <%s> %s\n" % (cr, date.strftime("%a %b %d %Y"),
                                                commit_info["author"],
                                                commit_info["email"],
                                                version))
            cr = "\n"
        # Track authors
        elif not prevauthor or prevauthor != commit_info["author"]:
            entries.append("[ %s ]\n" % commit_info["author"])

        entries.append("- %s\n" % commit_info["subject"])
        prevdate = date
        prevauthor = commit_info["author"]
    return entries


def do(opts, _args):

    project_root_dir = '.'

    try:
        repo = RpmGitRepository(project_root_dir)
    except GitRepositoryError:
        msger.error("No git repository found.")

    if not repo.is_clean():
        msger.error("Git tree is not clean")

    changes_file_list = glob.glob("%s/packaging/*.changes" % project_root_dir)

    if len(changes_file_list) > 1:
        msger.warning("Found more than one changes files, %s is taken " \
                       % (changes_file_list[0]))

    elif len(changes_file_list) == 0:
        msger.error("Found no changes file under packaging dir")

    origin_changes = changes_file_list[0]

    # save to a temp file
    fds, fn_changes = tempfile.mkstemp()
    fds2 = os.fdopen(fds, 'w')
    fds2.write(''.join(open(origin_changes).readlines()))
    fds2.close()

    changes = Changes(fn_changes)

    # get the commit start from the opts.since
    if opts.since:
        commitid_since = repo.rev_parse(opts.since)
        if not commitid_since:
            msger.error("Invalid since commit object name: %s" % (opts.since))
    else:
        sha1 = changes.parse_entry(changes.get_entry())[2].split('@')[-1]
        commitid_since = repo.rev_parse(sha1)
        if not commitid_since:
            msger.error("Can't find last commit ID in the log, "\
                       "please specify it by '--since'")

    commits = repo.get_commits(commitid_since, 'HEAD')
    if not commits:
        msger.error("Nothing found between %s and HEAD" % commitid_since)

    new_entries = make_log_entries(commits, repo)
    changes.add_entries(new_entries)

    rc = subprocess.call("%s %s" % (EDITOR, fn_changes), shell=True)
    shutil.move(fn_changes, origin_changes)
    msger.info("Change log file updated.")
