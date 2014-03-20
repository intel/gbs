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

"""Implementation of subcmd: import
"""
import os
import re

from gitbuildsys.errors import GbsError
from gitbuildsys.cmd_export import get_packaging_dir
from gitbuildsys.log import LOGGER as log
from gitbuildsys.utils import Temp
from gitbuildsys.conf import configmgr

from gbp.scripts.import_srpm import main as gbp_import_srpm
from gbp.scripts.import_orig_rpm import main as gbp_import_orig

def main(args):
    """gbs import entry point."""

    if args.author_name:
        os.environ["GIT_AUTHOR_NAME"] = args.author_name
    if args.author_email:
        os.environ["GIT_AUTHOR_EMAIL"] = args.author_email

    path = args.path

    tmp = Temp(prefix='gbp_',
               dirn=configmgr.get('tmpdir', 'general'),
               directory=True)

    upstream_branch = configmgr.get_arg_conf(args, 'upstream_branch')
    upstream_tag = configmgr.get_arg_conf(args, 'upstream_tag')
    # transform variables from shell to python convention ${xxx} -> %(xxx)s
    upstream_tag = re.sub(r'\$\{([^}]+)\}', r'%(\1)s', upstream_tag)

    params = ["argv[0] placeholder",
              "--color-scheme=magenta:green:yellow:red",
              "--packaging-dir=%s" % get_packaging_dir(args),
              "--upstream-branch=%s" % upstream_branch, path,
              "--upstream-tag=%s" % upstream_tag,
              "--tmp-dir=%s" % tmp.path,
              ]
    if args.debug:
        params.append("--verbose")
    if not args.no_pristine_tar and os.path.exists("/usr/bin/pristine-tar"):
        params.append("--pristine-tar")
    if args.filter:
        params += [('--filter=%s' % f) for f in args.filter]
    if args.upstream_vcs_tag:
        params.append('--upstream-vcs-tag=%s' % args.upstream_vcs_tag)

    if path.endswith('.src.rpm') or path.endswith('.spec'):
        params.append("--create-missing-branches")
        if args.allow_same_version:
            params.append("--allow-same-version")
        if args.native:
            params.append("--native")
        if args.orphan_packaging:
            params.append("--orphan-packaging")
        if args.no_patch_import:
            params.append("--no-patch-import")
        ret = gbp_import_srpm(params)
        if ret == 2:
            log.warning("Importing of patches into packaging branch failed! "
                        "Please import manually (apply and commit to git, "
                        "remove files from packaging dir and spec) in order "
                        "to enable automatic patch generation.")
        elif ret:
            raise GbsError("Failed to import %s" % path)
    else:
        if args.merge:
            params.append('--merge')
        else:
            params.append('--no-merge')
        if gbp_import_orig(params):
            raise GbsError('Failed to import %s' % path)

    log.info('done.')
