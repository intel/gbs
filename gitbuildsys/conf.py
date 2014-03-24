#!/usr/bin/python -tt
# vim: ai ts=4 sts=4 et sw=4
#
# Copyright (c) 2011 Intel, Inc.
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
'''
Provides classes and functions to read and write gbs.conf.
'''

from __future__ import with_statement
import os
import re
import base64
import shutil
from collections import namedtuple
from ConfigParser import SafeConfigParser, NoSectionError, \
                         MissingSectionHeaderError, Error

from gitbuildsys import errors
from gitbuildsys.safe_url import SafeURL
from gitbuildsys.utils import Temp
from gitbuildsys.log import LOGGER as log

def decode_passwdx(passwdx):
    '''decode passwdx into plain format'''
    return base64.b64decode(passwdx).decode('bz2')


def encode_passwd(passwd):
    '''encode passwd by bz2 and base64'''
    return base64.b64encode(passwd.encode('bz2'))


class BrainConfigParser(SafeConfigParser):
    """Standard ConfigParser derived class which can reserve most of the
    comments, indents, and other user customized stuff inside the ini file.
    """

    def read_one(self, filename):
        """only support one input file"""
        return SafeConfigParser.read(self, filename)

    def _read(self, fptr, fname):
        """Parse a sectioned setup file.

        Override the same method of parent class.

        Customization: save filename and file contents
        """

        # save the original filepath and contents
        self._fpname = fname
        self._flines = fptr.readlines()
        fptr.seek(0)

        return SafeConfigParser._read(self, fptr, fname)

    def _set_into_file(self, section, option, value, replace_opt=None):
        """Set the value in the file contents

        Parsing logic and lot of the code was copied directly from the
        ConfigParser module of Python standard library.
        """
        cursect = None                        # None, or a str
        optname = None
        new_line = '%s = %s\n' % (option, value)
        new_line_written = False
        last_section_line = None

        for lineno in range(len(self._flines)):
            line = self._flines[lineno]
            # We might have 'None' lines because of earlier updates
            if line is None:
                continue

            # comment or blank line?
            if line.strip() == '' or line[0] in '#;':
                continue
            if line.split(None, 1)[0].lower() == 'rem' and line[0] in "rR":
                # no leading whitespace
                continue
            # continuation line?
            if line[0].isspace() and cursect == section and \
                (optname == option or optname == replace_opt):
                self._flines[lineno] = None
            else:
                # is it a section header?
                match = self.SECTCRE.match(line)
                if match:
                    cursect = match.group('header')
                    # So sections can't start with a continuation line
                    optname = None
                # no section header in the file?
                elif cursect is None:
                    raise MissingSectionHeaderError(self._fpname,
                                                    lineno + 1, line)
                # an option line?
                else:
                    match = self.OPTCRE.match(line)
                    if match:
                        optname = match.group('option')
                        optname = self.optionxform(optname.rstrip())
                        # Replace / remove options
                        if cursect == section and \
                           (optname == option or optname == replace_opt):
                            if not new_line_written:
                                self._flines[lineno] = new_line
                                new_line_written = True
                            else:
                                # Just remove all matching lines, if we've
                                # already written the new value
                                self._flines[lineno] = None
                    # Just ignore non-fatal parsing errors

            # Save the last line of the matching section
            if cursect == section:
                last_section_line = lineno

        # Insert new key
        if not new_line_written:
            if last_section_line is not None:
                self._flines.insert(last_section_line + 1, new_line)
            else:
                self._flines.insert(lineno + 1, '\n')
                self._flines.insert(lineno + 2, '[%s]\n' % section)
                self._flines.insert(lineno + 3, new_line)

    def set_into_file(self, section, option, value, replace_opt=None):
        """When set new value, need to update the readin file lines,
        which can be saved back to file later.
        """
        if not self.has_section(section):
            self.add_section(section)
        SafeConfigParser.set(self, section, option, value)
        if replace_opt:
            SafeConfigParser.remove_option(self, section, replace_opt)

        # If the code reach here, it means the section and key are ok
        try:
            self._set_into_file(section, option, value, replace_opt)
        except Exception as err:
            # This really shouldn't happen, we've already once parsed the file
            # contents successfully.
            raise errors.ConfigError('BUG: ' + str(err))

    def update(self):
        """Update the original config file using updated values"""

        if self._fpname == '<???>':
            return

        with open(self._fpname, 'w') as fptr:
            buf = ''.join([line for line in self._flines if line is not None ])
            fptr.write(buf)


