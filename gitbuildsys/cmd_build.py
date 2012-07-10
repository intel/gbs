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
import glob
import subprocess
import urlparse
import re
import tempfile
import base64

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


def get_reops_conf():

    repos = set()
    # get repo settings form build section
    for opt in configmgr.options('build'):
        if opt.startswith('repo'):
            try:
                (name, key) = opt.split('.')
            except ValueError:
                raise errors.ConfigError("invalid repo option: %s" % opt)
            else:
                if key not in ('url', 'user', 'passwdx'):
                    raise errors.ConfigError("invalid repo option: %s" % opt)
                repos.add(name)

    # get repo settings form build section
    repo_urls = []
    repo_auths = set()
    for repo in repos:
        repo_auth = ''
        # get repo url
        try:
            repo_url = configmgr.get(repo + '.url', 'build')
            repo_urls.append(repo_url)
        except:
            continue

        try:
            repo_server = re.match('(https?://.*?)/.*', repo_url).groups()[0]
        except AttributeError:
            if repo_url.startswith('/') and os.path.exists(repo_url):
                repo_server = repo_url
            else:
                raise errors.ConfigError("Invalid repo url: %s" % repo_url)
        repo_auth = 'url' + ':' + repo_server + ';'

        valid = True
        for key in ['user', 'passwdx']:
            try:
                value = configmgr.get(repo+'.'+ key, 'build').strip()
            except:
                valid = False
                break
            if not value:
                valid = False
                break
            repo_auth = repo_auth + key + ':' + value + ';'

        if not valid:
            continue
        repo_auth = repo_auth[:-1]
        repo_auths.add(repo_auth)

    return repo_urls, ' '.join(repo_auths)

def do(opts, args):

    workdir = os.getcwd()
    if len(args) > 1:
        msger.error('only one work directory can be specified in args.')
    if len(args) == 1:
        workdir = os.path.abspath(args[0])

    try:
        repo = RpmGitRepository(workdir)
        if opts.commit:
            repo.rev_parse(opts.commit)
    except GitRepositoryError, err:
        msger.error(str(err))

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
    build_root = os.path.join(tmpdir, userid, 'gbs-builroot.%s' % buildarch)
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

    repos_urls_conf, repo_auth_conf = get_reops_conf()

    repos = {}
    if opts.repositories:
        for repourl in opts.repositories:
            (scheme, host, path, parm, query, frag) = \
                                    urlparse.urlparse(repourl.rstrip('/') + '/')
            repos[repourl] = {}
            if '@' in host:
                try:
                    user_pass, host = host.rsplit('@', 1)
                except ValueError, e:
                    raise errors.ConfigError('Bad URL: %s' % repourl)
                userpwd = user_pass.split(':', 1)
                repos[repourl]['user'] = userpwd[0]
                if len(userpwd) == 2:
                    repos[repourl]['passwd'] = userpwd[1]
                else:
                    repos[repourl]['passwd'] = None
            else:
                repos[repourl]['user'] = None
                repos[repourl]['passwd'] = None

    elif repos_urls_conf:
        for url in repos_urls_conf:
            repos[url] = {}
            if repo_auth_conf:
                repo_auth = {}
                for item in repo_auth_conf.split(';'):
                    key, val = item.split(':', 1)
                    if key == 'passwdx':
                        key = 'passwd'
                        try:
                            val = base64.b64decode(val).decode('bz2')
                        except (TypeError, IOError), err:
                            raise errors.ConfigError('passwdx: %s' % err)
                    repo_auth[key] = val
                if 'user' in repo_auth:
                    repos[url]['user'] = repo_auth['user']
                if 'passwd' in repo_auth:
                    repos[url]['passwd'] = repo_auth['passwd']
            else:
                    repos[url]['passwd'] = None
                    repos[url]['user'] = None
    else:
        msger.error('No package repository specified.')

    if opts.noinit:
        cmd += ['--no-init']
    else:
        # check & prepare repos and build conf if no noinit option
        cachedir = os.path.join(configmgr.get('tmpdir'), 'gbscache')
        if not os.path.exists(cachedir):
            os.makedirs(cachedir)
        msger.info('generate repositories ...')
        repoparser = utils.RepoParser(repos, cachedir)
        repourls = repoparser.get_repos_by_arch(buildarch)
        if not repourls:
            msger.error('no repositories found for arch: %s under the ' \
                        'following repos:\n      %s' % (buildarch,      \
                        '\n'.join(repos.keys())))
        for url in repourls:
            cmd += ['--repository=%s' % url]

        if opts.dist:
            distconf = opts.dist
        else:
            distconf = repoparser.buildconf
            if distconf is None:
                msger.info('failed to get build conf, use default build conf')
                distconf = configmgr.get('distconf', 'build')
            else:
                msger.info('build conf has been downloaded at:\n      %s'
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
        except errors.QemuError, exc:
            msger.error('%s' % exc)

    # Only guess spec filename here, parse later when we have the correct
    # spec file at hand
    specfile = utils.guess_spec(workdir, opts.spec)
    packaging_dir = os.path.join(workdir, 'packaging/')
    export_dir = tempfile.mkdtemp(prefix=packaging_dir + 'build_')
    with utils.Workdir(workdir):
        relative_spec = specfile.replace('%s/' % workdir, '')
        commit = opts.commit or 'HEAD'
        msger.info('export tar ball and packaging files ... ')
        try:
            if gbp_build(["argv[0] placeholder", "--git-export-only",
                          "--git-ignore-new", "--git-builder=osc",
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
    if os.getuid() == 0:
        os.environ['GBS_BUILD_REPOAUTH'] = repo_auth_conf
    else:
        cmd = ['sudo'] + proxies + ['GBS_BUILD_REPOAUTH=%s' % \
              repo_auth_conf ] + cmd

    cmd += [os.path.join(export_dir, os.path.basename(specfile))]
    # runner.show() can't support interactive mode, so use subprocess insterad.
    msger.debug("running command %s" % cmd)
    try:
        if subprocess.call(cmd):
            msger.error('rpmbuild fails')
        else:
            msger.info('The buildroot was: %s' % build_root)
            msger.info('Binaries RPM packges can be found here:\n     %s/%s' % \
                       (build_root, 'home/abuild/rpmbuild/RPMS/'))
            msger.info('Done')
    except KeyboardInterrupt:
        msger.info('keyboard interrupt, killing build ...')
        subprocess.call(cmd + ["--kill"])
        msger.error('interrrupt from keyboard')
    finally:
        import shutil
        shutil.rmtree(export_dir, ignore_errors=True)
