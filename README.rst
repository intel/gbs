===
gbs
===
---------------------------------------------------------------------
git build system
---------------------------------------------------------------------
:Copyright: GPLv2
:Manual section: 1

Overview
========
git-build-system is a command line tools for Tizen package developers

* gbs build : build rpm package from git repository on OBS
* gbs local-build : build rpm package from git repository at local
* gbs import-orig: import source tarball to current git repository, which can be used to upgrade a package
* gbs import : import source rpm or specfile to git repository
* gbs submit : maintain the changelogs file, sanity check etc.

It supports native running in many mainstream Linux distributions, including:

* Fedora (14 and above)
* openSUSE (11.3 and above)
* Ubuntu (10.04 and above)
* Debian (5.0 and above)

Installation
============
gbs is recommended to install from official repository, but if your system have
not been supported by official repo, you can try to install gbs from source 
code, before that, you should install gbs's dependencies such as git, osc. 

Repositories
------------
So far we support `gbs` binary rpms/debs for many popular Linux distributions,
please see the following list:

* Debian 6.0
* Fedora 14
* Fedora 15
* Fedora 16
* openSUSE 11.3
* openSUSE 11.4
* openSUSE 12.1
* Ubuntu 10.04
* Ubuntu 10.10
* Ubuntu 11.04
* Ubuntu 11.10

And you can get the corresponding repository on

 `<http://download.tizen.org/live/Tools:/Building:/Devel>`_

If there is no the distribution you want in the list, please install it from
source code.

Binary Installation
-------------------

Fedora Installation
~~~~~~~~~~~~~~~~~~~
1. Add Tools Building repo:
::

  $ sudo cat <<REPO > /etc/yum.repos.d/tools-building.repo
  > [tools-building]
  > name=Tools for Fedora
  > baseurl=http://download.tizen.org/live/Tools:/Building:/Devel/Fedora_<VERSION>
  > enabled=1
  > gpgcheck=0
  > REPO

2. Update repolist:
::

  $ sudo yum makecache

3. Install gbs:
::

  $ sudo yum install gbs

openSUSE Installation
~~~~~~~~~~~~~~~~~~~~~
1. Add Tools Building repo:
::

  $ sudo zypper addrepo http://download.tizen.org/live/Tools:/Building:/Devel/openSUSE_<VERSION>/ tools-building

2. Update repolist:
::

  $ sudo zypper refresh

3. Install gbs:
::

  $ sudo zypper install gbs

Ubuntu/Debian Installation
~~~~~~~~~~~~~~~~~~~~~~~~~~
1. Append repo source:
::

  $ sudo cat <<REPO >> /etc/apt-sources.list
  > deb http://download.tizen.org/live/Tools:/Building:/Devel/<Ubuntu/Debian>_<VERSION>/ /
  > REPO

2. Update repolist:
::

  $ sudo apt-get update

3. Install gbs:
::

  $ sudo apt-get install gbs

Source Installation
-------------------
If you need install gbs from source code, you need install gbs's dependencies
first, required packages as follows:

* git-core
* osc >= 0.131
* rpm (None Fedora)
* rpm-build (Fedora)

Official osc are maintained at:

 `<http://download.opensuse.org/repositories/openSUSE:/Tools/>`_

which can be added to you system, then using general package manager tools
to install osc. 

Gbs source code is managed by Gerrit in tizen staging zone(temporarily), you
need an account to access it.

Clone the source tree by:
::

  $ git clone ssh://<user_name>@review.stg.tizen.org:29418/gbs

*Tips*: You need login the Gerrit and upload you public SSH key first
and got your proxy setup.

Then using the following commands to install gbs:
::

  $ cd gbs
  $ sudo make install


Configuration file
==================
gbs read gbs configure file from ~/.gbs.conf. At the first time to run the gbs,
it will prompt you to input your user_name and password. Or edit the 
configuration file by yourself.  Just make sure it looks like as below:
::

  [general]
  ; general settings
  tmpdir = /var/tmp
  [build]
  ; settings for build subcommand
  build_server = <OBS API URL>
  user = <USER_NAME>
  passwd  = <PASSWORD in base64 string>
  passwdx = <PASSWORD encoded in base64 string>
  [localbuild]
  build_cmd = /usr/bin/build
  build_root= /var/tmp/build-root-gbs
  su-wrapper= su -c
  distconf=/usr/share/gbs/tizen-1.0.conf
  [import]
  commit_name= <Author Name>
  commit_email= <Author Email>

