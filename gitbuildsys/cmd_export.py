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
import re
import shutil
import glob
import errno
from urlparse import urlparse

from gitbuildsys import utils
from gitbuildsys.conf import configmgr
from gitbuildsys.errors import GbsError, Usage
from gitbuildsys.log import LOGGER as log

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
            raise GbsError('failed to create %s: %s' % (path, exc.strerror))

def is_native_pkg(repo, args):
    """
    Determine if the package is "native"
    """
    upstream_branch = configmgr.get_arg_conf(args, 'upstream_branch')
    return not repo.has_branch(upstream_branch)

def get_packaging_dir(args):
    """
    Determine the packaging dir to be used
    """
    path = configmgr.get_arg_conf(args, 'packaging_dir')
    return path.rstrip(os.sep)

def track_export_branches(repo, args):
    '''checking export related branches: pristine-tar, upstream.
    give warning if pristine-tar/upstream branch exist in remote
    but have not been checkout to local
    '''
    remote_branches = {}
    tracked_branches = []
    for branch in repo.get_remote_branches():
        remote_branches[branch.split('/', 1)[-1]] = branch
    upstream_branch = configmgr.get_arg_conf(args, 'upstream_branch')

    # track upstream/pristine-tar branch
    for branch in [upstream_branch, 'pristine-tar']:
        if not repo.has_branch(branch) and branch in remote_branches:
            log.info('tracking branch: %s -> %s' % (remote_branches[branch],
                                                    branch))
            repo.create_branch(branch, remote_branches[branch])
            tracked_branches.append(branch)

    return tracked_branches

def untrack_export_branches(repo, branches):
    ''' remove local tracking branches, created in track_export_branches()
    '''
    for branch in branches:
        repo.delete_branch(branch)

def create_gbp_export_args(repo, commit, export_dir, tmp_dir, spec, args,
                           create_tarball=True):
    """
    Construct the cmdline argument list for git-buildpackage export
    """
    upstream_branch = configmgr.get_arg_conf(args, 'upstream_branch')
    upstream_tag = configmgr.get_arg_conf(args, 'upstream_tag')
    # transform variables from shell to python convention ${xxx} -> %(xxx)s
    upstream_tag = re.sub(r'\$\{([^}]+)\}', r'%(\1)s', upstream_tag)

    log.debug("Using upstream branch: %s" % upstream_branch)
    log.debug("Using upstream tag format: '%s'" % upstream_tag)

    # Get patch squashing option
    squash_patches_until = configmgr.get_arg_conf(args, 'squash_patches_until')

    # Determine the remote repourl
    reponame = ""
    remotes = repo.get_remote_repos()
    if remotes:
        remotename = 'origin' if 'origin' in remotes else remotes.keys()[0]
        # Take the remote repo of current branch, if available
        try:
            config_remote = repo.get_config('branch.%s.remote' % repo.branch)
        except KeyError:
            pass
        else:
            if config_remote in remotes:
                remotename = config_remote
            elif config_remote != '.':
                log.warning("You appear to have non-existent remote '%s' "
                            "configured for branch '%s'. Check your git config!"
                            % (config_remote, repo.branch))
        reponame = urlparse(remotes[remotename][0]).path.lstrip('/')

    packaging_dir = get_packaging_dir(args)
    # Now, start constructing the argument list
    argv = ["argv[0] placeholder",
            "--git-color-scheme=magenta:green:yellow:red",
            "--git-ignore-new",
            "--git-compression-level=6",
            "--git-export-dir=%s" % export_dir,
            "--git-tmp-dir=%s" % tmp_dir,
            "--git-packaging-dir=%s" % packaging_dir,
            "--git-spec-file=%s" % spec,
            "--git-pq-branch=development/%(branch)s/%(upstreamversion)s",
            "--git-upstream-branch=%s" % upstream_branch,
            "--git-upstream-tag=%s" % upstream_tag,
            "--git-spec-vcs-tag=%s#%%(commit)s" % reponame]

    if create_tarball:
        argv.append("--git-force-create")
    else:
        argv.append("--git-no-create-orig")
    if args.debug:
        argv.append("--git-verbose")
    if is_native_pkg(repo, args) or args.no_patch_export:
        argv.extend(["--git-no-patch-export",
                     "--git-export=%s" % commit,
                     "--git-upstream-tree=%s" % commit])
    else:
        # Check if the revision seems to be of an orphan development branch
        is_orphan = False
        export_commitish = 'HEAD' if commit == 'WC.UNTRACKED' else commit
        try:
            repo.get_merge_base(export_commitish, upstream_branch)
        except GitRepositoryError:
            is_orphan = True
        # Development branch in orphan packaging model is identified in the conf
        orphan_packaging = configmgr.get('packaging_branch', 'orphan-devel')

        if not is_orphan:
            argv.extend(["--git-patch-export",
                         "--git-patch-export-compress=100k",
                         "--git-patch-export-squash-until=%s" %
                            squash_patches_until,
                         "--git-patch-export-ignore-path=^(%s/.*|.gbs.conf)" %
                            packaging_dir,
                        ])

            if orphan_packaging:
                argv.extend(["--git-export=%s" % orphan_packaging,
                             "--git-patch-export-rev=%s" % commit])
            else:
                argv.extend(["--git-export=%s" % commit])

        if repo.has_branch("pristine-tar"):
            argv.extend(["--git-pristine-tar"])

    if 'source_rpm' in args and args.source_rpm:
        argv.extend(['--git-builder=rpmbuild',
                     '--git-rpmbuild-builddir=.',
                     '--git-rpmbuild-builddir=.',
                     '--git-rpmbuild-rpmdir=.',
                     '--git-rpmbuild-sourcedir=.',
                     '--git-rpmbuild-specdir=.',
                     '--git-rpmbuild-srpmdir=.',
                     '--git-rpmbuild-buildrootdir=.',
                     '--short-circuit', '-bs',
                     ])
    else:
        argv.extend(["--git-builder=osc", "--git-export-only"])

    return argv