class ConfigMgr(object):
    '''Support multi-levels of gbs.conf. Use this class to get and set
    item value without caring about concrete ini format'''

    DEFAULTS = {
            'general': {
                'tmpdir': '/var/tmp',
                'editor': '',
                'packaging_branch': 'master',
                'upstream_branch': 'upstream',
                'upstream_tag': 'upstream/${upstreamversion}',
                'squash_patches_until': '',
                'buildroot':    '~/GBS-ROOT/',
                'packaging_dir': 'packaging',
                'work_dir': '.',
            },
    }

    DEFAULT_CONF_TEMPLATE = '''[general]
#Current profile name which should match a profile section name
profile = profile.tizen

[profile.tizen]
#Common authentication info for whole profile
#user =
#CAUTION: please use the key name "passwd" to reset plaintext password
#passwd =
obs = obs.tizen
#Comma separated list of repositories
repos = repo.tizen_latest
#repos = repo.tizen_main, repo.tizen_base

[obs.tizen]
#OBS API URL pointing to a remote OBS.
url = https://api.tizen.org
#Optional user and password, set if differ from profile's user and password
#user =
#passwd =

#Repo section example
[repo.tizen_latest]
#Build against repo's URL
url = http://download.tizen.org/releases/daily/trunk/ivi/latest/
#Optional user and password, set if differ from profile's user and password
#user =
#passwd =

#Individual repo is also supported
#[repo.tizen_base]
#url = http://download.tizen.org/releases/daily/trunk/ivi/latest/repos/base/ia32/packages/
#[repo.tizen_main]
#url = http://download.tizen.org/releases/daily/trunk/ivi/latest/repos/ivi/ia32/packages/
'''

    # make the manager class as singleton
    _instance = None
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(ConfigMgr, cls).__new__(cls, *args, **kwargs)

        return cls._instance

    def __init__(self, fpath=None):
        self._cfgfiles = []
        self._cfgparsers = []
        if fpath:
            if not os.path.exists(fpath):
                raise errors.ConfigError('Configuration file %s does not '\
                                         'exist' % fpath)
            self._cfgfiles.append(fpath)

        # find the default path
        fpaths = self._lookfor_confs()
        if not fpaths:
            self._new_conf()
            fpaths = self._lookfor_confs()
        self._cfgfiles.extend(fpaths)

        self.load_confs()

    def _create_default_parser(self):
        'create a default parser that handle DEFAULTS values'
        parser = BrainConfigParser()
        for sec, options in self.DEFAULTS.iteritems():
            parser.add_section(sec)
            for key, val in options.iteritems():
                parser.set(sec, key, val)
        return parser

    def load_confs(self):
        'reset all config values by files passed in'

        self._cfgparsers = []
        for fpath in self._cfgfiles:
            cfgparser = BrainConfigParser()
            try:
                cfgparser.read_one(fpath)
                if cfgparser.has_section('general') and \
                   cfgparser.has_option('general', 'work_dir') and \
                   cfgparser.get('general', 'work_dir') == '.':
                    cfgparser.set('general', 'work_dir',
                                  os.path.abspath(os.path.dirname(fpath)))
            except Error, err:
                raise errors.ConfigError('config file error:%s' % err)
            self._cfgparsers.append(cfgparser)
        self._cfgparsers.append(self._create_default_parser())

        self._check_passwd()

    def add_conf(self, fpath):
        """ Add new config to configmgr, and new added config file has
            highest priority
        """
        if not fpath:
            return
        if not os.path.exists(fpath):
            raise errors.ConfigError('Configuration file %s does not '\
                                     'exist' % fpath)
        # new added conf has highest priority
        self._cfgfiles.insert(0, fpath)
        # reload config files
        self.load_confs()

    @staticmethod
    def _lookfor_confs():
        """Look for available config files following the order:
            > Current project
            > User
            > System
        """

        paths = []

        def lookfor_tizen_conf(start_dir):
            """ Search topdir of tizen source code cloned using repo tool,
            if .gbs.conf exists under that dir, then return it
            """
            cur_dir = os.path.abspath(start_dir)
            while True:
                if os.path.exists(os.path.join(cur_dir, '.repo')) and \
                   os.path.exists(os.path.join(cur_dir, '.gbs.conf')):
                    return os.path.join(cur_dir, '.gbs.conf')
                if cur_dir == '/':
                    break
                cur_dir = os.path.dirname(cur_dir)

            return None

        tizen_conf = lookfor_tizen_conf(os.getcwd())
        if tizen_conf:
            paths.append(tizen_conf)
        for path in (os.path.abspath('.gbs.conf'),
                     os.path.expanduser('~/.gbs.conf'),
                     '/etc/gbs.conf'):
            if os.path.exists(path) and path not in paths:
                paths.append(path)

        return paths

    def _new_conf(self):
        'generate a default conf file in home dir'
        fpath = os.path.expanduser('~/.gbs.conf')

        with open(fpath, 'w') as wfile:
            wfile.write(self.DEFAULT_CONF_TEMPLATE)
        os.chmod(fpath, 0600)

        log.warning('Created a new config file %s. Please check and edit '
                    'your authentication information.' % fpath)

    def _check_passwd(self):
        'convert passwd item to passwdx and then update origin conf files'
        dirty = set()

        all_sections = set()
        for layer in self._cfgparsers:
            for sec in layer.sections():
                all_sections.add(sec)

        for sec in all_sections:
            for key in self.options(sec):
                if key.endswith('passwd'):
                    for cfgparser in self._cfgparsers:
                        if cfgparser.has_option(sec, key):
                            plainpass = cfgparser.get(sec, key)
                            if plainpass is None:
                                # empty string password is acceptable here
                                continue
                            cfgparser.set_into_file(sec,
                                     key + 'x',
                                     encode_passwd(plainpass),
                                     key)
                            dirty.add(cfgparser)

        if dirty:
            log.warning('plaintext password in config files will '
                        'be replaced by encoded ones')
            self.update(dirty)

    def _get(self, opt, section='general'):
        'get value from multi-levels of config file'
        for cfgparser in self._cfgparsers:
            try:
                return cfgparser.get(section, opt)
            except Error, err:
                pass
        raise errors.ConfigError(err)

    def options(self, section='general'):
        'merge and return options of certain section from multi-levels'
        sect_found = False
        options = set()
        for cfgparser in self._cfgparsers:
            try:
                options.update(cfgparser.options(section))
                sect_found = True
            except Error, err:
                pass

        if not sect_found:
            raise errors.ConfigError(err)

        return options

    def has_section(self, section):
        'indicate whether a section exists'
        for parser in self._cfgparsers:
            if parser.has_section(section):
                return True
        return False

    def get(self, opt, section='general'):
        'get item value. return plain text of password if item is passwd'
        if opt == 'passwd':
            val = self._get('passwdx', section)
            try:
                return decode_passwdx(val)
            except (TypeError, IOError), err:
                raise errors.ConfigError('passwdx:%s' % err)
        else:
            return self._get(opt, section)

    def get_arg_conf(self, args, opt, section='general'):
        """get value from command line arguments if found there, otherwise fall
           back to config
        """
        if hasattr(args, opt):
            value = getattr(args, opt)
            if value is not None:
                return value
        return self.get(opt, section)

    @staticmethod
    def update(cfgparsers):
        'update changed values into files on disk'
        for cfgparser in cfgparsers:
            try:
                cfgparser.update()
            except IOError, err:
                log.warning('update config file error: %s' % err)


