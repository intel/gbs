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

class CmdError(Exception):
    """An exception base class for all command calling errors."""
    keyword = ''

    def __str__(self):
        return self.keyword + str(self.args[0])

class Usage(CmdError):
    keyword = '<usage>'

    def __str__(self):
        return self.keyword + str(self.args[0]) + \
                ', please use "--help" for more info'

class ConfigError(CmdError):
    keyword = '<config>'

class ObsError(CmdError):
    keyword = '<obs>'

class UnpackError(CmdError):
    keyword = '<unpack>'

class FormatError(CmdError):
    keyword = '<format>'

class QemuError(CmdError):
    keyword = '<qemu>'

class Abort(CmdError):
    keyword = ''

class UrlError(CmdError):
    keyword = '<urlgrab>'
