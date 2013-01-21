#!/usr/bin/env python

"""GBS setup."""

import os, sys
import glob
import re

from distutils.core import setup

try:
    import setuptools
    # enable "setup.py develop", optional
except ImportError:
    pass

MOD_NAME = 'gitbuildsys'

def get_version(mod_name):
    """Get version from module __init__.py"""
    path = os.path.join(mod_name, "__init__.py")
    if not os.path.isfile(path):
        print 'No %s version file found' % path
        return

    content = open(path).read()
    match = re.search(r'^__version__\s*=\s*[\x22\x27]([^\x22\x27]+)[\x22\x27]',
                      content, re.M)
    if match:
        return match.group(1)

    print 'Unable to find version in %s' % path


VERSION = get_version(MOD_NAME)
if not VERSION:
    sys.exit(1)

# HACK!!! --install-layout=deb must be used in debian/rules
# "--install-layout=deb" is required for pyver>2.5 in Debian likes
if sys.version_info[:2] > (2, 5):
    if len(sys.argv) > 1 and 'install' in sys.argv:
        import platform
        # for debian-like distros, mods will be installed to
        # ${PYTHONLIB}/dist-packages
        if platform.linux_distribution()[0] in ('debian', 'Ubuntu'):
            sys.argv.append('--install-layout=deb')

setup(name='gbs',
      version=VERSION,
      description='The command line tools for Tizen package developers',
      author='Jian-feng Ding, Huaxu Wan',
      author_email='jian-feng.ding@intel.com, huaxu.wan@intel.com',
      url='https://git.tizen.org/',
      scripts=['tools/gbs'],
      packages=[MOD_NAME],
)
