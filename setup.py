#!/usr/bin/env python

import os, sys
import glob
from distutils.core import setup
try:
    import setuptools
    # enable "setup.py develop", optional
except ImportError:
    pass

MOD_NAME = 'gitbuildsys'

version_path = 'VERSION'
if not os.path.isfile(version_path):
    print 'No VERSION file in topdir, abort'
    sys.exit(1)

try:
    # first line should be the version number
    version = open(version_path).readline().strip()
    if not version:
        print 'VERSION file is invalid, abort'
        sys.exit(1)

    ver_file = open('%s/__version__.py' % MOD_NAME, 'w')
    ver_file.write("VERSION = \"%s\"\n" % version)
    ver_file.close()
except IOError:
    print 'WARNING: Cannot write version number file'

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

