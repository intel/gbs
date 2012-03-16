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
* gbs import : import source tarball or source rpm to git repository
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
then goto the root directory of git repository, run gbs build as follows:
::

  $ gbs build
  $ gbs build -B Test
  $ gbs build -B Test -T home:<userid>:gbs