In this configuration file, there are three sections: [common] is for general
setting, [build] section is for the options of gbs build, and [localbuild]
is for gbs localbuild.

In the [build] section, the following values can be specified:

build_server
    OBS API url, which point to remote OBS. Available value can be:
    https://api.stg.tizen.org
user
    OBS account user name
passwd
    raw OBS account user passwd
passwdx
    encoded OBS account user passwd, this key would be generated automaticlly.

In the [localbuild] section, the following values can be specified:

build_cmd
    build script path for building RPMs in a chroot environment
build_root
    patch for chroot environment
distconf
    Specify distribution configure file

In [import] section, the following values can be specified:

commit_name
    Commit author name while executing git commit
commit_email
    Commit author email adress while executing git commit

Usages
======
It's recommended to use `--help` or `help <subcmd>` to get the help message,
for the tool is more or less self-documented.

Running 'gbs build'
--------------------

Subcommand `build` is used to push local git code to remote obs build server
to build. The usage of subcommand `build` can be available using `gbs build --help`
::

  build (bl): test building for current pkg

  Usage:
      gbs build [options] [OBS_project]

  Options:
      -h, --help          show this help message and exit
      -B BASE_OBSPRJ, --base-obsprj=BASE_OBSPRJ
                          Base OBS project being used to branch from, use
                          "Trunk" if not specified
      -T TARGET_OBSPRJ, --target-obsprj=TARGET_OBSPRJ
                          OBS target project being used to build package, use
                          "home:<userid>:gbs:Trunk" if not specified

Before running gbs build, you need to prepare a package git repository first,
and packaging directory must be exist and have spec file in it. The spec file
is used to prepare package name, version and tar ball format, and tar ball
format is specified using SOURCE field in specfile.

Once git reposoritory and packaging directory are  ready,  goto  the  root
directory of git repository, run gbs build as follows:
::

  $ gbs build
  $ gbs build -B Test
  $ gbs build -B Test -T home:<userid>:gbs

Running 'gbs localbuild'
------------------------

Subcommand `localbuild` is used to build rpm package at local by rpmbuild. The
usage of subcommand `localbuild` can be available using `gbs localbuild --help`
::

  localbuild (lb): local build package
  Usage:
      gbs localbuild -R repository -A ARCH [options] [package git dir]
      [package git dir] is optional, if not specified, current dir would
      be used.
  Examples:
      gbs localbuild -R http://example1.org/packages/ \
                     -R http://example2.org/packages/ \
                     -A i586                          \
                     -D /usr/share/gbs/tizen-1.0.conf
  Note:
  if -D not specified, distconf key in ~/.gbs.conf would be used.
  Options:
      -h, --help          show this help message and exit
      --debuginfo         Enable build debuginfo sub-packages
      --noinit            Skip initialization of build root and start with build
                          immediately
      -C, --clean         Delete old build root before initializing it
      -A ARCH, --arch=ARCH
                          build target arch
      -B BUILDROOT, --buildroot=BUILDROOT
                          Specify build rootdir to setup chroot environment
      -R REPOSITORIES, --repository=REPOSITORIES
                          Specify package repositories, Supported format is rpm-
                          md
      -D DIST, --dist=DIST
                          Specify distribution configure file, which should be
                          full path

git repository and packaging directory should be prepared like `gbs build`.

Examples to run gbs localbuild:

1) Use specified dist file in command line using -D option
::

  $ gbs localbuild -R http://example1.org/ -A i586 -D /usr/share/gbs/tizen-1.0.conf

2) Use dist conf file specified in ~/.gbs.conf, if distconf key exist.
::

  $ gbs localbuild -R http://example1.org/ -A i586

3) Multi repos specified
::

  $ gbs lb -R http://example1.org/  -R http://example2.org/  -A i586

4) With --noinit option, Skip initialization of build root and start with build immediately
::

  $ gbs localbuild -R http://example1.org/ -A i586  --noinit

5) Specify a package git directory, instead of running in git top directory
::

  $ gbs localbuild -R http://example1.org/ -A i586  PackageKit

6) Local repo example
::

  $ gbs localbuild -R /path/to/repo/dir/ -A i586

