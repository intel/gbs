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

* gbs remotebuild : build rpm package from git repository on OBS
* gbs build  : build rpm package from git repository at local
* gbs import : import source rpm or specfile to git repository
* gbs changelog   : generate changelog from git commits to changelog file
* gbs submit : maintain the changelogs file, sanity check etc.
* gbs export : export git tree as tar ball, format of tar ball is from spec

It supports native running in many mainstream Linux distributions, including:

* openSUSE (12.1
* Ubuntu (11.10 and 12.04)

Installation
============
gbs is recommended to install from official repository, but if your system have
not been supported by official repo, you can try to install gbs from source
code, before that, you should install gbs's dependencies such as git, osc, rpm,
build.

Repositories
------------
So far we support `gbs` binary rpms/debs for many popular Linux distributions,
please see the following list:

* openSUSE 12.1
* Ubuntu 11.10
* Ubuntu 12.04

And you can get the corresponding repository on

 `<http://download.tizen.org/tools/>`_

If there is no the distribution you want in the list, please install it from
source code.

Binary Installation
-------------------

openSUSE Installation
~~~~~~~~~~~~~~~~~~~~~
1. Add Tools Building repo:
::

  $ sudo zypper addrepo http://download.tizen.org/tools/openSUSE12.1/ tools-building

2. Update repolist:
::

  $ sudo zypper refresh

3. Install gbs:
::

  $ sudo zypper install gbs

Ubuntu Installation
~~~~~~~~~~~~~~~~~~~~~~~~~~
1. Append repo source:
::

  Append the following line to /etc/apt/source.list:
  #for ubuntu 11.10:
  deb  http://download.tizen.org/tools/xUbuntu_11.10/ /
  #for ubuntu 12.04
  deb  http://download.tizen.org/tools/xUbuntu_12.04/ /

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
* rpm
* build

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
  [remotebuild]
  ; settings for build subcommand
  build_server = <OBS API URL>
  user = <USER_NAME>
  passwd  = <PASSWORD in plaintext> (will be updated w/ base64 encoded one)

  [build]
  build_cmd = /usr/bin/build
  build_root= /var/tmp/build-root-gbs
  su-wrapper= sudo
  distconf=/usr/share/gbs/tizen-1.0.conf
  repo1.url=
  repo1.user=
  repo1.passwd=
  repo2.url=
  repo2.user=
  repo2.passwd=

In this configuration file, there are three sections: [common] is for general
setting, [remotebuild] section is for the options of gbs remotebuild, and [build]
is for gbs build.

In the [remotebuild] section, the following values can be specified:

build_server
    OBS API url, which point to remote OBS. Available value can be:
    https://build.tizen.org
user
    OBS account user name
passwd
    raw OBS account user passwd
passwdx
    encoded OBS account user passwd, this key would be generated automaticlly.

In the [build] section, the following values can be specified:

build_cmd
    build script path for building RPMs in a chroot environment
build_root
    patch for chroot environment
distconf
    Specify distribution configure file
repox.url
    Specify the repo url used for gbs build
repox.user
    Specify the user name for repox
repox.passwd
    Specify the passwd for repox

Usages
======
It's recommended to use `--help` or `help <subcmd>` to get the help message,
for the tool is more or less self-documented.

Running 'gbs remotebuild'
-------------------------

Subcommand `remotebuild` is used to push local git code to remote obs build server
to build. The usage of subcommand `remotebuild` can be available using `gbs remotebuild --help`
::

  remotebuild (rb): remote build package

  Usage:
      gbs remotebuild [options] [package git dir]

  Options:
      -h, --help          show this help message and exit
      -B BASE_OBSPRJ, --base-obsprj=BASE_OBSPRJ
                          Base OBS project being used to branch from, use
                          "Tizen:Main" by default if not specified
      -T TARGET_OBSPRJ, --target-obsprj=TARGET_OBSPRJ
                          OBS target project being used to build package, use
                          "home:<userid>:gbs:Tizen:Main" if not specified

Before running gbs remotebuild, you need to prepare a package git repository
first, and packaging directory must be exist and have spec file in it. The spec
file is used to prepare package name, version and tar ball format, and tar ball
format is specified using SOURCE field in specfile.

Once git reposoritory and packaging directory are  ready,  goto  the  root
directory of git repository, run gbs build as follows:
::

  $ gbs remotebuild
  $ gbs remotebuild -B Test
  $ gbs remotebuild -B Test -T home:<userid>:gbs

Running 'gbs build'
------------------------

Subcommand `build` is used to build rpm package at local by rpmbuild. The
usage of subcommand `build` can be available using `gbs build --help`
::

  build (lb): local build package
  Usage:
      gbs build -R repository -A arch [options] [package git dir]
      [package git dir] is optional, if not specified, current dir would
      be used.
  Examples:
      gbs build -R http://example1.org/packages/ \
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

Examples to run gbs build:

1) Use specified dist file in command line using -D option
::

  $ gbs build -R http://example1.org/ -A i586 -D /usr/share/gbs/tizen-1.0.conf

