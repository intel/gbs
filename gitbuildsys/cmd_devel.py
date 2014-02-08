#!/usr/bin/python -tt
# vim: ai ts=4 sts=4 et sw=4
#
# Copyright (c) 2014 Intel, Inc.
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

"""Implementation of subcmd: devel
"""

import os
import datetime
import glob
import re

from gitbuildsys.cmd_export import get_packaging_dir
from gitbuildsys.conf import configmgr, BrainConfigParser
from gitbuildsys.errors import GbsError
from gitbuildsys.log import LOGGER as log
from gitbuildsys.utils import guess_spec, edit_file, Temp

from gbp.scripts.pq_rpm import main as gbp_pq_rpm
from gbp.rpm.git import GitRepositoryError, RpmGitRepository

def compose_gbp_args(repo, tmp_dir, spec, args):
    """Compose command line arguments for gbp-pq-rpm"""
    upstream_tag = configmgr.get_arg_conf(args, 'upstream_tag')
    # transform variables from shell to python convention ${xxx} -> %(xxx)s
    upstream_tag = re.sub(r'\$\{([^}]+)\}', r'%(\1)s', upstream_tag)

    packaging_dir = get_packaging_dir(args)

    # Compose the list of command line arguments
    argv = ["argv[0] placeholder",
            "--color-scheme=magenta:green:yellow:red",
            "--vendor=Tizen",
            "--tmp-dir=%s" % tmp_dir,
            "--packaging-dir=%s" % packaging_dir,
            "--new-packaging-dir=%s" % packaging_dir,
            "--spec-file=%s" % spec,
            "--upstream-tag=%s" % upstream_tag,
            "--pq-branch=development/%(branch)s/%(upstreamversion)s",
            "--import-files=.gbs.conf",
            "--patch-export-compress=100k",
            "--patch-export-ignore-path=^(%s/.*|.gbs.conf)" % packaging_dir]
    if args.debug:
        argv.append("--verbose")

    return argv

def update_local_conf(repo, values):
    """Create/update local gbs.conf"""
    parser = BrainConfigParser()
    conf_fn = os.path.join(repo.path, '.gbs.conf')
    log.info('Updating local .gbs.conf')
    with open(conf_fn, 'a+') as conf_fp:
        parser.readfp(conf_fp)
    for section, items in values.iteritems():
        for key, value in items.iteritems():
            parser.set_into_file(section, key, value)
    parser.update()

    log.info('Committing local .gbs.conf to git')
    repo.add_files(['.gbs.conf'])
    repo.commit_all(msg="Autoupdate local .gbs.conf\n\nGbp-Rpm: Ignore")


def main(args):
    """gbs devel entry point."""

    try:
        repo = RpmGitRepository(args.gitdir)
    except GitRepositoryError, err:
        raise GbsError(str(err))

    tmp = Temp(prefix='gbp_', dirn=configmgr.get('tmpdir', 'general'),
                     directory=True)
    packaging_dir = get_packaging_dir(args)

    # Guess spec from correct branch
    packaging_branch = configmgr.get('packaging_branch', 'orphan-devel')
    commit_id = packaging_branch if packaging_branch else 'WC.UNTRACKED'
    specfile = guess_spec(repo.path, packaging_dir, args.spec, commit_id)[0]

    # Get current branch
    try:
        current_branch = repo.get_branch()
    except GitRepositoryError:
        current_branch = None

    gbp_args = compose_gbp_args(repo, tmp.path, specfile, args)

    # Run gbp command
    if args.action == 'start':
        ret = gbp_pq_rpm(gbp_args + ['import'])
        if not ret:
            update_local_conf(repo, {'orphan-devel':
                                     {'packaging_branch': current_branch}})
    elif args.action == 'export':
        log.info('Exporting patches to packaging branch')
        ret = gbp_pq_rpm(gbp_args + ['export'])
    elif args.action == 'switch':
        ret = gbp_pq_rpm(gbp_args + ['switch'])
    elif args.action == 'drop':
        ret = gbp_pq_rpm(gbp_args + ['drop'])
    elif args.action == 'convert':
        log.info('Converting package to orphan-packaging git layout')
        ret = gbp_pq_rpm(gbp_args + ['convert'])
        if not ret:
            log.info("You can now create the development branch with "
                      "'gbs devel start'")
    if ret:
        raise GbsError('Action failed!')

