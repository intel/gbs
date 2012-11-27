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

from gitbuildsys import msger
from gitbuildsys.utils import guess_spec, edit_file
from gitbuildsys.cmd_export import get_packaging_dir

from gbp.rpm.git import GitRepositoryError, RpmGitRepository



def get_all_entries(changesfile, new_entries):
    """return all entries including old in changesfile and new_entries"""
    lines = ["%s%s" % (line, os.linesep) for line in new_entries]
    lines.append(os.linesep)

    if os.path.exists(changesfile):
        with open(changesfile) as chlog:
            lines.extend(chlog.readlines())
    return ''.join(lines)


def get_latest_rev(changesfile):
    """Get latest git revision from the changelog."""
    if os.path.exists(changesfile):
        with open(changesfile) as chlog:
            line = chlog.readline()
            return line.strip().split(" ")[-1].split("@")[-1]
    return ''

def get_version(git_repo, commit):
    """
    Construct version from commit using rev-parse.
    Set version to <tag>@<sha1> or <sha1> if tag is not found.
    """
    version = git_repo.rev_parse(commit, short=7)
    try:
        version = "%s@%s" % (git_repo.find_tag(commit), version)
    except GitRepositoryError:
        pass

    return version

def make_log_entries(commits, git_repo):
    """Make changelog entries from the set of git commits."""
    entries = []
    # Add header
    author = git_repo.get_author_info()
    entries.append("* %s %s <%s> %s" % \
                   (datetime.datetime.now().strftime("%a %b %d %Y"),
                    author.name, author.email, get_version(git_repo,
                                                           commits[0])))
    for commit in commits:
        commit_info =  git_repo.get_commit_info(commit)
        entries.append("- %s" % commit_info["subject"])
    return entries


def main(args):
    """gbs changelog entry point."""

    try:
        repo = RpmGitRepository(args.gitdir)
    except GitRepositoryError, err:
        msger.error(str(err))

    project_root_dir = repo.path

    packaging_dir = get_packaging_dir(args)
    changes_file_list = glob.glob("%s/%s/*.changes" % (project_root_dir,
                                                       packaging_dir))

    if args.spec or not changes_file_list:
        # Create .changes file with the same name as a spec
        specfile = os.path.basename(guess_spec(project_root_dir,
                                               packaging_dir, args.spec))
        fn_changes = os.path.splitext(specfile)[0] + ".changes"
        fn_changes = os.path.join(project_root_dir, packaging_dir, fn_changes)
    else:
        fn_changes = changes_file_list[0]
        if len(changes_file_list) > 1:
            msger.warning("Found more than one changes files, %s is taken " \
                           % (changes_file_list[0]))

    # get the commit start from the args.since
    if args.since:
        since = args.since
    else:
        since = get_latest_rev(fn_changes)

    commitid_since = None
    if since:
        try:
            commitid_since = repo.rev_parse(since)
        except GitRepositoryError:
            if args.since:
                msger.error("Invalid commit: %s" % (since))
            else:
                msger.error("Can't find last commit ID in the log, "\
                            "please specify it by '--since'")

    commits = repo.get_commits(commitid_since, 'HEAD')
    if not commits:
        msger.error("Nothing found between %s and HEAD" % commitid_since)

    if args.message:
        author = repo.get_author_info()
        lines = ["- %s" % line for line in args.message.split(os.linesep) \
                                            if line.strip()]
        new_entries = ["* %s %s <%s> %s" % \
                           (datetime.datetime.now().strftime("%a %b %d %Y"),
                            author.name, author.email,
                            get_version(repo, commits[0]))]
        new_entries.extend(lines)
    else:
        new_entries = make_log_entries(commits, repo)

    content = get_all_entries(fn_changes, new_entries)
    if edit_file(fn_changes, content):
        msger.info("Change log has been updated.")
    else:
        msger.info("Change log has not been updated")

