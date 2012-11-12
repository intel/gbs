#!/usr/bin/env python
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

"""Local additions to commandline parsing."""

import os
import re
import functools

from argparse import RawDescriptionHelpFormatter, ArgumentTypeError

class GbsHelpFormatter(RawDescriptionHelpFormatter):
    """Changed default argparse help output by request from cmdln lovers."""

    def __init__(self, *args, **kwargs):
        super(GbsHelpFormatter, self).__init__(*args, **kwargs)
        self._aliases = {}

    def add_argument(self, action):
        """Collect aliases."""

        if action.choices:
            for item, parser in action.choices.iteritems():
                self._aliases[str(item)] = parser.get_default('alias')

        return super(GbsHelpFormatter, self).add_argument(action)

    def format_help(self):
        """
        There is no safe and documented way in argparse to reformat
        help output through APIs as almost all of them are private,
        so this method just parses the output and changes it.
        """
        result = []
        subcomm = False
        for line in super(GbsHelpFormatter, self).format_help().split('\n'):
            if line.strip().startswith('{'):
                continue
            if line.startswith('optional arguments:'):
                line = 'Global Options:'
            if line.startswith('usage:'):
                line = "Usage: gbs [GLOBAL-OPTS] SUBCOMMAND [OPTS]"
            if subcomm:
                match = re.match("[ ]+([^ ]+)[ ]+(.+)", line)
                if match:
                    name, help_text  = match.group(1), match.group(2)
                    alias = self._aliases.get(name) or ''
                    if alias:
                        alias = "(%s)" % alias
                    line = "  %-22s%s" % ("%s %s" % (name, alias), help_text)
            if line.strip().startswith('subcommands:'):
                line = 'Subcommands:'
                subcomm = True
            result.append(line)
        return '\n'.join(result)

def subparser(func):
    """Convenient decorator for subparsers."""
    @functools.wraps(func)
    def wrapper(parser):
        """
        Create subparser
        Set first line of function's docstring as a help
        and the rest of the lines as a description.
        Set attribute 'module' of subparser to 'cmd'+first part of function name
        """
        splitted = func.__doc__.split('\n')
        name = func.__name__.split('_')[0]
        subpar = parser.add_parser(name, help=splitted[0],
                                   description='\n'.join(splitted[1:]),
                                   formatter_class=RawDescriptionHelpFormatter)
        subpar.set_defaults(module="cmd_%s" % name)
        return func(subpar)
    return wrapper


def basename_type(path):
    '''validate function for base file name argument'''
    if os.path.basename(path) != path:
        raise ArgumentTypeError('should be a file name rather than a path')
    return path
