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
import shutil
import pwd

from gitbuildsys import msger, utils, runner, errors
from gitbuildsys.conf import configmgr
from gitbuildsys.safe_url import SafeURL

from gbp.rpm.git import GitRepositoryError, RpmGitRepository

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
            'ia32':     'i586',
            'i686':     'i586',
            'i586':     'i586',
            'i386':     'i586',
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

def prepare_repos_and_build_conf(opts, arch):
    '''generate repos and build conf options for depanneur'''

    cmd_opts = []
    userid     = pwd.getpwuid(os.getuid())[0]
    tmpdir     = os.path.join(configmgr.get('tmpdir', 'general'),
                              '%s-gbs' % userid)
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
    repourls = repoparser.get_repos_by_arch(arch)
    if not repourls:
        msger.error('no available repositories found for arch %s under the '
                    'following repos:\n%s' % (arch, '\n'.join(repos)))
    cmd_opts += [('--repository=%s' % url.full) for url in repourls]

    if opts.dist:
        distconf = opts.dist
        if not os.path.exists(distconf):
            msger.error('specified build conf %s does not exists' % distconf)
    else:
        if repoparser.buildconf is None:
            msger.error('failed to get build conf from repos, please '
                        'use snapshot repo or specify build config using '
                        '-D option')
        else:
            shutil.copy(repoparser.buildconf, tmpdir)
            distconf = os.path.join(tmpdir, os.path.basename(\
                                    repoparser.buildconf))
            msger.info('build conf has been downloaded at:\n      %s' \
                       % distconf)

    if distconf is None:
        msger.error('No build config file specified, please specify in '\
                    '~/.gbs.conf or command line using -D')

    # must use abspath here, because build command will also use this path
    distconf = os.path.abspath(distconf)

    if not distconf.endswith('.conf') or '-' in os.path.basename(distconf):
        msger.error("build config file must end with .conf, and can't "
                    "contain '-'")
    dist = os.path.basename(distconf)[:-len('.conf')]
    cmd_opts += ['--dist=%s' % dist]
    cmd_opts += ['--configdir=%s' % os.path.dirname(distconf)]

    return cmd_opts

def prepare_depanneur_opts(opts):
    '''generate extra options for depanneur'''

    cmd_opts = []
    if opts.exclude:
        cmd_opts += ['--exclude=%s' % i for i in opts.exclude]
    if opts.exclude_from_file:
        cmd_opts += ['--exclude-from-file=%s' % opts.exclude_from_file]
    if opts.overwrite:
        cmd_opts += ['--overwrite']
    if opts.clean_once:
        cmd_opts += ['--clean-once']
    if opts.debug:
        cmd_opts += ['--debug']
    if opts.incremental:
        cmd_opts += ['--incremental']
    if opts.keepgoing:
        cmd_opts += ['--keepgoing']
    if opts.no_configure:
        cmd_opts += ['--no-configure']
    if opts.binary_list:
        if not os.path.exists(opts.binary_list):
            msger.error('specified binary list file %s not exists' %\
                        opts.binary_list)
        cmd_opts += ['--binary=%s' % opts.binary_list]
    cmd_opts += ['--threads=%s' % opts.threads]

    return cmd_opts

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
    """
    get arch of host
    """
    hostarch = os.uname()[4]
    if hostarch == 'i686':
        hostarch = 'i586'
    return hostarch

def find_binary_path(binary):
    """
    return full path of specified binary file
    """
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
    """
    check if binary is statically linked
    """
    return ", statically linked, " in runner.outs(['file', binary])

def setup_qemu_emulator():
    """
    setup qemu emulator env using system static qemu
    """
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


def do(opts, args):
    """
    Main of build module
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
        workdir = repo.path
    except GitRepositoryError:
        pass

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

    build_root = os.path.expanduser('~/GBS-ROOT/')
    if 'TIZEN_BUILD_ROOT' in os.environ:
        build_root = os.environ['TIZEN_BUILD_ROOT']
    if opts.buildroot:
        build_root = opts.buildroot
    os.environ['TIZEN_BUILD_ROOT'] = build_root

    # get virtual env from system env first
    if 'VIRTUAL_ENV' in os.environ:
        cmd = ['%s/usr/bin/depanneur' % os.environ['VIRTUAL_ENV']]
    else:
        cmd = ['depanneur']

    cmd += ['--arch=%s' % buildarch]

    if opts.clean:
        cmd += ['--clean']

    # check & prepare repos and build conf
    cmd += prepare_repos_and_build_conf(opts, buildarch)

    cmd += ['--path=%s' % workdir]

    if opts.ccache:
        cmd += ['--ccache']

    if opts.extra_packs:
        cmd += ['--extra-packs=%s' % opts.extra_packs]

    if hostarch != buildarch and buildarch in CHANGE_PERSONALITY:
        cmd = [ CHANGE_PERSONALITY[buildarch] ] + cmd

    if buildarch.startswith('arm'):
        try:
            setup_qemu_emulator()
        except errors.QemuError, exc:
            msger.error('%s' % exc)

    # Extra depanneur special command options
    cmd += prepare_depanneur_opts(opts)

    # Extra options for gbs export
    if opts.include_all:
        cmd += ['--include-all']
    if opts.commit:
        cmd += ['--commit=%s' % opts.commit]
    if opts.upstream_branch:
        cmd += ['--upstream-branch=%s' % opts.upstream_branch]
    if opts.upstream_tag:
        cmd += ['--upstream-tag=%s' % opts.upstream_tag]
    if opts.squash_patches_until:
        cmd += ['--squash-patches-until=%s' % opts.squash_patches_until]

    msger.debug("running command: %s" % ' '.join(cmd))
    retcode = os.system(' '.join(cmd))
    if retcode != 0:
        msger.error('rpmbuild fails')
    else:
        dist = [opt[len('--dist='):] for opt in cmd \
                                     if opt.startswith('--dist=')][0]
        repodir = os.path.join(build_root, 'local', 'repos', dist)
        msger.info('generated RPM packages can be found from local repo:'\
                   '\n     %s' % repodir)
        msger.info('build roots located in:\n     %s' % \
                   os.path.join(build_root, 'local', 'scratch.{arch}.*'))
        msger.info('Done')
