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

"""
This module takes care of handling/generating/parsing of build.xml
"""

import re

from collections import OrderedDict
from xml.dom import minidom

class BuildDataError(Exception):
    """Custom BuildData exception."""
    pass

class BuildData(object):
    """Class for handling build data.

    NOTE! For now it contains only APIs used by pre-release job
          (see usage example below).
    NOTE! Feel free to add APIs, used by gbs here

    """

    # fixing of buggy xml.dom.minidom.toprettyxml
    XMLTEXT_RE = re.compile('>\n\s+([^<>\s].*?)\n\s+</', re.DOTALL)

    def __init__(self, build_id=None):
        self.build_id = build_id
        self.targets = OrderedDict()

    def add_target(self, target):
        """Add (or update) target to the list of targets."""
        self.targets[target["name"]] = target

    def load(self, xml):
        """Load build data from string."""

        def get_elem(node, name):
            """Helper: get first element by tag name."""
            try:
                return node.getElementsByTagName(name)[0]
            except IndexError:
                raise BuildDataError("Error: <%s><%s> not found" % \
                                     (node.nodeName, name))
        dom = minidom.parseString(xml)
        btargets = get_elem(dom, "buildtargets")

        for btarget in btargets.getElementsByTagName("buildtarget"):
            print btarget.childNodes
            bconf = get_elem(btarget, "buildconf")

            target = {
                "name":  btarget.getAttribute("name"),
                "archs": [],
                "buildconf": {
                    "location":
                        get_elem(bconf, "location").getAttribute("href"),
                    "checksum": {
                       "type": get_elem(bconf, "checksum").getAttribute("type"),
                       "value": get_elem(bconf, "checksum").firstChild.data
                    }
                }
            }

            # Get archs
            for barch in btarget.getElementsByTagName("arch"):
                target["archs"].append(barch.getAttribute("name"))

            self.targets[target["name"]] = target

    def to_xml(self, hreadable=True):
        """Format build data as xml."""
        content = '<?xml version="1.0"?><build version="1.0">'\
                  '<id>%s</id>' % self.build_id
        # list of repos
        content += '<repos>'
        archs = []
        for name, target in self.targets.iteritems():
            content += '<repo>%s</repo>' % name
            archs.extend(target['archs'])
        content += '</repos>'

        # list of architectures
        content += '<archs>'
        for arch in set(archs):
            content += '<arch>%s</arch>' % arch
        content += '</archs>'

        # build config
        #for name in self.targets:
        #    content += '<buildconf>%s</buildconf>' % \
        #               self.targets[name]['buildconf']

        # build targets
        content += '<buildtargets>'
        for name in self.targets:
            target = self.targets[name]
            content += '<buildtarget name="%s">' % name

            # buildconf
            content += '<buildconf>'
            buildconf = target['buildconf']
            content += '<location href="%s"/>' % buildconf['location']
            content += '<checksum type="%s">%s</checksum>' % \
                       (buildconf['checksum']['type'],
                        buildconf['checksum']['value'])
            content += '</buildconf>'

            # archs
            content += '<arch default="yes">%s</arch>' % target['archs'][0]
            for arch in target["archs"][1:]:
                content += '<arch>%s</arch>' % arch

            content += '</buildtarget>'
        content += '</buildtargets></build>'

        # make it human readable
        if hreadable:
            dom = minidom.parseString(content)
            content = self.XMLTEXT_RE.sub('>\g<1></',
                                          dom.toprettyxml(indent='  '))

        return content

    def save(self, fname, hreadable=True):
        """Save builddata to file."""
        # Write content down
        with open(fname, 'w') as out:
            out.write(self.to_xml(hreadable))
