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
import re
import subprocess
import tempfile
import urllib2
import glob
import shutil
import base64
from urlparse import urlsplit, urlunsplit

import msger
import utils
import runner
import errors
from conf import configmgr

from gbp.scripts.buildpackage_rpm import main as gbp_build
from gbp.rpm.git import GitRepositoryError, RpmGitRepository
import gbp.rpm as rpm
from gbp.errors import GbpError

change_personality = {
            'i686':  'linux32',
            'i586':  'linux32',
            'i386':  'linux32',
            'ppc':   'powerpc32',
            's390':  's390',
            'sparc': 'linux32',
            'sparcv8': 'linux32',
          }

obsarchmap = {
            'i686':     'i586',
            'i586':     'i586',
          }

buildarchmap = {
            'ia32':     'i686',
            'i686':     'i686',
            'i586':     'i686',
            'i386':     'i686',
          }

supportedarchs = [
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
        qemu_arm_string = ":arm:M::\\x7fELF\\x01\\x01\\x01\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x02\\x00\\x28\\x00:\\xff\\xff\\xff\\xff\\xff\\xff\\xff\\x00\\xff\\xff\\xff\\xff\\xff\\xff\\xff\\xff\\xfa\\xff\\xff\\xff:%s:" % qemu_emulator
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


def get_repos_conf():
    """
    Make list of urls using repox.url, repox.user and repox.passwd
    configuration file parameters from 'build' section.
    Validate configuration parameters.
    """

    repos = {}
    # get repo settings form build section
    for opt in configmgr.options('build'):
        if opt.startswith('repo'):
            try:
                key, name = opt.split('.')
            except ValueError:
                raise errors.ConfigError("invalid repo option: %s" % opt)

            if name not in ('url', 'user', 'passwdx'):
                raise errors.ConfigError("invalid repo option: %s" % opt)

            if key not in repos:
                repos[key] = {}

            if name in repos[key]:
                raise errors.ConfigError('Duplicate entry %s' % opt)

            value = configmgr.get(opt, 'build')
            if name == 'passwdx':
                try:
                    value = base64.b64decode(value).decode('bz2')
                except (TypeError, IOError), err:
                    raise errors.ConfigError('Error decoding %s: %s' % \
                                             (opt, err))
                repos[key]['passwd'] = urllib2.quote(value, safe='')
            else:
                repos[key][name] = value

    result = []
    for key, item in repos.iteritems():
        if 'url' not in item:
            raise errors.ConfigError("Url is not specified for %s" % key)

        splitted = urlsplit(item['url'])
        if splitted.username and item['user'] or \
           splitted.password and item['passwd']:
            raise errors.ConfigError("Auth info specified twice for %s" % key)

        # Get auth info from the url or urlx.user and urlx.pass
        user = item.get('user') or splitted.username
        passwd = item.get('passwd') or splitted.password

        splitted_list = list(splitted)
        if user:
            if passwd:
                splitted_list[1] = '%s:%s@%s' % (urllib2.quote(user, safe=''),
                                                 passwd, splitted.hostname)
            else:
                splitted_list[1] = '%s@%s' % (urllib2.quote(user, safe=''),
                                              splitted.hostname)
        elif passwd:
            raise errors.ConfigError('No user is specified for %s, '\
                                     'only password' % key)

        result.append(urlunsplit(splitted_list))

    return result

def clean_repos_userinfo(repos):
    striped_repos = []
    for repo in repos:
        splitted = urlsplit(repo)
        if not splitted.username:
            striped_repos.append(repo)
        else:
            splitted_list = list(splitted)
            if splitted.port:
                splitted_list[1] = '%s:%d' % (splitted.hostname, splitted.port)
            else:
                splitted_list[1] = splitted.hostname
            striped_repos.append(urlunsplit(splitted_list))

    return striped_repos

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

    if not opts.incremental:
        utils.gitStatusChecker(repo, opts)
    workdir = repo.path

    hostarch = get_hostarch()
    if opts.arch:
        buildarch = opts.arch
    else:
        buildarch = hostarch
        msger.info('No arch specified, using system arch: %s' % hostarch)
    if buildarch in buildarchmap:
        buildarch = buildarchmap[buildarch]

    if not buildarch in supportedarchs:
        msger.error('arch %s not supported, supported archs are: %s ' % \
                   (buildarch, ','.join(supportedarchs)))

    build_cmd  = configmgr.get('build_cmd', 'build')
    userid     = configmgr.get('user', 'remotebuild')
    tmpdir     = configmgr.get('tmpdir', 'general')
    build_root = os.path.join(tmpdir, userid, 'gbs-buildroot.%s' % buildarch)
    if opts.buildroot:
        build_root = opts.buildroot
    cmd = [ build_cmd,
            '--root='+build_root,
            '--arch='+buildarch ]

    build_jobs = get_processors()
    if build_jobs > 1:
        cmd += ['--jobs=%s' % build_jobs]
    if opts.clean:
        cmd += ['--clean']
    if opts.debuginfo:
        cmd += ['--debug']

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
            repos = get_repos_conf()

        if opts.repositories:
            repos.extend(opts.repositories)
        if not repos:
            msger.error('No package repository specified.')

        repoparser = utils.RepoParser(repos, cachedir)
        repourls = repoparser.get_repos_by_arch(buildarch)
        if not repourls:
            msger.error('no repositories found for arch: %s under the '\
                        'following repos:\n      %s' % \
                        (buildarch, '\n'.join(clean_repos_userinfo(repos))))
        for url in repourls:
            if not  re.match('https?://.*', url) and \
               not (url.startswith('/') and os.path.exists(url)):
                msger.error("Invalid repo url: %s" % url)
            cmd += ['--repository=%s' % url]

        if opts.dist:
            distconf = opts.dist
        else:
            if repoparser.buildconf is None:
                msger.info('failed to get build conf, use default build conf')
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

    if hostarch != buildarch and buildarch in change_personality:
        cmd = [ change_personality[buildarch] ] + cmd

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
        try:
            if gbp_build(["argv[0] placeholder", "--git-export-only",
                          "--git-ignore-new", "--git-builder=osc",
                          "--git-no-auto-patch-gen",
                          "--git-upstream-tree=%s" % commit,
                          "--git-export-dir=%s" % export_dir,
                          "--git-packaging-dir=packaging",
                          "--git-specfile=%s" % relative_spec,
                          "--git-export=%s" % commit]):
                msger.error("Failed to get packaging info from git tree")
        except GitRepositoryError, excobj:
            msger.error("Repository error: %s" % excobj)

    # Parse spec file
    try:
        spec = rpm.parse_spec(os.path.join(export_dir, os.path.basename(specfile)))
    except GbpError, err:
        msger.error('%s' % err)

    if not spec.name or not spec.version:
        msger.error('can\'t get correct name or version from spec file.')

    cmd += [spec.specfile]

    if opts.incremental:
        cmd += ['--rsync-src=%s' % os.path.abspath(workdir)]
        cmd += ['--rsync-dest=/home/abuild/rpmbuild/BUILD/%s-%s' % \
                (spec.name, spec.version)]

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
            msger.info('The buildroot was: %s' % build_root)
            msger.info('Binaries RPM packages can be found here:'\
                       '\n     %s' % out_dir)
            msger.info('Done')
    except KeyboardInterrupt:
        msger.info('keyboard interrupt, killing build ...')
        subprocess.call(cmd + ["--kill"])
        msger.error('interrupt from keyboard')
