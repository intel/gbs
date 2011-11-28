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
import os, sys
import base64
from ConfigParser import *
import msger

class BrainConfigParser(SafeConfigParser):
    """Standard ConfigParser derived class which can reserve most of the
    comments, indents, and other user customized stuff inside the ini file.
    """

    def read(self, filenames):
        """Limit the read() only support one input file. It's enough for
        current case.
        """

        if len(filenames) > 1:
            msger.warning('Will not support multiple config files, only read in the 1st one.')
            filenames = filenames[:1]

        return SafeConfigParser.read(self, filenames)

    def _read(self, fp, fpname):
        """Parse a sectioned setup file.

        The sections in setup file contains a title line at the top,
        indicated by a name in square brackets (`[]'), plus key/value
        options lines, indicated by `name: value' format lines.
        Continuations are represented by an embedded newline then
        leading whitespace.  Blank lines, lines beginning with a '#',
        and just about everything else are ignored.

        Customization: save filename and corresponding lineno for all
        the sections and keys
        """
        # save the original filepath and contents
        self._fpname = fpname
        self._flines = fp.readlines()
        fp.seek(0)
        # init dict DS to store lineno
        self._sec_linenos = {}
        self._opt_linenos = {}

        cursect = None                            # None, or a dictionary
        optname = None
        lineno = 0
        e = None                                  # None, or an exception
        while True:
            line = fp.readline()
            if not line:
                break
            lineno = lineno + 1
            # comment or blank line?
            if line.strip() == '' or line[0] in '#;':
                continue
            if line.split(None, 1)[0].lower() == 'rem' and line[0] in "rR":
                # no leading whitespace
                continue
            # continuation line?
            if line[0].isspace() and cursect is not None and optname:
                value = line.strip()
                if value:
                    cursect[optname] = "%s\n%s" % (cursect[optname], value)
                    self._opt_linenos["%s.%s" % (cursect['__name__'], optname)].append(lineno)
            # a section header or option header?
            else:
                # is it a section header?
                mo = self.SECTCRE.match(line)
                if mo:
                    sectname = mo.group('header')
                    if sectname in self._sec_linenos:
                        self._sec_linenos[sectname].append(lineno)
                    else:
                        self._sec_linenos[sectname] = [lineno]

                    if sectname in self._sections:
                        cursect = self._sections[sectname]
                    elif sectname == DEFAULTSECT:
                        cursect = self._defaults
                    else:
                        cursect = self._dict()
                        cursect['__name__'] = sectname
                        self._sections[sectname] = cursect
                    # So sections can't start with a continuation line
                    optname = None
                # no section header in the file?
                elif cursect is None:
                    raise MissingSectionHeaderError(fpname, lineno, line)
                # an option line?
                else:
                    mo = self.OPTCRE.match(line)
                    if mo:
                        optname, vi, optval = mo.group('option', 'vi', 'value')
                        if vi in ('=', ':') and ';' in optval:
                            # ';' is a comment delimiter only if it follows
                            # a spacing character
                            pos = optval.find(';')
                            if pos != -1 and optval[pos-1].isspace():
                                optval = optval[:pos]
                        optval = optval.strip()
                        # allow empty values
                        if optval == '""':
                            optval = ''
                        optname = self.optionxform(optname.rstrip())
                        cursect[optname] = optval
                        self._opt_linenos["%s.%s" % (cursect['__name__'], optname)] = [lineno]

                    else:
                        # a non-fatal parsing error occurred.  set up the
                        # exception but keep going. the exception will be
                        # raised at the end of the file and will contain a
                        # list of all bogus lines
                        if not e:
                            e = ParsingError(fpname)
                        e.append(lineno, repr(line))

        # if any parsing errors occurred, raise an exception
        if e:
            raise e

    def set(self, section, option, value, replace_opt=None):
        """When set new value, need to update the readin file lines,
        which can be saved back to file later.
        """

        def _find_next_section_lineno(section):
            if section not in self._sec_linenos:
                # new section?
                return -1

            found = False
            for sec, lineno in sorted(self._sec_linenos.items(), key=lambda x: x[1][0]):
                if found:
                    return lineno[0]-1

                if sec == section:
                    found = True

            # if reach here, sec is the last one
            return -1

        SafeConfigParser.set(self, section, option, value)
        
        # If the code reach here, it means the section and key are ok
        if replace_opt is None:
            kname = "%s.%s" % (section, option)
        else:
            kname = "%s.%s" % (section, replace_opt)

        line = '%s = %s\n' %(option, value)
        if kname in self._opt_linenos:
            # update an old key
            self._flines[self._opt_linenos[kname][0]-1] = line
            if len(self._opt_linenos[kname]) > 1:
                # multiple lines value, remote the rest
                del self._flines[self._opt_linenos[kname][1]-1:self._opt_linenos[kname][-1]]
        else:
            # new key
            line += '\n' # one more blank line
            nextsec = _find_next_section_lineno(section)
            if nextsec == -1:
                self._flines.append(line)
            else:
                self._flines.insert(nextsec, line)

    def update(self):
        """Update the original config file using updated values"""

        if self._fpname == '<???>':
            return

        fp = open(self._fpname, 'w')
        fp.writelines(self._flines)
        fp.close()

