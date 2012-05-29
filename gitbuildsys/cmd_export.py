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

from gbp.scripts.buildpackage_rpm import git_archive, guess_comp_type
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

    if not os.path.exists("%s/packaging" % workdir):
        msger.error('No packaging directory, so there is nothing to export.')

    if len(args) > 1:
        msger.error('only one work directory can be specified in args.')
    if len(args) == 1:
        workdir = args[0]

    if not os.path.isdir("%s/.git" % workdir):
        msger.error('Not a git repository (%s), aborting' % workdir)

    outdir = "%s/packaging" % workdir
    if opts.outdir:
        outdir = opts.outdir

    specfile = utils.guess_spec(workdir, opts.spec)
    spec = rpm.parse_spec(specfile)
    if not spec.name or not spec.version:
        msger.error('can\'t get correct name or version from spec file.')
    else:
        if opts.outdir:
            outdir = "%s/%s-%s-%s" % (outdir, spec.name,
                    spec.version, spec.release)
        mkdir_p(outdir)

    if outdir and outdir != workdir and outdir != "%s/packaging" % workdir:
        for name in glob.glob('%s/packaging/*' % workdir):
            if (os.path.isfile(name)):
                shutil.copy(name, outdir)

    urlres = urlparse.urlparse(spec.orig_file)
    tarball = '%s/%s' % (outdir, os.path.basename(urlres.path))
    msger.info('generate tar ball: %s' % tarball)
    try:
        repo = RpmGitRepository(workdir)
    except GitRepositoryError:
        msger.error("%s is not a git repository" % (os.path.curdir))

    try:
        comp_type = guess_comp_type(spec)
        if not git_archive(repo, spec, outdir, 'HEAD',
                           comp_type, comp_level=9, with_submodules=True):
            msger.error("Cannot create source tarball %s" % tarball)
    except GbpError, exc:
        msger.error(str(exc))