def export_sources(repo, commit, export_dir, spec, args, create_tarball=True):
    """
    Export packaging files using git-buildpackage
    """
    tmp = utils.Temp(prefix='gbp_', dirn=configmgr.get('tmpdir', 'general'),
                            directory=True)

    gbp_args = create_gbp_export_args(repo, commit, export_dir, tmp.path,
                                      spec, args, create_tarball=create_tarball)
    try:
        ret = gbp_build(gbp_args)
        if ret == 2 and not is_native_pkg(repo, args):
            # Try falling back to old logic of one monolithic tarball
            log.error("Generating upstream tarball and/or generating patches "
                      "failed. GBS tried this as you have upstream branch in "
                      "you git tree. Fix the problem by either:\n"
                      "  1. Update your upstream branch and/or fix the spec "
                      "file. Also, check the upstream tag format.\n"
                      "  2. Remove or rename the upstream branch (change the "
                      "package to native)\n"
                      "See https://source.tizen.org/documentation/reference/"
                      "git-build-system/upstream-package for more details.")
        if ret:
            raise GbsError("Failed to export packaging files from git tree")
    except GitRepositoryError, excobj:
        raise GbsError("Repository error: %s" % excobj)


def main(args):
    """gbs export entry point."""

    if args.commit and args.include_all:
        raise Usage("--commit can't be specified together with --include-all")

    workdir = args.gitdir
    try:
        repo = RpmGitRepository(workdir)
    except GitRepositoryError, err:
        raise GbsError(str(err))

    utils.read_localconf(repo.path)
    utils.git_status_checker(repo, args)
    workdir = repo.path


    # Only guess spec filename here, parse later when we have the correct
    # spec file at hand
    if args.commit:
        commit = args.commit
    elif args.include_all:
        commit = 'WC.UNTRACKED'
    else:
        commit = 'HEAD'
    orphan_packaging = configmgr.get('packaging_branch', 'orphan-devel')
    spec_commit_id = orphan_packaging if orphan_packaging else commit
    packaging_dir = get_packaging_dir(args)
    main_spec, rest_specs = utils.guess_spec(workdir, packaging_dir,
                                             args.spec, spec_commit_id)

    if args.outdir:
        outdir = args.outdir
    else:
        outdir = os.path.join(workdir, packaging_dir)
    outdir = os.path.abspath(outdir)
    if os.path.exists(outdir):
        if not os.access(outdir, os.W_OK|os.X_OK):
            raise GbsError('no write permission to outdir: %s' % outdir)
    else:
        mkdir_p(outdir)

    tmpdir = configmgr.get('tmpdir', 'general')
    tempd = utils.Temp(prefix=os.path.join(tmpdir, '.gbs_export_'), \
                       directory=True)
    export_dir = tempd.path

    tracked_branches = track_export_branches(repo, args)

    with utils.Workdir(workdir):
        export_sources(repo, commit, export_dir, main_spec, args)

        if rest_specs:
            # backup updated spec file
            specbakd = utils.Temp(prefix=os.path.join(tmpdir, '.gbs_export_'),
                               directory=True)
            shutil.copy(os.path.join(export_dir,
                        os.path.basename(main_spec)), specbakd.path)
            for spec in rest_specs:
                export_sources(repo, commit, export_dir, spec, args,
                               create_tarball=False)
                shutil.copy(os.path.join(export_dir,
                            os.path.basename(spec)), specbakd.path)
            # restore updated spec files
            for spec in glob.glob(os.path.join(specbakd.path, "*.spec")):
                shutil.copy(spec, export_dir)

    # Remove tracked export branches
    if tracked_branches:
        untrack_export_branches(repo, tracked_branches)

    specfile = os.path.basename(main_spec)
    try:
        spec = rpm.SpecFile(os.path.join(export_dir, specfile))
    except GbpError, err:
        raise GbsError('%s' % err)

    if not spec.name or not spec.version:
        raise GbsError('can\'t get correct name or version from spec file.')
    else:
        outdir = "%s/%s-%s-%s" % (outdir, spec.name, spec.upstreamversion,
                                  spec.release)
    if os.path.exists(outdir):
        if not os.access(outdir, os.W_OK|os.X_OK):
            raise GbsError('no permission to update outdir: %s' % outdir)
        shutil.rmtree(outdir, ignore_errors=True)

    shutil.move(export_dir, outdir)
    if args.source_rpm:
        log.info('source rpm generated to:\n     %s/%s.src.rpm' % \
                   (outdir, os.path.basename(outdir)))

    log.info('package files have been exported to:\n     %s' % outdir)
