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
import glob
import subprocess

import msger

from conf import configmgr

from gbp.rpm.git import GitRepositoryError, RpmGitRepository

EDITOR = configmgr.get('editor') or os.getenv('EDITOR') or 'vi'


def add_entries(changesfile, new_entries):
    """Add new entries to the top of changelog."""
    lines = new_entries[:]
    lines.append("\n")
    with open(changesfile) as chlog:
        lines.extend(chlog.readlines())
    with open(changesfile, "w") as chlog:
        chlog.writelines(lines)


def get_latest_rev(changesfile):
    """Get latest git revision from the changelog."""
    with open(changesfile) as chlog:
        line = chlog.readline()
        return line.strip().split(" ")[-1].split("@")[-1]


def make_log_entries(commits, git_repo):
    """Make changelog entries from the set of git commits."""
    entries = []
    prevdate = None
    prevauthor = None
    cret = ""
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
            entries.append("%s* %s %s <%s> %s\n" % (cret,
                                                date.strftime("%a %b %d %Y"),
                                                commit_info["author"],
                                                commit_info["email"],
                                                version))
            cret = "\n"
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

    if changes_file_list:
        fn_changes = changes_file_list[0]
        if len(changes_file_list) > 1:
            msger.warning("Found more than one changes files, %s is taken " \
                           % (changes_file_list[0]))
    else:
        # Create .changes file with the same name as a spec
        spec_file_list = glob.glob("%s/packaging/*.spec" % project_root_dir)
        if spec_file_list:
            fn_changes = os.path.splitext(spec_file_list[0])[0] + ".changes"
            open(fn_changes, 'w').close() # touch
        else:
            msger.error("Found no changes nor spec files under packaging dir")

    # get the commit start from the opts.since
    if opts.since:
        since = opts.since
    else:
        since = get_latest_rev(fn_changes)

    commitid_since = None
    if since:
        try:
            commitid_since = repo.rev_parse(since)
        except GitRepositoryError:
            if opts.since:
                msger.error("Invalid commit: %s" % (opts.since))
            else:
                msger.error("Can't find last commit ID in the log, "\
                            "please specify it by '--since'")

    commits = repo.get_commits(commitid_since, 'HEAD')
    if not commits:
        msger.error("Nothing found between %s and HEAD" % commitid_since)

    new_entries = make_log_entries(commits, repo)
    add_entries(fn_changes, new_entries)

    subprocess.call("%s %s" % (EDITOR, fn_changes), shell=True)
    msger.info("Change log file updated.")