URL = namedtuple('URL', 'url user password')


class SectionConf(object):
    """Config items related to obs and repo sections."""

    def __init__(self, parent, name, url, base=None, target=None):
        self.parent = parent
        self.name = name
        self.base = base
        self.target = target

        user = url.user or parent.common_user
        password = url.password or parent.common_password
        try:
            self.url = SafeURL(url.url, user, password)
        except ValueError, err:
            raise errors.ConfigError('%s for %s' % (str(err), url.url))

    def dump(self, fhandler):
        """Dump ini to file object."""
        parser = BrainConfigParser()
        parser.add_section(self.name)

        parser.set(self.name, 'url', self.url)

        if self.url.user and self.url.user != self.parent.common_user:
            parser.set(self.name, 'user', self.url.user)

        if self.url.passwd and self.url.passwd != self.parent.common_password:
            parser.set(self.name, 'passwdx',
                       encode_passwd(self.url.passwd))

        if self.base:
            parser.set(self.name, 'base_prj', self.base)

        if self.target:
            parser.set(self.name, 'target_prj', self.target)
        parser.write(fhandler)


class Profile(object):
    '''Profile which contains all config values related to same domain'''

    def __init__(self, name, user, password):
        self.name = name
        self.common_user = user
        self.common_password = password
        self.repos = []
        self.obs = None
        self.buildroot = None
        self.buildconf = None

    def add_repo(self, repoconf):
        '''add a repo to repo list of the profile'''
        self.repos.append(repoconf)

    def set_obs(self, obsconf):
        '''set OBS api of the profile'''
        self.obs = obsconf

    def dump(self, fhandler):
        'dump ini to file object'
        parser = BrainConfigParser()
        parser.add_section(self.name)

        if self.common_user:
            parser.set(self.name, 'user', self.common_user)
        if self.common_password:
            parser.set(self.name, 'passwdx',
                       encode_passwd(self.common_password))
        if self.buildroot:
            parser.set(self.name, 'buildroot', self.buildroot)

        if self.obs:
            parser.set(self.name, 'obs', self.obs.name)
            self.obs.dump(fhandler)

        if self.repos:
            names = []
            for repo in self.repos:
                names.append(repo.name)
                repo.dump(fhandler)
            parser.set(self.name, 'repos', ', '.join(names))
        parser.write(fhandler)