class ConfigMgr(object):
    DEFAULTS = {
        'hudson_user': 'hudsonuser',
        'hudson_pass': '',
        'hudson_passx': '',
    }

    DEFAULT_CONF_TEMPLATE="""[general]
; general settings
hudson_user = $hudson_user
hudson_pass = $hudson_pass
hudson_passx = $hudson_passx

[build]
; settings for build subcommand

[packaging]
; settings for packaging subcommand

[import]
; settings for import subcommand
"""

    # make the manager class as singleton
    _instance = None
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(ConfigMgr, cls).__new__(cls, *args, **kwargs)

        return cls._instance

    def __init__(self, fpath=None):
        self.cfgparser = BrainConfigParser()

        if not fpath:
            # use the default path
            fpath = os.path.expanduser('~/.tizenpkg.conf')

        if not os.path.exists(fpath):
            if not self._new_conf(fpath):
                msger.error('No config file available')

        self.cfgparser.read([fpath])
        self._check_passwd()

    def get_default_conf(self, defaults=None):
        from string import Template
        if not defaults:
            defaults = self.DEFAULTS
        return Template(self.DEFAULT_CONF_TEMPLATE).safe_substitute(defaults)

    def _new_conf(self, fpath):
        if msger.ask('Create config file %s using default values?' % fpath):
            import getpass

            defaults = self.DEFAULTS.copy()
            defaults['hudson_user'] = raw_input('Username: ')
            msger.info('Your password will be encoded before saving ...')
            defaults['hudson_pass'] = ''
            defaults['hudson_passx'] = base64.b64encode(getpass.getpass().encode('bz2'))

            with open(fpath, 'w') as wf:
                wf.write(self.get_default_conf(defaults))
            return True

        return False

    def _check_passwd(self):
        plainpass = self.get('hudson_pass')
        if not plainpass:
            # None or ''
            return

        msger.warning('plaintext password in config file will be replaced by encoded one')
        self.set('hudson_passx', base64.b64encode(plainpass.encode('bz2')), replace_opt='hudson_pass')
        self.update()

    def get(self, opt, section='general'):
        try:
            return self.cfgparser.get(section, opt)
        except NoOptionError:
            if opt in self.DEFAULTS:
                return self.DEFAULTS[opt]
            else:
                return None

    def set(self, opt, val, section='general', replace_opt=None):
        return self.cfgparser.set(section, opt, val, replace_opt)

    def update(self):
        self.cfgparser.update()

configmgr = ConfigMgr()
