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
import ast
import base64
from ConfigParser import SafeConfigParser, NoSectionError, NoOptionError, \
                         MissingSectionHeaderError

from gitbuildsys import msger, errors
from gitbuildsys.safe_url import SafeURL


def decode_passwdx(passwdx):
    '''decode passwdx into plain format'''
    return base64.b64decode(passwdx).decode('bz2')


def encode_passwd(passwd):
    '''encode passwd by bz2 and base64'''
    return base64.b64encode(passwd.encode('bz2'))


def evalute_string(string):
    '''safely evaluate string'''
    if string.startswith('"') or string.startswith("'"):
        return ast.literal_eval(string)
    return string


def split_and_evaluate_string(string, sep=None, maxsplit=-1):
    '''split a string and evaluate each of them'''
    return [ evalute_string(i.strip()) for i in string.split(sep, maxsplit) ]


class SectionPattern(object):
    '''Pattern of section that support [section "name"] and [section].
    1. If there is white-space in section header, it must obey the format like:
        section_type white_spaces section_name,
    section_name could be any string.
    2. otherwise section name is the whole string in brackets
    '''

    SECTCRE = re.compile(
        r'\['                            # [
        r'(?P<header>[^] \t]+)'          # section name without any white-space
            r'([ \t]+'                   # or
            r'(?P<name>[^]]+)'           # section type and section name
            r')?'                        # this section name is optional
        r'\]'                            # ]
        )

    class MatchObject(object):
        '''Match object for SectionPattern'''

        def __init__(self, match):
            self.match = match

        def group(self, _group1):
            '''return a tuple(type, name) if section has a name,
            otherwise return a string as section name
            '''
            type_ = self.match.group('header')
            name = self.match.group('name')
            if not name:
                return type_

            name = evalute_string(name)
            return type_, name

    def match(self, string):
        '''return MatchObject if string match the pattern'''
        match = self.SECTCRE.match(string)
        return self.MatchObject(match) if match else match


class BrainConfigParser(SafeConfigParser):
    """Standard ConfigParser derived class which can reserve most of the
    comments, indents, and other user customized stuff inside the ini file.
    """

    SECTCRE = SectionPattern()

    def read(self, filenames):
        """Limit the read() only support one input file. It's enough for
        current case.
        If the input list has multiple values, use the last one.
        """

        if not isinstance(filenames, basestring) and len(filenames) > 1:
            msger.warning('Will not support multiple config files, '
                          'only read in the last one.')
            filenames = filenames[-1:]

        return SafeConfigParser.read(self, filenames)

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
                raise NoSectionError(section)

    def set(self, section, option, value, replace_opt=None):
        """When set new value, need to update the readin file lines,
        which can be saved back to file later.
        """
        try:
            SafeConfigParser.set(self, section, option, value)
            if replace_opt:
                SafeConfigParser.remove_option(self, section, replace_opt)
        except NoSectionError, err:
            raise errors.ConfigError(str(err))

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

        fptr = open(self._fpname, 'w')
        for line in self._flines:
            if line is not None:
                fptr.write(line)
        fptr.close()