class BizConfigManager(ConfigMgr):
    '''config manager which handles high level conception, such as profile info
    '''


    def _interpolate(self, value):
        '''do string interpolation'''

        general_keys = {}

        for opt in self.DEFAULTS['general']:
            if opt == 'work_dir' and self.get(opt, 'general') == '.':
                general_keys[opt] = os.getcwd()
            else:
                general_keys[opt] = self.get(opt, 'general')

        value = re.sub(r'\$\{([^}]+)\}', r'%(\1)s', value)
        try:
            value = value % general_keys
        except KeyError, err:
            raise errors.ConfigError('unknown key: %s. Supportted '\
                    'keys are %s' % (str(err), ' '.join( \
                    self.DEFAULTS['general'].keys())))
        return value

    def is_profile_oriented(self):
        '''return True if config file is profile oriented'''
        return self.get_optional_item('general', 'profile') is not None

    def get_current_profile(self):
        '''get profile current used'''
        if self.is_profile_oriented():
            return self.build_profile_by_name(self.get('profile'))

        profile = self._build_profile_by_subcommand()
        self.convert_to_new_style(profile)
        return profile

    def convert_to_new_style(self, profile):
        'convert ~/.gbs.conf to new style'
        def dump_general(fhandler):
            'dump options in general section'
            parser = BrainConfigParser()
            parser.add_section('general')
            parser.set('general', 'profile', profile.name)

            for opt in self.options('general'):
                val = self.get(opt)
                if val != self.DEFAULTS['general'].get(opt):
                    parser.set('general', opt, val)
            parser.write(fhandler)

        fname = '~/.gbs.conf.template'
        try:
            tmp = Temp()
            with open(tmp.path, 'w') as fhandler:
                dump_general(fhandler)
                profile.dump(fhandler)
            shutil.move(tmp.path, os.path.expanduser(fname))
        except IOError, err:
            raise errors.ConfigError(err)

        log.warning('subcommand oriented style of config is deprecated. '
            'Please check %s, a new profile oriented style of config which'
            ' was converted from your current settings.' % fname)

    def get_optional_item(self, section, option, default=None):
        '''return default if section.option does not exist'''
        try:
            return self.get(option, section)
        except errors.ConfigError:
            return default

    def _get_url_options(self, section_id):
        '''get url/user/passwd from a section'''
        url = os.path.expanduser(self._interpolate(self.get('url', section_id)))
        user = self.get_optional_item(section_id, 'user')
        password = self.get_optional_item(section_id, 'passwd')
        return URL(url, user, password)

    def build_profile_by_name(self, name):
        '''return profile object by a given section'''
        if not name.startswith('profile.'):
            raise errors.ConfigError('section name specified by general.profile'
                ' must start with string "profile.": %s' % name)
        if not self.has_section(name):
            raise errors.ConfigError('no such section: %s' % name)

        user = self.get_optional_item(name, 'user')
        password = self.get_optional_item(name, 'passwd')

        profile = Profile(name, user, password)

        obs = self.get_optional_item(name, 'obs')
        if obs:
            if not obs.startswith('obs.'):
                raise errors.ConfigError('obs section name should start '
                                         'with string "obs.": %s' % obs)

            obsconf = SectionConf(profile, obs,
                                  self._get_url_options(obs),
                                  self.get_optional_item(obs, 'base_prj'),
                                  self.get_optional_item(obs, 'target_prj'))
            profile.set_obs(obsconf)

        repos = self.get_optional_item(name, 'repos')
        if repos:
            for repo in repos.split(','):
                repo = repo.strip()
                if not repo.startswith('repo.'):
                    log.warning('ignore %s, repo section name should start '
                                'with string "repo."' % repo)
                    continue

                repoconf = SectionConf(profile, repo,
                                       self._get_url_options(repo))
                profile.add_repo(repoconf)

        profile.buildroot = self.get_optional_item(name, 'buildroot')
        if self.get_optional_item(name, 'buildconf'):
            profile.buildconf = os.path.expanduser(self._interpolate(
                                                   self.get_optional_item(name,
                                                   'buildconf')))
        return profile

    def _parse_build_repos(self):
        """
        Make list of urls using repox.url, repox.user and repox.passwd
        configuration file parameters from 'build' section.
        Validate configuration parameters.
        """
        repos = {}
        # get repo settings form build section
        for opt in self.options('build'):
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

                value = self.get(opt, 'build')
                if name == 'passwdx':
                    try:
                        value = decode_passwdx(value)
                    except (TypeError, IOError), err:
                        raise errors.ConfigError('Error decoding %s: %s' % \
                                                 (opt, err))
                    repos[key]['passwd'] = value
                else:
                    repos[key][name] = value
        return sorted(repos.items(), key=lambda i: i[0])

    def _build_profile_by_subcommand(self):
        '''return profile object from subcommand oriented style of config'''
        profile = Profile('profile.current', None, None)

        sec = 'remotebuild'
        addr = self.get_optional_item(sec, 'build_server')
        if addr:
            user = self.get_optional_item(sec, 'user')
            password = self.get_optional_item(sec, 'passwd')
            url = URL(addr, user, password)

            obsconf = SectionConf(profile, 'obs.%s' % sec, url,
                        self.get_optional_item('remotebuild', 'base_prj'),
                        self.get_optional_item('remotebuild', 'target_prj'))
            profile.set_obs(obsconf)

        repos = self._parse_build_repos()
        for key, item in repos:
            if 'url' not in item:
                raise errors.ConfigError("URL is not specified for %s" % key)
            url = URL(item['url'], item.get('user'), item.get('passwd'))

            repoconf = SectionConf(profile, 'repo.%s' % key, url)
            profile.add_repo(repoconf)

        return profile


configmgr = BizConfigManager()
