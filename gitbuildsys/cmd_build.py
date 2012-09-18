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

"""Implementation of subcmd: localbuild
"""

import os
import subprocess
import tempfile
import glob
import shutil
import pwd

from gitbuildsys import msger, utils, runner, errors
from gitbuildsys.conf import configmgr
from gitbuildsys.safe_url import SafeURL
from gitbuildsys.cmd_export import export_sources

from gbp.rpm.git import GitRepositoryError, RpmGitRepository
import gbp.rpm as rpm
from gbp.errors import GbpError

CHANGE_PERSONALITY = {
            'i686':  'linux32',
            'i586':  'linux32',
            'i386':  'linux32',
            'ppc':   'powerpc32',
            's390':  's390',
            'sparc': 'linux32',
            'sparcv8': 'linux32',
          }

BUILDARCHMAP = {
            'ia32':     'i686',
            'i686':     'i686',
            'i586':     'i686',
            'i386':     'i686',
          }

SUPPORTEDARCHS = [
            'ia32',
            'i686',
            'i586',
            'armv7hl',
            'armv7el',
            'armv7tnhl',
            'armv7nhl',
            'armv7l',
          ]

def get_processors():
    """
    get number of processors (online) based on
    SC_NPROCESSORS_ONLN (returns 1 if config name does not exist).
    """
    try:
        return os.sysconf('SC_NPROCESSORS_ONLN')
    except ValueError:
        return 1

def get_hostarch():
    hostarch = os.uname()[4]
    if hostarch == 'i686':
        hostarch = 'i586'
    return hostarch

def find_binary_path(binary):
    if os.environ.has_key("PATH"):
        paths = os.environ["PATH"].split(":")
    else:
        paths = []
        if os.environ.has_key("HOME"):
            paths += [os.environ["HOME"] + "/bin"]
        paths += ["/usr/local/sbin", "/usr/local/bin", "/usr/sbin",
                  "/usr/bin", "/sbin", "/bin"]

    for path in paths:
        bin_path = "%s/%s" % (path, binary)
        if os.path.exists(bin_path):
            return bin_path
    return None

def is_statically_linked(binary):
    return ", statically linked, " in runner.outs(['file', binary])

def setup_qemu_emulator():
    # mount binfmt_misc if it doesn't exist
    if not os.path.exists("/proc/sys/fs/binfmt_misc"):
        modprobecmd = find_binary_path("modprobe")
        runner.show([modprobecmd, "binfmt_misc"])
    if not os.path.exists("/proc/sys/fs/binfmt_misc/register"):
        mountcmd = find_binary_path("mount")
        runner.show([mountcmd, "-t", "binfmt_misc", "none",
                     "/proc/sys/fs/binfmt_misc"])

    # qemu_emulator is a special case, we can't use find_binary_path
    # qemu emulator should be a statically-linked executable file
    qemu_emulator = "/usr/bin/qemu-arm"
    if not os.path.exists(qemu_emulator) or \
           not is_statically_linked(qemu_emulator):
        qemu_emulator = "/usr/bin/qemu-arm-static"
    if not os.path.exists(qemu_emulator):
        raise errors.QemuError("Please install a statically-linked qemu-arm")

    # disable selinux, selinux will block qemu emulator to run
    if os.path.exists("/usr/sbin/setenforce"):
        msger.info('Try to disable selinux')
        runner.show(["/usr/sbin/setenforce", "0"])

    node = "/proc/sys/fs/binfmt_misc/arm"
    if is_statically_linked(qemu_emulator) and os.path.exists(node):
        return qemu_emulator

    # unregister it if it has been registered and
    # is a dynamically-linked executable
    # FIXME: fix permission issue if qemu-arm dynamically used
    if not is_statically_linked(qemu_emulator) and os.path.exists(node):
        qemu_unregister_string = "-1\n"
        fds = open("/proc/sys/fs/binfmt_misc/arm", "w")
        fds.write(qemu_unregister_string)
        fds.close()

    # register qemu emulator for interpreting other arch executable file
    if not os.path.exists(node):
        qemu_arm_string = ":arm:M::\\x7fELF\\x01\\x01\\x01\\x00\\x00\\x00\\x00"\
                          "\\x00\\x00\\x00\\x00\\x00\\x02\\x00\\x28\\x00:\\xff"\
                          "\\xff\\xff\\xff\\xff\\xff\\xff\\x00\\xff\\xff\\xff"\
                          "\\xff\\xff\\xff\\xff\\xff\\xfa\\xff\\xff\\xff:%s:" \
                          % qemu_emulator
        try:
            (tmpfd, tmppth) = tempfile.mkstemp()
            os.write(tmpfd, "echo '%s' > /proc/sys/fs/binfmt_misc/register" \
                                % qemu_arm_string)
            os.close(tmpfd)
            # on this way can work to use sudo register qemu emulator
            ret = os.system('sudo sh %s' % tmppth)
            if ret != 0:
                raise errors.QemuError('failed to set up qemu arm environment')
        except IOError:
            raise errors.QemuError('failed to set up qemu arm environment')
        finally:
            os.unlink(tmppth)

    return qemu_emulator