2) Use dist conf file specified in ~/.gbs.conf, if distconf key exist.
::

  $ gbs build -R http://example1.org/ -A i586

3) Multi repos specified
::

  $ gbs lb -R http://example1.org/  -R http://example2.org/  -A i586

4) With --noinit option, Skip initialization of build root and start with build immediately
::

  $ gbs build -R http://example1.org/ -A i586  --noinit

5) Specify a package git directory, instead of running in git top directory
::

  $ gbs build -R http://example1.org/ -A i586  PackageKit

6) Local repo example
::

  $ gbs build -R /path/to/repo/dir/ -A i586

'''BKM''': to have quick test with local repo, you can run 'gbs build'
with remote repo. rpm packages will be downloaded to localdir /var/cache/\
build/md5-value/, then you can use the following command to create it as local
repo
::

  $ mv /var/cache/build/md5-value/ /var/cache/build/localrepo
  $ cd /var/cache/build/localrepo
  $ createrepo . # if createrepo is not available, you should install it first
  $ gbs build -R /var/cache/build/localrepo/ -A i586/armv7hl

If gbs build fails with dependencies, you should download it manually and
put it to /var/cache/build/localrepo, then createrepo again.

Running 'gbs import'
--------------------

Subcommand `import` is used to import source rpm or unpacked \*.src.rpm to current
git repository. This subcommand is mostly used for initializing git repository
or upgrading packages. Usage of subcommand `import` can be available using
`gbs import --help`
::

  import (im): Import spec file or source rpm to git repository

  Usage:
      gbs import [options] specfile | source rpm | tarball


  Examples:
    $ gbs import /path/to/specfile/
    $ gbs import /path/to/*.src.rpm
    $ gbs import /path/to/tarball
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

3) gbs import tarball must run under the top dir of package git repository, the
following command can be used:
::

  $ cd example/
  $ gbs import example-0.1.tar.gz
  $ gbs import example-0.2-tizen.tar.bz2

Running 'gbs changelog'
-----------------------

Subcommand `changelog` is used to generate changelog file in ./packaging dir.
This subcommand is mostly used for create changelog before submit code.
Usage of subcommand `changelog` can be available using
`gbs changelog --help`
::

  changelog (ch): update the changelog file with the git commit messages

  Usage:
      gbs changelog [--since]

  Examples:
    $ gbs changelog
    $ gbs changelog --since=COMMIT_ID
  Options:
      -h, --help          show this help message and exit
      -s SINCE, --since=SINCE
                          commit to start from

Running 'gbs export'
--------------------

Subcommand `export` is used to export current working git tree as a tar ball.
Usage of subcommand `export` can be available using `gbs changelog --help`
::

  test@test-desktop:~/$ gbs export -h
  export (ex): export files and prepare for build

  Usage:
      gbs export

  Note:

  Options:
      -h, --help          show this help message and exit
      --spec=SPEC         Specify a spec file to use
      -o OUTDIR, --outdir=OUTDIR
                          Output directory

Running 'gbs submit'
--------------------

Subcommand `submit` is used to submit local commits to gerrit for code review.
Usage of subcommand `submit` can be available using `gbs changelog --help`
::

  test@test-desktop:~/$ gbs submit -h
  submit (sr): submit commit request to gerrit for review

  Usage:
      gbs submit -m "msg for commit" [--changelog] [--tag]

  Note:

  Options:
      -h, --help          show this help message and exit
      --branch=TARGET_BRANCH
                          specify the target branch for submit
      --tag               make a tag before submit
      -m MSG, --msg=MSG   specify commit message info
      --changelog         invoke gbs changelog to create changelog
