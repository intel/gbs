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

from __future__ import with_statement
import os
import base64
from ConfigParser import SafeConfigParser, NoSectionError, NoOptionError, \
                         MissingSectionHeaderError

from gitbuildsys import msger, errors

class BrainConfigParser(SafeConfigParser):
    """Standard ConfigParser derived class which can reserve most of the
    comments, indents, and other user customized stuff inside the ini file.
    """

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
    DEFAULTS = {
            'general': {
                'tmpdir': '/var/tmp',
                'editor': '',
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
        from string import Template
        if not defaults:
            defaults = self.DEFAULTS

        tmpl_keys = {}
        for sec, opts in defaults.iteritems():
            for opt, val in opts.iteritems():
                tmpl_keys['%s__%s' % (sec, opt)] = val

        return Template(self.DEFAULT_CONF_TEMPLATE).safe_substitute(tmpl_keys)

    def _new_conf(self, fpath=None):
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
                        base64.b64encode(getpass.getpass().encode('bz2'))
        else:
            defaults['remotebuild']['passwdx'] = \
                        base64.b64encode(
                            defaults['remotebuild']['passwd'].encode('bz2'))

        with open(fpath, 'w') as wfile:
            wfile.write(self.get_default_conf(defaults))
        os.chmod(fpath, 0600)

        msger.info('Done. Your gbs config is now located at %s' % fpath)
        msger.warning("Don't forget to double-check the config manually.")
        return True

    def _check_passwd(self):
        replaced_keys = False
        for sec in self.DEFAULTS.keys():
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
                                     base64.b64encode(plainpass.encode('bz2')),
                                     key)
                            replaced_keys = True

        if replaced_keys:
            msger.warning('plaintext password in config files will '
                          'be replaced by encoded ones')
            self.update()

    def _get(self, opt, section='general'):
        sect_found = False
        for cfgparser in self._cfgparsers:
            try:
                return cfgparser.get(section, opt)
            except NoSectionError:
                pass
            except NoOptionError:
                sect_found = True

        if not sect_found:
            if section in self.DEFAULTS and opt in self.DEFAULTS[section]:
                return self.DEFAULTS[section][opt]
            else:
                raise errors.ConfigError('no section %s' % section)
        else:
            if opt in self.DEFAULTS[section]:
                return self.DEFAULTS[section][opt]
            else:
                raise errors.ConfigError('no opt: %s in section %s' \
                                         % (opt, section))

    def check_opt(self, opt, section='general'):
        if section in self.DEFAULTS and \
           opt in self.DEFAULTS[section]:
            return True
        else:
            return False

    def options(self, section='general'):
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
        if opt == 'passwd':
            opt = 'passwdx'
            val = self._get(opt, section)
            if val:
                try:
                    return base64.b64decode(val).decode('bz2')
                except (TypeError, IOError), err:
                    raise errors.ConfigError('passwdx:%s' % err)
            else:
                return val
        else:
            return self._get(opt, section)

    def set(self, opt, val, section='general'):
        if opt.endswith('passwd'):
            val = base64.b64encode(val.encode('bz2'))
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
        for cfgparser in self._cfgparsers:
            cfgparser.update()

configmgr = ConfigMgr()