def get_env_proxies():
    proxies = []
    for name, value in os.environ.items():
        name = name.lower()
        if value and name.endswith('_proxy'):
            proxies.append('%s=%s' % (name, value))
    return proxies


def do(opts, args):

    workdir = os.getcwd()
    if len(args) > 1:
        msger.error('only one work directory can be specified in args.')
    if len(args) == 1:
        workdir = os.path.abspath(args[0])

    if opts.commit and opts.include_all:
        raise errors.Usage('--commit can\'t be specified together with '\
                           '--include-all')

    if opts.out:
        if not os.path.exists(opts.out):
            msger.error('Output directory %s doesn\'t exist' % opts.out)
        if not os.path.isdir(opts.out):
            msger.error('%s is not a directory' % opts.out)

    try:
        repo = RpmGitRepository(workdir)
    except GitRepositoryError, err:
        msger.error(str(err))

    utils.git_status_checker(repo, opts)
    workdir = repo.path

    hostarch = get_hostarch()
    if opts.arch:
        buildarch = opts.arch
    else:
        buildarch = hostarch
        msger.info('No arch specified, using system arch: %s' % hostarch)
    if buildarch in BUILDARCHMAP:
        buildarch = BUILDARCHMAP[buildarch]

    if not buildarch in SUPPORTEDARCHS:
        msger.error('arch %s not supported, supported archs are: %s ' % \
                   (buildarch, ','.join(SUPPORTEDARCHS)))

    build_cmd  = configmgr.get('build_cmd', 'build')
    userid     = pwd.getpwuid(os.getuid())[0]
    tmpdir = os.path.join(configmgr.get('tmpdir', 'general'), "%s-gbs" % userid)
    build_root = os.path.join(tmpdir, 'gbs-buildroot.%s' % buildarch)
    if opts.buildroot:
        build_root = opts.buildroot
    cmd = [ build_cmd,
            '--root='+build_root,
            '--arch='+buildarch ]

    if os.path.exists(os.path.join(build_root, 'not-ready')):
        cmd += ['--clean']

    build_jobs = get_processors()
    if build_jobs > 1:
        cmd += ['--jobs=%s' % build_jobs]
    if opts.clean and '--clean' not in cmd:
        cmd += ['--clean']

    if opts.noinit:
        cmd += ['--no-init']
    else:
        # check & prepare repos and build conf if no noinit option
        cache = utils.Temp(prefix=os.path.join(tmpdir, 'gbscache'),
                           directory=True)
        cachedir  = cache.path
        if not os.path.exists(cachedir):
            os.makedirs(cachedir)
        msger.info('generate repositories ...')

        if opts.skip_conf_repos:
            repos = []
        else:
            repos = [i.url for i in configmgr.get_current_profile().repos]

        if opts.repositories:
            for i in opts.repositories:
                try:
                    opt_repo = SafeURL(i)
                except ValueError, err:
                    msger.warning('Invalid repo %s: %s' % (i, str(err)))
                else:
                    repos.append(opt_repo)

        if not repos:
            msger.error('No package repository specified.')

        repoparser = utils.RepoParser(repos, cachedir)
        repourls = repoparser.get_repos_by_arch(buildarch)
        if not repourls:
            msger.error('no available repositories found for arch %s under the '
                        'following repos:\n%s' % (buildarch, '\n'.join(repos)))
        cmd += [('--repository=%s' % url.full) for url in repourls]

        if opts.dist:
            distconf = opts.dist
        else:
            if repoparser.buildconf is None:
                msger.warning('failed to get build conf, '
                              'use default build conf')
                distconf = configmgr.get('distconf', 'build')
            else:
                shutil.copy(repoparser.buildconf, tmpdir)
                distconf = os.path.join(tmpdir, os.path.basename(\
                                        repoparser.buildconf))
                msger.info('build conf has been downloaded at:\n      %s' \
                           % distconf)

        if distconf is None:
            msger.error('No build config file specified, please specify in '\
                        '~/.gbs.conf or command line using -D')
        cmd += ['--dist=%s' % distconf]

    if opts.ccache:
        cmd += ['--ccache']

    if opts.extra_packs:
        extrapkgs = opts.extra_packs.split(',')
        cmd += ['--extra-packs=%s' % ' '.join(extrapkgs)]

    if hostarch != buildarch and buildarch in CHANGE_PERSONALITY:
        cmd = [ CHANGE_PERSONALITY[buildarch] ] + cmd

    proxies = get_env_proxies()

    if buildarch.startswith('arm'):
        try:
            setup_qemu_emulator()
            cmd += ['--use-system-qemu']
        except errors.QemuError, exc:
            msger.error('%s' % exc)

    # Only guess spec filename here, parse later when we have the correct
    # spec file at hand
    specfile = utils.guess_spec(workdir, opts.spec)
    tmpd = utils.Temp(prefix=os.path.join(tmpdir, '.gbs_build'), directory=True)
    export_dir = tmpd.path
    with utils.Workdir(workdir):
        if opts.commit:
            commit = opts.commit
        elif opts.include_all:
            commit = 'WC.UNTRACKED'
        else:
            commit = 'HEAD'
        relative_spec = specfile.replace('%s/' % workdir, '')
        msger.info('export tar ball and packaging files ... ')
        export_sources(repo, commit, export_dir, relative_spec, opts)

    # Parse spec file
    try:
        spec = rpm.parse_spec(os.path.join(export_dir,
                                           os.path.basename(specfile)))
    except GbpError, err:
        msger.error('%s' % err)

    if not spec.name or not spec.version:
        msger.error('can\'t get correct name or version from spec file.')

    cmd += [spec.specfile]

    # if current user is root, don't run with sucmd
    if os.getuid() != 0:
        cmd = ['sudo'] + proxies + cmd

    # runner.show() can't support interactive mode, so use subprocess insterad.
    msger.debug("running command %s" % cmd)
    try:
        if subprocess.call(cmd):
            msger.error('rpmbuild fails')
        else:
            out_dir = os.path.join(build_root, 'home/abuild/rpmbuild/RPMS/')
            if opts.out:
                for fpath in glob.glob(out_dir + '/*/*.rpm'):
                    shutil.copy(fpath, opts.out)
                msger.info('RPMs have been copied from %s to %s' \
                           % (out_dir, opts.out))
                out_dir = os.path.abspath(opts.out)
                subprocess.call(["createrepo", out_dir])
                msger.info("RPM repo has been created: %s" % out_dir)
            msger.info('The buildroot was: %s' % build_root)
            msger.info('Binaries RPM packages can be found here:'\
                       '\n     %s' % out_dir)
            msger.info('Done')
    except KeyboardInterrupt:
        msger.info('keyboard interrupt, killing build ...')
        subprocess.call(cmd + ["--kill"])
        msger.error('interrupt from keyboard')
