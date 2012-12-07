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

"""
Custom global gbs exceptions. Almost useless as
most of exceptions should be moved to modules where they raised.
"""

class CmdError(Exception):
    """An exception base class for all command calling errors."""
    keyword = ''

    def __str__(self):
        return self.keyword + str(self.args[0])

class Usage(CmdError):
    """Usage error. Raised only by remotebuild."""
    keyword = '<usage>'

    def __str__(self):
        return self.keyword + str(self.args[0]) + \
                ', please use "--help" for more info'

class ConfigError(CmdError):
    """Config parsing error. Raised only by conf module."""
    keyword = '<config>'

class ObsError(CmdError):
    """OBS error. Raised only by oscapi module."""
    keyword = '<obs>'

class UrlError(CmdError):
    """Url grabber error. Raised only by utils.URLGrabber class."""
    keyword = '<url>'

class GbsError(CmdError):
    """
    Most used exception. Should be base exception class as CmdError is
    not directly raised anywhere.
    """
    keyword = '<gbs>'
