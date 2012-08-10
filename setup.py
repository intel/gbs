#!/usr/bin/env python

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
version_path = os.path.join(MOD_NAME, "__init__.py")
if not os.path.isfile(version_path):
    print 'No %s version file found' % version_path
    sys.exit(1)

content = open(version_path).read()
match = re.search(r'^__version__\s*=\s*[\x22\x27]([^\x22\x27]+)[\x22\x27]',
                  content, re.M)
if match:
    version = match.group(1)
else:
    print 'Unable to find version in %s' % version_path
    sys.exit(1)

# "--install-layout=deb" is required for pyver>2.5 in Debian likes
if sys.version_info[:2] > (2, 5):
    if len(sys.argv) > 1 and 'install' in sys.argv:
        try:
            import platform
            (dist, ver, rid) = platform.linux_distribution()

            # for debian-like distros, mods will be installed to
            # ${PYTHONLIB}/dist-packages
            if dist in ('debian', 'Ubuntu'):
                sys.argv.append('--install-layout=deb')
        except:
            pass

setup(name='gbs',
      version = version,
      description='The command line tools for Tizen package developers',
      author='Jian-feng Ding, Huaxu Wan',
      author_email='jian-feng.ding@intel.com, huaxu.wan@intel.com',
      url='https://git.tizen.org/',
      scripts=['tools/gbs'],
      packages=[MOD_NAME],
      data_files = [('/usr/share/gbs', glob.glob('data/*'))],
     )

