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

import glob

from gitbuildsys.utils import guess_spec, get_editor_cmd
from gitbuildsys.cmd_export import get_packaging_dir
from gitbuildsys.errors import GbsError
from gitbuildsys.log import LOGGER as log

from gbp.rpm.git import GitRepositoryError, RpmGitRepository
from gbp.scripts.rpm_changelog import main as gbp_rpm_ch



def main(args):
    """gbs changelog entry point."""

    try:
        repo = RpmGitRepository(args.gitdir)
    except GitRepositoryError, err:
        raise GbsError(str(err))

    packaging_dir = get_packaging_dir(args)
    specfile = guess_spec(repo.path, packaging_dir, args.spec)[0]
    changes_file_list = glob.glob("%s/%s/*.changes" % (repo.path,
                                                       packaging_dir))
    if changes_file_list:
        fn_changes = changes_file_list[0]
        if len(changes_file_list) > 1:
            log.warning("Found more than one changes files, %s is taken "
                           % (changes_file_list[0]))
    else:
        fn_changes = 'CHANGES'

    gbp_args = ['dummy argv[0]',
                '--color-scheme=magenta:green:yellow:red',
                '--ignore-branch',
                '--changelog-revision=%(tagname)s',
                '--spawn-editor=always',
                '--git-author',
                '--packaging-dir=%s' % packaging_dir,
                '--spec-file=%s' % specfile,
                '--changelog-file=%s' % fn_changes,
                '--editor-cmd=%s' % get_editor_cmd(),
                ]
    if args.since:
        gbp_args.append('--since=%s' % args.since)
    if args.message:
        gbp_args.append('--message=%s' % args.message)

    ret = gbp_rpm_ch(gbp_args)
    if ret:
        raise GbsError("Change log has not been updated")
    else:
        log.info("Change log has been updated.")