class ConfigMgr(object):
    '''Support multi-levels of gbs.conf. Use this class to get and set
    item value without caring about concrete ini format'''

    DEFAULTS = {
            'general': {
                'tmpdir': '/var/tmp',
                'editor': '',
                'upstream_branch': 'upstream',
                'upstream_tag': 'upstream/%(upstreamversion)s',
            },
            'remotebuild': {
                'build_server': 'https://api.tizen.org',
                'user':         '',
                'passwd':       '',
                'base_prj':     'Tizen:Main',
                'target_prj':   ''
            },
            'build': {
                'build_cmd':    '/usr/bin/build',
                'distconf':     '/usr/share/gbs/tizen-1.0.conf',
            },
    }

    DEFAULT_CONF_TEMPLATE = """[general]
; general settings
tmpdir = $general__tmpdir
editor = $general__editor

[remotebuild]
; settings for build subcommand
build_server = $remotebuild__build_server
user = $remotebuild__user
; CAUTION: please use the key name "passwd" to reset plaintext password
passwdx = $remotebuild__passwdx
; Default base project
base_prj = $remotebuild__base_prj
; Default target project
target_prj = $remotebuild__target_prj

[build]
build_cmd = $build__build_cmd
distconf = $build__distconf

; optional, repos definitions
#repo1.url=
#repo1.user=
#repo1.passwd=
; one more repo
#repo2.url=
#repo2.user=
#repo2.passwd=
"""

    # make the manager class as singleton
    _instance = None
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(ConfigMgr, cls).__new__(cls, *args, **kwargs)

        return cls._instance

    def __init__(self, fpath=None):
        self._cfgparsers = []
        self.reset_from_conf(fpath)

    def reset_from_conf(self, fpath):
        'reset all config values by files passed in'
        if fpath:
            if not os.path.exists(fpath):
                raise errors.ConfigError('Configuration file %s does not '\
                                         'exist' % fpath)
            fpaths = [fpath]
        else:
            # use the default path
            fpaths = self._lookfor_confs()
            if not fpaths:
                if not self._new_conf():
                    msger.error('No config file available')

        for fpath in fpaths:
            cfgparser = BrainConfigParser()
            try:
                cfgparser.read(fpath)
            except MissingSectionHeaderError, err:
                raise errors.ConfigError('config file error:%s' % err)
            self._cfgparsers.append(cfgparser)
        self._check_passwd()

    @staticmethod
    def _lookfor_confs():
        """Look for available config files following the order:
            > Current git
            > Cwd
            > User
        """

        paths = []
        for path in (os.path.abspath('.git/gbs.conf'),
                     os.path.abspath('.gbs.conf'),
                     os.path.expanduser('~/.gbs.conf')):
            if os.path.exists(path) and path not in paths:
                paths.append(path)

        return paths

    def get_default_conf(self, defaults=None):
        'returns ini template string contains default values'
        from string import Template
        if not defaults:
            defaults = self.DEFAULTS

        tmpl_keys = {}
        for sec, opts in defaults.iteritems():
            for opt, val in opts.iteritems():
                tmpl_keys['%s__%s' % (sec, opt)] = val

        return Template(self.DEFAULT_CONF_TEMPLATE).safe_substitute(tmpl_keys)

    def _new_conf(self, fpath=None):
        'generate a new conf file located by fpath'
        if not fpath:
            fpath = os.path.expanduser('~/.gbs.conf')

        import getpass
        msger.info('Creating config file %s ... ' % fpath)
        # user and passwd in [build] section need user input
        defaults = self.DEFAULTS.copy()
        build_server = raw_input('Remote build server url (use %s by default):'\
                                 % defaults['remotebuild']['build_server'])
        if build_server:
            defaults['remotebuild']['build_server'] = build_server

        defaults['remotebuild']['user'] = \
                          raw_input('Username for remote build server '\
                    '(type <enter> to skip): ')

        if defaults['remotebuild']['user']:
            msger.info('Your password will be encoded before saving ...')
            defaults['remotebuild']['passwdx'] = \
                encode_passwd(getpass.getpass())
        else:
            defaults['remotebuild']['passwdx'] = \
                encode_passwd(defaults['remotebuild']['passwd'])

        with open(fpath, 'w') as wfile:
            wfile.write(self.get_default_conf(defaults))
        os.chmod(fpath, 0600)

        msger.info('Done. Your gbs config is now located at %s' % fpath)
        msger.warning("Don't forget to double-check the config manually.")
        return True

    def _check_passwd(self):
        'convert passwd item to passwdx and then update origin conf files'
        replaced_keys = False

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
                            cfgparser.set(sec,
                                     key + 'x',
                                     encode_passwd(plainpass),
                                     key)
                            replaced_keys = True

        if replaced_keys:
            msger.warning('plaintext password in config files will '
                          'be replaced by encoded ones')
            self.update()

    def _get(self, opt, section='general'):
        'get value from multi-levels of config file'
        sect_found = False
        for cfgparser in self._cfgparsers:
            try:
                return cfgparser.get(section, opt)
            except NoSectionError:
                pass
            except NoOptionError:
                sect_found = True

        if section in self.DEFAULTS and opt in self.DEFAULTS[section]:
            return self.DEFAULTS[section][opt]

        if not sect_found:
            raise errors.ConfigError('no section %s' % str(section))
        else:
            raise errors.ConfigError('no opt: %s in section %s' \
                                     % (opt, str(section)))

    def check_opt(self, opt, section='general'):
        if section in self.DEFAULTS and \
           opt in self.DEFAULTS[section]:
            return True
        else:
            return False

    def options(self, section='general'):
        'merge and return options of certain section from multi-levels'
        sect_found = False
        options = set()
        for cfgparser in self._cfgparsers:
            try:
                options.update(cfgparser.options(section))
                sect_found = True
            except NoSectionError:
                pass

        if section in self.DEFAULTS:
            options.update(self.DEFAULTS[section].keys())
            sect_found = True

        if not sect_found:
            raise errors.ConfigError('invalid section %s' % (section))

        return options

    def get(self, opt, section='general'):
        'get item value. return plain text of password if item is passwd'
        if opt == 'passwd':
            opt = 'passwdx'
            val = self._get(opt, section)
            if val:
                try:
                    return decode_passwdx(val)
                except (TypeError, IOError), err:
                    raise errors.ConfigError('passwdx:%s' % err)
            else:
                return val
        else:
            return self._get(opt, section)

    def set(self, opt, val, section='general'):
        if opt.endswith('passwd'):
            val = encode_passwd(val)
            opt += 'x'

        for cfgparser in self._cfgparsers:
            if cfgparser.has_option(section, opt):
                return cfgparser.set(section, opt, val)

        # Option not found, add a new key to the first cfg file that has
        # the section
        for cfgparser in self._cfgparsers:
            if cfgparser.has_section(section):
                return cfgparser.set(section, opt, val)

        raise errors.ConfigError('invalid section %s' % (section))

    def update(self):
        'update changed values into files on disk'
        for cfgparser in self._cfgparsers:
            cfgparser.update()


