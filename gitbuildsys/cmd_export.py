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

"""Implementation of subcmd: export
"""

import os
import glob
import urlparse
import shutil
import errno

import msger
import utils

from gbp.scripts.buildpackage_rpm import main as gbp_build
from gbp.rpm.git import GitRepositoryError, RpmGitRepository
import gbp.rpm as rpm
from gbp.errors import GbpError


def mkdir_p(path):
    """
    Create directory as in mkdir -p
    """
    try:
        os.makedirs(path)
    except OSError as exc: # Python >2.5
        if exc.errno == errno.EEXIST:
            pass
        else:
            raise

def do(opts, args):
    """
    The main plugin call
    """
    workdir = os.getcwd()

    if len(args) > 1:
        msger.error('only one work directory can be specified in args.')
    if len(args) == 1:
        workdir = os.path.abspath(args[0])

    try:
        repo = RpmGitRepository(workdir)
        if repo.get_branch() is None:
            msger.error('currently not on a branch')
    except GitRepositoryError, err:
        msger.error(str(err))

    workdir = repo.path

    if not os.path.exists("%s/packaging" % workdir):
        msger.error('No packaging directory, so there is nothing to export.')

    if not os.path.isdir("%s/.git" % workdir):
        msger.error('Not a git repository (%s), aborting' % workdir)

    outdir = "%s/packaging" % workdir
    if opts.outdir:
        outdir = opts.outdir

    specfile = utils.guess_spec(workdir, opts.spec)
    try:
        spec = rpm.parse_spec(specfile)
    except GbpError, err:
        msger.error('%s' % err)

    if not spec.name or not spec.version:
        msger.error('can\'t get correct name or version from spec file.')
    else:
        outdir = "%s/%s-%s-%s" % (outdir, spec.name, spec.version, spec.release)
        mkdir_p(outdir)

    urlres = urlparse.urlparse(spec.orig_file)
    tarball = '%s/%s' % (outdir, os.path.basename(urlres.path))
    msger.info('generate tar ball: %s' % tarball)

    with utils.Workdir(workdir):
        relative_spec = specfile.replace('%s/' % workdir, '')
        try:
            if gbp_build(["argv[0] placeholder", "--git-export-only",
                          "--git-ignore-new", "--git-builder=osc",
                          "--git-export-dir=%s" % outdir,
                          "--git-packaging-dir=packaging",
                          "--git-specfile=%s" % relative_spec,
                          "--git-export=%s" % 'HEAD']):
                msger.error("Failed to get packaging info from git tree")
        except GitRepositoryError, excobj:
            msger.error("Repository error: %s" % excobj)

    msger.info('package files have been exported to:\n     %s' % outdir)