'''BKM''': to have quick test with local repo, you can run 'gbs localbuild' 
with remote repo. rpm packages will be downloaded to localdir /var/cache/\
build/md5-value/, then you can use the following command to create it as local
repo
::

  $ mv /var/cache/build/md5-value/ /var/cache/build/localrepo
  $ cd /var/cache/build/localrepo
  $ createrepo . # if createrepo is not available, you should install it first
  $ gbs localbuild -R /var/cache/build/localrepo/ -A i586/armv7hl

If gbs localbuild fails with dependencies, you should download it manually and
put it to /var/cache/build/localrepo, then createrepo again.


Running 'gbs import-orig'
-------------------------

Subcommand `import-orig` is used to import original upstream tar ball to current
git repository. This subcommand is mostly used for upgrading packages. Upstream
tar ball format can be *.tar.gz,*.tar.bz2,*.tar.xz,*.tar.lzma,*.zip.

Usage of subcommand `import-orig` can be available from `gbs import-orig --help`
::

  root@test-virtual-machine:~/gbs# gbs import-orig -h
  import_orig (import-orig): Import tar ball to upstream branch

  Usage:
      gbs import-orig [options] original-tar-ball


  Examples:
    $ gbs import-orig original-tar-ball
  Options:
      -h, --help          show this help message and exit
      --tag               Create tag while importing new version of upstream
                          tar ball
      --no-merge          Don't merge new upstream branch to master branch,
                          please merge it manually
      --upstream_branch=UPSTREAM_BRANCH
                          specify upstream branch for new version of package
      --author-email=AUTHOR_EMAIL
                          author's email of git commit
      --author-name=AUTHOR_NAME
                          author's name of git commit

gbs import-orig must run under the top directory of package git repository,the
following command can be used:
::

  $ gbs import-orig example-0.1.tar.gz
  $ gbs import-orig example-0.2-tizen.tar.bz2
  Info: unpack upstream tar ball ...
  Info: submit the upstream data
  Info: merge imported upstream branch to master branch
  Info: done.
  $

Running 'gbs import'
--------------------

Subcommand `import` is used to import source rpm or unpacked \*.src.rpm to current
git repository. This subcommand is mostly used for initializing git repository
or upgrading packages. Usage of subcommand `import` can be available using
`gbs import --help`
::

  import (im): Import spec file or source rpm to git repository

  Usage:
      gbs import [options] specfile | source rpm


  Examples:
    $ gbs import /path/to/specfile/
    $ gbs import /path/to/*.src.rpm
  Options:
      -h, --help          show this help message and exit
      --tag               Create tag while importing new version of upstream tar
                          ball
      --upstream_branch=UPSTREAM_BRANCH
                          specify upstream branch for new version of package
      --author-email=AUTHOR_EMAIL
                          author's email of git commit
      --author-name=AUTHOR_NAME
                          author's name of git commit


Examples to run gbs import:

1) import from source rpm, and package git repository would be generated
::

  $test@test/gbs-demo# gbs import expect-5.43.0-18.13.src.rpm 
   Info: unpack source rpm package: expect-5.43.0-18.13.src.rpm
   Info: No git repository found, creating one.
   Info: unpack upstream tar ball ...
   Info: submitted the upstream data as first commit
   Info: create upstream branch
   Info: submit packaging files as second commit
   Info: done.

2) import from unpacked source rpm, spec file need to be specified from args
::

  $test@test/gbs-demo# gbs import expect-5.43.0/expect.spec --tag
   Info: No git repository found, creating one.
   Info: unpack upstream tar ball ...
   Info: submitted the upstream data as first commit
   Info: create tag named: 5.43.0
   Info: create upstream branch
   Info: submit packaging files as second commit
   Info: done.
  $test@test/gbs-demo# cd expect&git log
   commit 3c344812d0fa53bd9c56ebd054998dc1b401ecde
   Author: root <root@test-virtual-machine.(none)>
   Date:   Sun Nov 27 00:34:25 2011 +0800

        packaging files for tizen

   commit b696a78b36ebd3d5614f0d3044834bb4e6bcd928
   Author: root <root@test-virtual-machine.(none)>
   Date:   Sun Nov 27 00:34:25 2011 +0800

        Upstream version 5.43.0