class Profile(object):
    '''Profile which contains all config values related to same domain'''

    def __init__(self, user, password):
        self.common_user = user
        self.common_password = password
        self.repos = []
        self.api = None

    def make_url(self, url, user, password):
        '''make a safe url which contains auth info'''
        user = user or self.common_user
        password = password or self.common_password
        try:
            return SafeURL(url, user, password)
        except ValueError, err:
            raise errors.ConfigError('%s for %s' % (str(err), url))

    def add_repo(self, url, user, password):
        '''add a repo to repo list of the profile'''
        self.repos.append(self.make_url(url, user, password))

    def set_api(self, url, user, password):
        '''set OBS api of the profile'''
        self.api = self.make_url(url, user, password)

    def get_repos(self):
        '''get repo list of the profile'''
        return self.repos

    def get_api(self):
        '''get OBS api of the profile'''
        return self.api


class BizConfigManager(ConfigMgr):
    '''config manager which handles high level conception, such as profile info
    '''

    def is_profile_oriented(self):
        '''return True if config file is profile oriented'''
        return self.get_optional_item('general', 'profile') is not None

    def get_current_profile(self):
        '''get profile current used'''
        if self.is_profile_oriented():
            return self._build_profile_by_name(self.get('profile'))

        msger.warning('subcommand oriented style of config is deprecated, '
                      'please convert to profile oriented style.')
        return self._build_profile_by_subcommand()

    def get_optional_item(self, section, option, default=None):
        '''return default if section.option does not exist'''
        try:
            return self.get(option, section)
        except errors.ConfigError:
            return default

    def _get_url_section(self, section_id):
        '''get url/user/passwd from a section'''
        url = self.get('url', section_id)
        user = self.get_optional_item(section_id, 'user')
        password = self.get_optional_item(section_id, 'passwd')
        return url, user, password

    def _build_profile_by_name(self, name):
        '''return profile object by a given section'''
        profile_id = ('profile', name)
        user = self.get_optional_item(profile_id, 'user')
        password = self.get_optional_item(profile_id, 'passwd')

        profile = Profile(user, password)

        conf_api = self.get_optional_item(profile_id, 'api')
        if conf_api:
            api = self.get('api', profile_id)
            api_id = ('obs', api)
            profile.set_api(*self._get_url_section(api_id))

        conf_repos = self.get_optional_item(profile_id, 'repos')
        if conf_repos:
            repos = split_and_evaluate_string(conf_repos, ',')
            for repo in repos:
                repo_id = ('repo', repo)
                profile.add_repo(*self._get_url_section(repo_id))

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
        profile = Profile(None, None)

        section_id = 'remotebuild'
        url = self.get('build_server', section_id)
        user = self.get_optional_item(section_id, 'user')
        password = self.get_optional_item(section_id, 'passwd')
        profile.set_api(url, user, password)

        repos = self._parse_build_repos()
        for key, item in repos:
            if 'url' not in item:
                raise errors.ConfigError("Url is not specified for %s" % key)
            profile.add_repo(item['url'], item.get('user'), item.get('passwd'))

        return profile


configmgr = BizConfigManager()
