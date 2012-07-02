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
import shutil

import msger
import utils

from conf import configmgr

from gbp.rpm.git import GitRepositoryError, RpmGitRepository

EDITOR = configmgr.get('editor') or os.getenv('EDITOR') or 'vi'


def add_entries(changesfile, new_entries):
    """Add new entries to the top of changelog."""
    lines = ["%s%s" % (line, os.linesep) for line in new_entries]
    lines.append(os.linesep)
    with open(changesfile) as chlog:
        lines.extend(chlog.readlines())
    with open(changesfile, "w") as chlog:
        chlog.writelines(lines)


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
    version = git_repo.rev_parse(commit, ['--short'])
    try:
        version = "%s@%s" % (git_repo.find_tag(commit), version)
    except GitRepositoryError:
        pass

    return version

def make_log_entries(commits, git_repo):
    """Make changelog entries from the set of git commits."""
    entries = []
    prevauthor = None
    # Add header
    author = git_repo.get_author_info()
    entries.append("* %s %s <%s> %s" % \
                   (datetime.datetime.now().strftime("%a %b %d %Y"),
                    author.name, author.email, get_version(git_repo,
                                                           commits[0])))
    for commit in commits:
        commit_info =  git_repo.get_commit_info(commit)

        # Track authors
        if not prevauthor or prevauthor != commit_info["author"]:
            entries.append("[ %s ]" % commit_info["author"])

        entries.append("- %s" % commit_info["subject"])
        prevauthor = commit_info["author"]
    return entries


def do(opts, _args):

    try:
        repo = RpmGitRepository('.')
        if repo.get_branch() is None:
            msger.error('currently not on a branch')
    except GitRepositoryError, err:
        msger.error(str(err))

    project_root_dir = repo.path

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

    commits = [info.split()[1] for info in sorted(repo.get_commits(\
                  commitid_since, 'HEAD', options=['--pretty=format:%at %H']),
                  reverse=True)]
    if not commits:
        msger.error("Nothing found between %s and HEAD" % commitid_since)

    if opts.message:
        author = repo.get_author_info()
        lines = [" -%s" % line for line in opts.message.split(os.linesep) \
                                            if line.strip()]
        new_entries = ["* %s %s <%s> %s" % \
                           (datetime.datetime.now().strftime("%a %b %d %Y"),
                            author.name, author.email,
                            get_version(repo, commits[0]))]
        new_entries.extend(lines)
    else:
        new_entries = make_log_entries(commits, repo)

    # create temporary copy and update it with new entries
    temp = utils.TempCopy(fn_changes)
    add_entries(temp.name, new_entries)
    temp.update_stat()

    subprocess.call("%s %s" % (EDITOR, temp.name), shell=True)

    if temp.is_changed():
        try:
            shutil.copy2(temp.name, fn_changes)
        except (IOError, shutil.Error), excobj:
            msger.error("Can't update %s: %s" % (fn_changes, str(excobj)))
        msger.info("Change log has been updated.")
    else:
        msger.info("Change log has not been updated")

