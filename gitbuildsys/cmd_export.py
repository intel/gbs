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
import shutil
import errno

import msger
import runner
import utils
import errors

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

    if opts.commit and opts.include_all:
        raise errors.Usage('--commit can\'t be specified together with '\
                           '--include-all')

    try:
        repo = RpmGitRepository(workdir)
    except GitRepositoryError, err:
        msger.error(str(err))

    utils.gitStatusChecker(repo, opts)
    workdir = repo.path

    if not os.path.exists("%s/packaging" % workdir):
        msger.error('No packaging directory, so there is nothing to export.')

    # Only guess spec filename here, parse later when we have the correct
    # spec file at hand
    specfile = utils.guess_spec(workdir, opts.spec)

    outdir = "%s/packaging" % workdir
    if opts.outdir:
        outdir = opts.outdir
    mkdir_p(outdir)
    outdir = os.path.abspath(outdir)
    tempd = utils.Temp(prefix='gbs_export_', dirn=outdir, directory=True)
    export_dir = tempd.path

    with utils.Workdir(workdir):
        if opts.commit:
            commit = opts.commit
        elif opts.include_all:
            commit = 'WC.UNTRACKED'
        else:
            commit = 'HEAD'
        relative_spec = specfile.replace('%s/' % workdir, '')
        try:
            if gbp_build(["argv[0] placeholder", "--git-export-only",
                          "--git-ignore-new", "--git-builder=osc",
                          "--git-no-auto-patch-gen",
                          "--git-upstream-tree=%s" % commit,
                          "--git-export-dir=%s" % export_dir,
                          "--git-packaging-dir=packaging",
                          "--git-spec-file=%s" % relative_spec,
                          "--git-export=%s" % commit]):
                msger.error("Failed to get packaging info from git tree")
        except GitRepositoryError, excobj:
            msger.error("Repository error: %s" % excobj)

    try:
        spec = rpm.parse_spec(os.path.join(export_dir, os.path.basename(specfile)))
    except GbpError, err:
        msger.error('%s' % err)

    if not spec.name or not spec.version:
        msger.error('can\'t get correct name or version from spec file.')
    else:
        outdir = "%s/%s-%s-%s" % (outdir, spec.name, spec.upstreamversion, spec.release)
        shutil.rmtree(outdir, ignore_errors=True)
        shutil.move(export_dir, outdir)

    if opts.source_rpm:
        cmd = ['rpmbuild',
               '--short-circuit', '-bs',
               '--define "_topdir %s"' % outdir,
               '--define "_builddir %_topdir"',
               '--define "_buildrootdir %_topdir"',
               '--define "_rpmdir %_topdir"',
               '--define "_sourcedir %_topdir"',
               '--define "_specdir %_topdir"',
               '--define "_srcrpmdir %_topdir"',
               specfile
              ]
        runner.quiet(' '.join(cmd))
        msger.info('source rpm generated to:\n     %s/%s.src.rpm' % \
                   (outdir, os.path.basename(outdir)))

    msger.info('package files have been exported to:\n     %s' % outdir)
