===
GBS
===

----------------
git build system
----------------
:Date:              2013-10-23
:Copyright:         GPLv2
:Version:           0.19
:Manual section:    1
:Manual group:      System

Git Build System
================

**GBS**  (git-build-system) is a developer command line tool that supports Tizen package development. It's used to generate tarballs based on Git repositories, to do local test buildings, and to submit code to OBS (Tizen's main build service).

This section contains more detailed GBS information. We recommend reading the `Setup Development Environment </documentation/developer-guide/environment-setup/>`_ pages first.

- `Installation or Upgrade </documentation/developer-guide/environment-setup>`_:  How to install or upgrade the tools
- `Configuration File </documentation/reference/git-build-system/configuration-file>`_:  How to modify the configuration for GBS
- `Upstream package management </documentation/reference/git-build-system/upstream-tarball-and-patch-generation-support>`_:  Describes how to manage native and non-native packages in a more proper way
- `GBS Usage </documentation/reference/git-build-system/usage>`_:  Describes, in more detail, how to use GBS
- `FAQ </documentation/reference/git-build-system/faqs>`_:  Frequently Asked Questions

GBS Configuration File
======================

Configuration File Overview
---------------------------
GBS's configuration files are all simple INI-style files that record various choices and settings used by many GBS commands. Some settings represent purely personal preferences, others are vital to a build functioning correctly, and still others tweak command behavior a bit.

**Note:** ".conf" is a common extension for an INI file, an informal standard for configuration files. INI files are simple text files with basic structure composed of sections and properties. Like many tools, GBS supports a hierarchy of configuration files, which are shown below in decreasing precedence:

* **$PWD/.gbs.conf:** project-specific configuration settings that affect only the specific project in the specified working directory. These settings have the highest precedence.

* **/home/<user>/.gbs.conf:** user-specific configuration settings that affect only the specified user.

* **/etc/gbs.conf:** system-wide configuration settings that affect the entire system. These settings have the lowest precedence.

When specifying the configuration file by using -c (--config) option, one of the above files is loaded and applied by GBS. If no configuration file can be found, GBS automatically generates ~/.gbs.conf. Here's an example of specifying one configuration file among a hierarchy of configuration files:

::

    $ gbs -c ~/gbs-my.conf build -A ...

2 Profile Oriented Style of Configuration
-----------------------------------------
This section provides information about the profile oriented style in a GBS configuration file.

2.1 Basic Structure
```````````````````
The basic structure of a configuration file is composed of properties and sections.

2.1.1 Properties
''''''''''''''''
The basic element contained in a configuration file is the property. Every property has a name and a value, delimited by an equal sign (=). The name appears to the left of the equal sign.

2.1.2 Sections
''''''''''''''
Properties may be grouped into various sections, named according to the naming conventions specified in Section 2.2. The section name appears on a line by itself in square brackets ([ ]). All the properties after the section declaration are associated with that section. No explicit "end of section" delimiter is needed. Sections end at the next section declaration or the end of the file. Possible sections include:

* **General section**

  The default profile is defined in the general section and has impacts on GBS behaviors on a general basis. That is, upon the modification of the general section, all GBS behaviors will be changed accordingly. Supported properties include tmpdir, upstream_branch, upstreamtag, buildroot, and packaging_dir.

* **Profile section**

  It is recommended that you set common authentication information in the profile level, instead of repeating identical configurations in various sections. These settings can be automatically passed to OBS and repository sections. Add authentication information to a specific repository or OBS section only when it is unique to the corresponding OBS or repository. In addition, multiple profile sections can exist in one configuration file, enabling the manipulation of GBS behaviors aimed at different devices (for example, mobile phone, IVI) in a central configuration file. For more information, refer to Section 3.2. Supported properties include user, passwd, repos, and obs.

* **OBS section**

  The OBS section specifies the configurations of the remote build server for remote build. Supported properties include url, user, and password.

* **Repository section**

  As with the profile section, multiple repository sections can exist in one configuration file, so, various repositories can be manipulated in "batch". Properties supported include url, user, and password. User and password can be omitted if the corresponding repository does not need authentication information.

2.2 Naming Conventions
``````````````````````
The section names must follow these naming conventions:

* Name the general section exactly as "[general]".
* Start the profile section name with "profile.". For example, [profile.tizen], [profile.IVI].
* Start the OBS section name with "obs.". For example, [obs.tizen].
* Start the repository section name with "repo.".

Here's an example of configuration file:

::

    [general]
    #Current profile name which should match a profile section name
    tmpdir = /var/tmp
    editor =
    packaging_branch = master
    upstream_branch = upstream
    upstream_tag = upstream/${upstreamversion}
    packaging_dir = packaging
    profile = profile.tizen
    buildroot = ~/GBS-ROOT/
    work_dir = .

    [profile.tizen]
    obs = obs.tizen
    repos = repo.tizen_latest
    # If no buildroot for profile, the buildroot in general section will be used
    buildroot = ~/GBS-ROOT-profile.tizen/
    # Specify build conf for a specific profile by using shell-style variable references
    buildconf = ${work_dir}/tizen-conf/build.conf
    # Common authentication information
    user = xxxxx
    passwd = xxxxxx

    [obs.tizen]
    url = https://api.tizen.org
    user = xxxx
    passwd = xxxx
    # set default base_prj for this obs
    #base_prj=Tizen:Main
    # set default target prj for this obs, default is home:<user>:gbs:<base_prj>
    #target_prj=<specify target project>

    [repo.tizen_latest]
    url = http://download.tizen.org/releases/trunk/daily/ivi/latest/
    #Optional user and password, set if differ from profile's user and password
    #user =
    #passwd =

3 Configuration Specification
-----------------------------
This section provides information about the configuration specification.

3.1 Configuring Common Properties
`````````````````````````````````
Typical common properties include buildroot, user, and password. To configure the buildroot to override the default value "~/GBS-ROOT", use this assignment equation:

::

    buildroot=<New_Build_Root>

The reason we need to configure the "passwd" property is because the password line will be automatically converted to an encoded version after running the GBS, as shown in this example:

::

    passwdx = QlpoOTFBWSZTWVyCeo8AAAKIAHJAIAAhhoGaAlNOLuSKcKEguQT1

To reset the password, delete the "passwdx" line above and add this assignment equation:

::

    passwd=<New_Password>

3.2 Configuring Multiple Profiles
`````````````````````````````````
By adding configuration specifications of multiple profiles aimed at various devices in one configuration file, the GBS behaviors oriented for a variety of devices can be manipulated by using a central configuration file. Here's an example of configuring multiple profiles:

::

    [general]
    profile = profile.ivi

    [profile.mobile]
    ...
    [profile.ivi]
    ...

When specifying the profile section by using -P (--profile) option, the specified profile configurations are applied by GBS. Here are examples of specifying one profile among multiple profiles:

::

    $ gbs build --profile=profile.mobile -A i586
    $ gbs remotebuild --profile=mobile

3.3 Configuring Repository
``````````````````````````
This section describes how to configure the repository to adapt the GBS build. The repository configuration specification starts with the section declaration named "[repo.<customized_name>]", and followed by various properties, including:

* url

  The url property specifies the URL of a remote repository, or the full path of a local or remote repository. That is, the following two types of remote repositories are supported:

  - a standard RPM repository that has a repodata/ subdirectory under the /repos/ directory.
  - a Tizen repository that has a builddata/ subdirectory, for example, http://download.tizen.org/releases/daily/2.0alpha/common/latest/

  **Note:** To guarantee the quality of the GBS build, the release folder must be used, instead the snapshot folder.

* user

* passwd

Here's an example of repository configuration specification:

::

    [repo.tizen_latest]
    url = http://download.tizen.org/releases/trunk/daily/ivi/latest/
    user = xxx
    passwd = xxx
    [repo.my_local]
    #local repo must be an absolute path
    url = <Full_Path_of_Local_Repository>

3.4 Shell-Style Variable References
```````````````````````````````````
Properties defined in [general] section can be directly used in other sections by using shell-style variable references in GBS 0.17 and later versions.

Here's an example:

::

    [general]
    tmpdir=/var/tmp
    work_dir=~/test
    [profile.tizen]
    buildconf=${work_dir}/tizen.conf
    buildroot=${tmpdir}/profile.tizen/

Maintenance Models Supported by GBS
===================================

This section describes how to properly manage packages with GBS. "Properly"
here meaning, if we (Tizen) are not the upstream of the package:

- the source archive of the package (orig tarball) contains pristine upstream sources, not polluted with any local changes
- local changes are presented as a series of patches, applied on top of the (pristine) orig archive


Native and non-native packages
------------------------------

From the package maintenance point of view, we can divide the packages into two categories:

- **Native**:  packages where we/you/Tizen is the upstream and controls the source code repository. An example in the context of Tizen could be power-manager. For native packages, we control the versioning and releasing, so package maintenance is simpler. We can release a new version basically whenever we want.
- **Non-native (or upstream)**: packages for which we/you/Tizen is not the upstream. For example, the Linux kernel or zlib. For these packages, we need to follow the releasing process and schedule of the upstream project. For example, from a developer and legal point of view, it is very beneficial to clearly track the local modifications (that is, separate upstream and local changes) both in the source code repository and on the packaging level.


Also GBS divides packages into these two categories. GBS determines a package as non-native, if the git repository has an `upstream` branch. The actual name of the upstream branch can be configured using the 'upstream_branch' in option in the .gbs.conf file or with `--upstream-branch` command line option.

GBS build, remotebuild, and export commands behave differently for native and non-native packages. Namely, the preparation of the packaging files for building differs.

GBS currently supports two different maintenance models for non-native packages: one with packaging and source code in the same branch and one with separate packaging and development branches.

GBS and native packages
```````````````````````

GBS simply creates a monolithic source tarball from the HEAD of the current branch. Packaging files, from the packaging directory, are copied as is. No patch generation is done.

The Git repository layout looks like this:

::

            v1.0    v2.0
              |       |
  o---A---B---C---D---E   master

GBS and non-native packages: joint-packaging, i.e. packaging and development in the same branch
```````````````````````````````````````````````````````````````````````````````````````````````

In the `joint-packaging` model packaging data (spec file etc) is kept in the same branch with the source code:

::

                F---G---H   master (packaging + code changes)
               /
  o---A---B---C---D---E     upstream
              |       |
            v1.0    v2.0

GBS tries to create a (real) upstream source tarball, auto-generate patches from the local changes, and auto-update the spec file accordingly.
The logic is the following:

- Generate patches

  - Create patches between `upstream-tag..HEAD`, remove possible old patches
  - Update the spec file: remove old 'Patch:' tags and '%patch' macros and replace them with ones that correspond with the newly generated patches.

- Create upstream tarball if patch-generation was successful

  - If the git repository has `pristine-tar` branch (and you have the pristine-tar tool installed), GBS tries to checkout the source tarball with pristine-tar
  - If the previous step fails, GBS tries to create a source tarball from the correct `upstream tag`, matching the version taken from the .spec file.

- If source tarball or patch generation fails GBS reverts back to the old method (that is, treats the package as native), creating just one monolithic tarball without patch generation.

You shouldn't have any pre-existing patches in the packaging directory or spec file. Otherwise, GBS refuses to create patches. Please see `Advanced usage/Manually maintained patches` section for manually maintained patches.


GBS and non-native packages: orphan-packaging, i.e. separate packaging and development branches
```````````````````````````````````````````````````````````````````````````````````````````````

In the `orphan-packaging` model packaging data is kept in a separate (orphan) branch with no
source code or common history with the code development branch(es):

::

  o---I---J---K---L         master (packaging)

                F---G---H   development/master/1.0 (local source code changes)
               /
  o---A---B---C---D---E     upstream
              |       |
            v1.0    v2.0

All packaging data, including patches are stored in the packaging branch.
Development branch only contains upstream sources - with no packaging data.
The gbs `devel` command assists in working with the separate branches.

Developers work on the development branch, making changes to the source code.
When the package maintainer wants to release a new version of the package,
he/she exports changes (with gbs `devel` one patch per commit) from the
development branch to the packaging branch, commits the changes, updates
changelog and submits a new version.

When building/exporting the package GBS creates a real upstream source tarball
(similar to the joint-packaging model). Patches are auto-generated (and spec
file auto-modified) when working on the development branch. When working on the
packaging branch the packaging files are exported as is with no modifications.



Building non-native package in the joint-packaging model
--------------------------------------------------------

This is pretty straightforward and easy to use. For GBS to see the package
as non-native (i.e. enable upstream source tarball and patch generation) you
should:

1. have `upstream branch` in the git repository, with untouched upstream sources

2. have `upstream tag` format configured correctly in the package specific .gbs.conf, default is upstream/${upstreamversion}

3. have your `development branch` be based on the upstream version (indicated in .spec)

4. all your local manually maintained patches (in packaging dir) applied in to your development branch and removed from the packaging directory

Additionally, you may have:

5. `pristine-tar branch` in the git repository for generating the upstream tarball with the pristine-tar tool

Doing development is easy: Just edit/commit/build on your development branch. GBS handles the tarball and patch generation, plus updating the spec file. Running gbs should look something like this (using gbs export as an example here for the shorted output):

::

 $ gbs export -o export
 info: Generating patches from git (v1.2.7..HEAD)
 info: Didn't find any old '%patch' macros, adding new patches after the last '%setup' macro at line %s
 info: Didn't find any old 'Patch' tags, adding new patches after the last 'Source' tag.
 info: zlib-1.2.7.tar.bz2 does not exist, creating from 'v1.2.7'
 info: package files have been exported to:
     /home/test/src/zlib/export/zlib-1.2.7-0

When trying out the patch generation for the first time, you might want to export first and examine the auto-updated spec file (in the export directory) to see that GBS updated it correctly. Please see `Advanced usage/Manually maintained patches` section for manually maintained patches.

Reasons for the upstream tarball and/or patch generation failure may be e.g.

- upstream tag was not found

  * version is not present in your git repository
  * tag format is configured incorrectly

- current branch is not a descendant of the upstream version that it claims to be derived from


Building non-native package in the orphan-packaging model
---------------------------------------------------------

In order to use the orphan-packaging model you should:

1. have `upstream branch` in the git repository, with untouched upstream sources

2. have `upstream tag` format configured correctly in the package specific .gbs.conf, default is upstream/${upstreamversion}

3. Have an orphan `packaging branch` that only contains packaging files, including patches

4. Have a `development branch` which is all patches applied on top of the upstream version

Again, additionally, you may have:

5. `pristine-tar branch` in the git repository for generating the upstream tarball with the pristine-tar tool

Code development is done on the `development branch`: just edit/commit/build
similarly to the joint-packaging model. However, all packaging changes are done
in the `packaging branch`. And most importantly, submissions (i.e. relesing to
integration) are done from the `packaging branch`. Before submitting, the
package maintainer creates patches from from the new changes in the
`development branch` and commits these to the `packaging branch`. See the **GBS
devel** section below for detailed instructions how to manage packaging and
development branches with the *gbs devel* command.



Managing upstream sources
-------------------------

This section is only of interest to the package maintainers.

To maintain packages using the model described above, you need to keep unmodified upstream sources in a separate branch in your git repository.
GBS supports two models for this.

Import upstream source archive to git
`````````````````````````````````````

In this model, you import source tarballs (or zip files) from the upstream release to your git repository using the `gbs import` command.  GBS commits the sources in the upstream branch and creates a tag for the upstream release. An example of starting from scratch, that is importing to an empty repo:

::

 $ mkdir zlib && cd zlib && git init
 $ gbs import ../zlib-1.2.6.tar.gz
   ...
 $ git branch
 * master
   upstream
 $ git tag
 upstream/1.2.6

Now you could start development just by adding packaging files to the master branch. When you need to update to a newer upstream version, just use `gbs import` again:

::

 $ gbs import ../zlib-1.2.7.tar.gz
 $ git tag
 upstream/1.2.6
 upstream/1.2.7

**Note** Currently, GBS automatically merges the new upstream version to your master branch. Thus, you need to update the version number in your spec file accordingly.


Tracking remote git
```````````````````

In this model, you directly track a remote (git) repository. You shouldn't use GBS import at all.
GBS needs to know only the name of the upstream branch and the format of the upstream release tags.
These are package dependent information so you should configure them in a package-specific .gbs.conf
in the master branch. An example for starting a package from scratch, again:

::

 $ git clone git://github.com/madler/zlib.git && cd zlib
 $ git branch -m master origin  # to keep origin tracking the upstream
 $ git checkout -b master
 $ vim .gbs.conf
 $ git add .gbs.conf && git commit -m"Add gbs.conf"

The example configuration file would be:

::

 [general]
 upstream_branch = origin
 upstream_tag = v${upstreamversion}

Pristine-tar support
````````````````````

Optionally (but highly recommended!), you can use pristine-tar for storing/checking out the upstream tarballs (see http://joeyh.name/code/pristine-tar/). You can install it from the Tizen tools repository. Pristine-tar guarantees that the tarball generated by GBS is bit-identical to the real upstream release source tarball. GBS uses pristine-tar automatically if you have pristine-tar installed in your system. If you use GBS import to manage the upstream sources everything works out-of-the box: GBS import automatically commits new tarballs to the `pristine-tar branch`.

However, if you track a remote upstream repository directly, you need to commit the upstream source tarballs to pristine-tar branch manually. So, like in our zlib example:

::

 $ cd zlib
 $ git branch
 * master
   origin
 $ pristine-tar commit ../zlib-1.2.7.tar.gz v1.2.7
 $ git branch
 * master
   origin
   pristine-tar

Converting existing repository to a non-native package
------------------------------------------------------

1. You need an `upstream branch`

  a. If you are already tracking the upstream, just configure the upstream branch name and tag format in the package-specific .gbp.conf.
  b. If not, import upstream source tarball with `gbs import` or add the upstream remote to your repo and start tracking that.

2. Recommended: If you're tracking the upstream git directly, you may want to do 'pristine-tar commit <tarball> <upstream-tag>'
3. Rebase your current development branch on the correct upstream version (that is, rebase on the upstream tag)
4. Remove all local patches: apply and commit them on top of your development branch and then remove the patches from the packaging directory and preferably from the spec file, too.
5. Optionally, if you want to maintain the package using the `orphan-packaging`
   model, you can create the packaging and development branches using the `gbs
   devel convert` command.


Advanced usage
--------------

Manually maintained patches
```````````````````````````

GBS supports manually maintaining patches, that is, outside the automatic patch generation. This may be needed
for architecture-dependent patches, for example, as GBS patch generation does not yet support conditional patches.
Another example could be patches that are applied on top of a secondary source tree, whose sources are not maintained
in your git tree, but only as a tarball in your packaging directory.

To use this feature, you need to have your patch(es) in the packaging directory and listed in the spec.  In addition, you need to mark the patch to be ignored by the patch generation/importing by putting `# Gbp-Ignore-Patches: <patch numbers>` into the spec file. This will make GBS ignore the 'Patch:' tags and '%patch' macros of the listed patches when importing or generating patches.  An excerpt of an example spec file:

::

 ...
 Source0:     %{name}-%{version}.tar.bz2
 # Gbp-Ignore-Patches: 0
 Patch0:     my.patch

 %description
 ...

Actually, you can have this special marker anywhere in the spec file. And, it is case-insensitive, so you might use `GBP-IGNORE-PATCHES:`, for example, if you like it better. The reason for the GBP prefix is that GBS uses git-buildpackage (gbp) as the backend for patch generation.

**Note:** In addition, pay attention to patch generation when building or exporting. Also `gbs import` will ignore patches
marked for manual maintenance when importing source rpms.

Patch macro location
````````````````````


GBS tries to automatically find the correct location to add the '%patch' macros in the spec file when updating it with the newly generated patches. This usually works fine, but GBS can also guess wrong. You can manually mark the location for auto-generated '%patch' macros by adding a `# Gbp-Patch-Macros` marker line into the spec file.  An excerpt of an example spec file:

::

 ...
 %prep
 %setup
 # do things here...

 # Gbp-Patch-Macros

 # do more things here...

 %build
 ...

GBS will put the new '%patch' macros after the marker line. This marker is case-insensitive, similar to `# Gbp-Ignore-Patches`.

Squashing commits
`````````````````

When generating patches, GBS supports squashing a range of commits into one monolithic diff.
Currently, one can only squash from `upstream-tag` up to a given commit-ish.
An example use case could be squashing commits from an upstream release up to a stable update
into a single diff (commits on top of the stable generate one patches normally).
You can enable this with the 'squash_patches_until' config file option or with the
'--squash-patches-until' command line option: the format for the option is <commit-ish>[:<filename-base>].

An example:

::

 $ git branch
 * master
   stable
   upstream
 $ gbs export --squash-patches-until=stable:stable-update
 info: Generating patches from git (upstream/0.1.2..HEAD)
 info: Squashing commits a2a7d82..9c0f5ba into one monolithic 'stable-update.diff'
 info: Didn't find any old 'Patch' tags, adding new patches after the last 'Source' tag.
 info: Didn't find any old '%patch' macros, adding new patches after the last '%setup' macro
 info: mypackage-0.1.2.tar.gz does not exist, creating from 'upstream/0.1.2'
 info: package files have been exported to:
      /home/user/src/mypackage/packaging/mypackage-0.1.2-1.21

**Note!** If you're planning to use this, it is highly recommended that you configure it in the package-specific .gbs.conf file. This way, all users (including the automatic build machinery) build/export the package in a similar way.



GBS Usage
=========

This section provides more details about GBS usage. You can also use `$ gbs --help` or `$ gbs <subcmd> --help` to get the help message.

To get help:

- For global options and the command list

::

  $ gbs  -h | --help

- For each sub-command:

::

  $ gbs <sub-command> --help

GBS provides several subcommands, including:


- `gbs clone  </documentation/reference/git-build-system/usage/gbs-clone>`_: clone a git repository representing a package managed with gbs

- `gbs pull  </documentation/reference/git-build-system/usage/gbs-pull>`_: update a git repository representing a package managed with gbs

- `gbs build  </documentation/reference/git-build-system/usage/gbs-build>`_: build rpm package from git repositories at the local development environment

- `gbs remotebuild  </documentation/reference/git-build-system/usage/gbs-remotebuild>`_: generate tarballs based on Git repositories, and upload to remote OBS to build rpm packages

- `gbs submit  </documentation/reference/git-build-system/usage/gbs-submit>`_: create/push annotate tag to Gerrit and trigger code submission to remote OBS

- `gbs chroot  </documentation/reference/git-build-system/usage/gbs-chroot>`_: chroot to build root

- `gbs import  </documentation/reference/git-build-system/usage/gbs-import/>`_: import source code to git repository, supporting these formats: source rpm, specfile, and tarball

- `gbs export  </documentation/reference/git-build-system/usage/gbs-export>`_: export files and prepare for building package, the spec file defines the format of tarball

- `gbs changelog  </documentation/reference/git-build-system/usage/gbs-changelog>`_: update the changelog file with git commits message

- `gbs devel  </documentation/reference/git-build-system/usage/gbs-devel>`_: manage developmet branches and patches in packaging branch

GBS clone
---------
The `gbs clone` command makes it more convenient  for a developer to clone a git repository being maintained with gbs. The benefit of using `gbs clone` (instead of `git clone`) is that it automatically starts to track all relevant branches, the upstream and pristine-tar branches in the case of non-native packages. The clone subcommand also sets up local copies of all these branches.

For instructions on using the clone subcommand, type:

::

  $ gbs clone --help


Example: clone a tizen package using gbs clone

::

  $ gbs clone tizen:toolchains/zlib.git
  info: cloning tizen:toolchains/zlib.git
  .......
  info: finished
  $ cd zlib/
  $ git branch
  * master
  $

Special options
```````````````
The `--all` option can be used to track and create a local copy of all remote branches. Example:

::

  $ gbs clone --all tizen:toolchains/zlib.git
  info: cloning tizen:toolchains/zlib.git
  .......
  Branch 1.0_post set up to track remote branch 1.0_post from origin.
  Branch 2.0alpha set up to track remote branch 2.0alpha from origin.
  info: finished
  $ cd zlib/
  $ git branch
    1.0_post
    2.0alpha
  * master

You can use the `--depth` command line option to create shallow clones of the remote repository. This can be used to preserve space and potentially greatly speed up the clone operation if you're only interested in the most recent changes of a project.

GBS pull
--------

The `pull` command makes it more convenient for a developer to update from a remote git repository being maintained with gbs. The benefit of using gbs pull is that it automatically updates all relevant branches, the upstream and pristine-tar branches in the case of non-native packages.

The `pull` subcommand will update all local branch HEADs that can be fast-forwarded. It will print a warning for branches that could not be fast-forwarded. See the `--force` option below to override this. It is recommended to always do your local development on feature/development brances, and keep the master/upstream branches untouched and always in sync with the remote by using the gbs pull command.

For instructions on using the pull subcommand, type:

::

  $ gbs pull --help

Example: update a tizen package repo using gbs pull

::

  $ gbs pull
  info: updating from remote
  .....
  info: Updating 'master'
  Updating 30e59a6..7ae7fc7
  Fast-forward
  info: finished

Special options
```````````````

The `--all` option can be used to update all remote branches. Using this will update all remote-tracking branches that have identical name in the remote repository.

Using the `--depth` one can deepen shallow clones, that is, fetch deeper history from the remote.

With the --force option the developer can force update the local branch HEADs to match the remote repo.

**WARNING**: Use the `--force` option with care. It will discard all local changes to the updated branches! This effectively does a `git reset --hard` for the local branches. Example:

::

  $ gbs pull --all
  info: updating from remote
  .....
  info: Branch '1.0_post' is already up to date.
  warning: Skipping non-fast forward of '2.0alpha' - use --force or update manually
  info: Updating 'master'
  Updating 30e59a6..7ae7fc7
  Fast-forward
  error: Failed to update some of the branches!
  $ gbs pull --all --force
  info: updating from remote
  ......
  info: Branch '1.0_post' is already up to date.
  info: Checking out clean copy of '2.0alpha' due to --force=clean
  info: Updating '2.0alpha'
  info: Branch 'master' is already up to date.
  info: finished

GBS build
---------

By using 'gbs build', the developer can build the source code and generate rpm packages locally.
For instructions on using the `build` subcommand, use this command: `gbs build --help`

::

 $ gbs build -h

gbs build workflow
``````````````````

Input of gbs build
''''''''''''''''''
Below is the input for gbs build:

- git project(s) which contains rpm packaging files
- binary rpm repositories (remote or local)
- project build configurations (macros, flags, etc)

The binary rpm repositories contain all the binary rpm packages which are used to create the chroot environment and build packages, which can be remote, like tizen release or snapshot repositories, or local repository. Local repository supports two types:

- A standard repository with repodata exists
- A normal directory contains RPM packages. GBS will find all RPM packages under this directory.

Please refer to `Configuration File </documentation/reference/git-build-system/configuration-file>`_ part to configure a repository.

Build workflow
''''''''''''''

The input and output of gbs build are all repositories.

**Note**: All the rpm packages under the output repository (by default, ~/GBS-ROOT/local/repos/<VERSION>/) will be used when building packages. That is, all the packages under the output repository will be applied to the build environment, so make sure the output repository is clean if you don't want this behavior.

Here's the basic gbs build workflow

::

   ____________________
  |                    |      ___________
  | Source Code (GIT)  |---->|           |      _________________________
  |____________________|     |           |     |                         |
                             |           |     |  Local repository of    |
   ____________________      | GBS Build |---->|  build RPM packages     |
  |                    |     |           |     |(~/GBS-ROOT/local/repos/)|
  |Binary repositories |     |           |     |_________________________|
  |in GBS conf         |---->|___________|                  |
  |(Remote or Local)   |           ^                        |
  |____________________|           |________________________|


From the above diagram, we can see the input and input are all repositories and the output repository located at '~/GBS-ROOT/locals/repos/' by default. You can change the repo path by using '--buildroot' to specify a different build root.

Local repos in gbs build root ('~/GBS-ROOT' by default) will affect build results, so you must make sure that repos don't contains old or unnecessary RPM packages. While running gbs build, you can specify '--clean-repos' to clean up local repos, which gbs created, before building. We recommend that gbs users set different gbs build root directories for different profiles. There are several ways:

- By default, the GBS build will put all output files under ~/GBS-ROOT/.
- If the environment variable TIZEN_BUILD_ROOT exists, ${TIZEN_BUILD_ROOT} will be used as output top dir
- If -B option is specified, then the specified directory is used, even if ${TIZEN_BUILD_ROOT} exists


Output of gbs build
'''''''''''''''''''

Structure of a GBS build root directory

::

  gbs output top dir
  |-- local
  |   |-- cache                    # repodata and RPMs from remote repositories
  |   |-- repos                    # generated local repo top directory
  |   |   |-- tizen                # distro one: tizen
  |   |   |   |-- armv7l           # store armv7l RPM packages
  |   |   |   |-- i586             # store x86 RPM packages
  |   |   `-- tizen2.0             # build for distro two: tizen2.0
  |   |       `-- i586             # the same as above
  |   |-- scratch.armv7l.0         # first build root for arm build
  |   |-- scratch.i586.0           # second build root for x86 build
  |   |-- scratch.i586.1           # third build root for x86 build
  |   |-- scratch.i586.2           # fourth build root for x86 build
  |   |-- scratch.i586.3           # fifth build root for x86 build
  |   |                            # The above build root dir can be used by gbs chroot <build root dir>
  |   `-- sources                  # sources generated for build, including tarball, spec, patches, etc.
  |       |-- tizen
  |       `-- tizen2.0
  `-- meta                         # meta data used by gbs

GBS Build Examples (Basic Usage)
````````````````````````````````

1. Build a single package.

::

   $ cd package1
   $ gbs build -A i586

2. Build the package for a different architecture.

::

   $ gbs build -A armv7l      #build package for armv7l
   $ gbs build -A i586        #build package for i586

3. Make a clean build by deleting the old build root. This option must be specified if the repo has been changed, for example, changed to another release.

::

   $ gbs build -A armv7l --clean

4. Build the package with a specific commit.

::

   $ gbs build -A armv7l --commit=<COMMIT_ID>

5. Use `--overwrite` to trigger a rebuild.

If you have already built before, and want to rebuild, `--overwrite` should be specified, or the packages will be skipped.

::

   $ gbs build -A i586 --overwrite

If you change the commit or specify `--include-all` option, it will always rebuild, so `--overwrite` is not needed.

6. Output the debug info.

::

   $ gbs build -A i586 --debug

7. Build against a local repository. You can config the local repo at .gbs.conf file or through the command line.

::

   $ gbs build -R /path/to/repo/dir/ -A i586

8. Use `--noinit` to build package in offline mode
`--noinit` option can only be used if build root is ready. With `--noinit` option, gbs will not connect the remote repo, and skip parsing & checking repo and initialize build environment. `rpmbuild` will be used to build the package directly. Here's an example:

::

  $ gbs build -A i586           # build first and create build environment
  $ gbs build -A i586 --noinit  # use --noinit to start building directly

9. Build with all uncommitted changes using `--include-all`.

For example, the git tree contains one modified file and two extra files:

::

   $ git status -s
   M ail.pc.in
   ?? base.repo
   ?? main.repo

- Build without the `--include-all` option

Builds committed files only. All the modified files, which are not committed nor added, will NOT be built:

::

    $ gbs build -A i586
    warning: the following untracked files would NOT be included: base.repo main.repo
    warning: the following uncommitted changes would NOT be included: ail.pc.in
    warning: you can specify '--include-all' option to include these uncommitted and untracked files.
    ....
    info: Binaries RPM packages can be found here:
    /home/test/GBS-ROOT/local/scratch.i586.0/home/abuild/rpmbuild/RPMS/
    info: Done

- Build with the `--include-all` option builds all the files:

::

    $ gbs build -A i586 --include-all
    info: the following untracked files would be included: base.repo main.repo
    info: the following un-committed changes would be included: ail.pc.in
    info: export tar ball and packaging files
    ...
    ...
    [build finished]

- Use .gitignore to ignore specific files, when using the `--include-all` option. If you want to ignore some files types, you can update your .gitignore. For example:

::

    $ cat .gitignore
    .*
    */.*
    *.pyc
    *.patch*



Incremental build
`````````````````

Incremental Concept
'''''''''''''''''''

Starting from gbs 0.10, the gbs build subcommand supports building incrementally, which can be enabled by specifying the '--incremental' option.

This mode is designed for development and verification of single packages. It is not intended to replace the standard mode. Only one package can be built at a time using this mode.

This mode will set up the build environment in multiple steps, finishing by mounting the local Git tree of a package in the chroot build environment.

**Note**: Because gbs will mount your git tree to the build root, be very careful when you remove your build root. You need to make sure you've already umounted the source tree manually before you remove it.

This has the following benefits:

1. The build environment uses the latest source code and changes to source do not trigger a new build environment (in the chroot).
2. The Git source tree becomes the source of the builds.  Any change made in the Git repository followed by invocation of the build script will build the changed sources
3. If the build fails for some reason, the build script will continue from the spot where it has failed, once the code has been changed to fix the problem causing the failure.

This mode is, in many ways, similar to traditional code development, where changes are made to sources, followed by running `make` to test and compile the changes. However, it enables development using the build environment of the target, instead of the host OS.

This method has some limitations, mostly related to packaging and how the sources are maintained.  Among others, it depends on how the RPM spec file is composed:

1. It does not support patches in the spec file. All source has to be maintained as part of the Git tree
2. It requires a clean packaging workflow.  Exotic workflows in the spec files might not work well, because this mode expects the following model:

   a. Code preparation (%prep)
   b. Code building (%build)
   c. Code installation (%install)

3. Because we run the %build section every time, if the %build script has configuration scripts (auto-tools), binaries might be regenerated, causing a complete build every time.  To avoid this, you are encouraged to use the following macros, which can be overridden using the `--no-configure` option:

   a. %configure: runs the configure script with pre-defined paths and options.
   b. %reconfigure: regenerates the scripts and runs %configure
   c. %autogen: runs the autogen script


Example
'''''''

In this example, we use `dlog` source code. First, we need to build with --incremental, then just modify one source file, and trigger the incremental build again. We will see that only modified source code has been compiled during the incremental build.

::

  $ cd dlog
  # first build:
  $ gbs build -A i586 --incremental
  $ vim log.c # change code
  # second build:
  $ gbs build -A i586 --incremental
  info: generate repositories ...
  info: build conf has been downloaded at:
  /var/tmp/test-gbs/tizen.conf
  info: Start building packages from: /home/test/packages/dlog (git)
  info: Prepare sources...
  info: Retrieving repo metadata...
  info: Parsing package data...
  info: *** overwriting dlog-0.4.1-5.1 i586 ***
  info: Next pass:
  dlog
  info: *** building dlog-0.4.1-5.1 i586 tizen (worker: 0) ***
  info: Doing incremental build
  [    0s] Memory limit set to 10854336KB
  [    0s] Using BUILD_ROOT=/home/test/GBS-ROOT/local/scratch.i586.0
  [    0s] Using BUILD_ARCH=i686:i586:i486:i386:noarch
  [    0s] test-desktop started "build dlog.spec" at Thu Sep 13 07:36:14 UTC 2012.
  [    0s] -----------------------------------------------------------------
  [    0s] ----- building dlog.spec (user abuild)
  [    0s] -----------------------------------------------------------------
  [    0s] -----------------------------------------------------------------
  [    0s] + rpmbuild --short-circuit -bc /home/abuild/rpmbuild/SOURCES/dlog.spec
  [    0s] Executing(%build): /bin/sh -e /var/tmp/rpm-tmp.XLz8je
  [    0s] + umask 022
  [    0s] + export LD_AS_NEEDED
  [    4s] + make -j4
  [    4s] make  all-am
  [    4s] make[1]: Entering directory /home/abuild/rpmbuild/BUILD/dlog-0.4.1
  [    4s] /bin/sh ./libtool --tag=CC   --mode=compile gcc -c -o log.lo log.c
  [    4s] mv -f .deps/log.Tpo .deps/log.Plo
  [    4s] /bin/sh ./libtool --tag=CC --mode=link gcc -o libdlog.la /usr/lib log.lo
  [    4s] libtool: link: gcc -shared  .libs/log.o -o .libs/libdlog.so.0.0.0
  [    4s] libtool: link: ar cru .libs/libdlog.a  log.o
  [    4s] libtool: link: ranlib .libs/libdlog.a
  [    4s] make[1]: Leaving directory /home/abuild/rpmbuild/BUILD/dlog-0.4.1
  [    4s] + exit 0
  [    4s] finished "build dlog.spec" at Thu Sep 13 07:36:18 UTC 2012.
  [    4s]
  info: finished incremental building dlog
  info: Local repo can be found here:
  /home/test/GBS-ROOT/local/repos/tizen/
  info: Done

From the buildlog, we can see that only log.c has been re-compiled. That's the incremental build behavior.

`--noinit` option can be used together with `--incremental` to make a build more quickly, like:

::

  $ gbs build --incremental --noinit



Limitations of Incremental Build
''''''''''''''''''''''''''''''''

Incremental build doesn't support all packages. Here are some limitations:

- Incremental build currently supports building only a single package. It doesn't support building multiple packages in parallel
- The tarball's name in the spec file should be %{name}-%{version}.{tar.gz|tar.bz2|zip|...}, otherwise GBS can't mount source code to build the root correctly
- %prep section should only contains %setup macro to unpack tarball, and should not contains other source code related operations, such as unpack another source, apply patches, etc.


Multiple packages build (dependency build)
``````````````````````````````````````````

Multiple package build has been supported since gbs 0.10. If packages have dependencies on each other, gbs will build packages in the correct order calculated by dependency relationship. Previously built out RPMs will be used to build the following packages that depend on them, which is the dependency build.

**Examples**:

1. Build all packages under a specified package directory

::

   $ mkdir tizen-packages
   $ cp package1 package2 package3 ... tizen-packages/
   $ gbs build -A i586 tizen-packages # build all packages under tizen-packages

2. Build multiple packages in parallel with `--threads`

::

   # current directory have multiple packages, --threads can be used to set the max build worker at the same time
   $ gbs build -A armv7l --threads=4

3. Select a group of packages to be built

The --binary-from-file option specifies a text file that contains a name list of RPM packages to be built. The format in the text file is one package per line.

The --binary-list option specifies a list in which the package names are separated by comma.

When the number of packages is small, thus the packages can be clearly presented in command line, it is recommended to use the --binary-list option for simplicity.

::

  $ gbs build -A i586 --binary-from-file=/path/to/packages.list
  $ gbs build -A i586 --binary-list=<pkg1>,<pkg2>

4. Exclude certain packages.

The --exclude option specifies a list in which the names of packages to be ignored are separated by comma.
The --exclude-from-file option specifies a text file  that contains a name list of packages to be ignored.

::

  $ gbs build -A i586 tizen-packages --exclude=<pkg1>
  $ gbs build -A i586 tizen-packages --exclude=<pkg1>,<pkg2>
  $ gbs build -A i586 tizen-packages --exclude-from-file=/path/to/packages.list

5. Build packages based on dependencies.
The --deps option enables GBS to build specific packages, together with all the related packages on which they depend.The --rdep option enables GBS to build specific packages, together with all the related packages that depend on them.

The specific packages can be included by the --binary-from-file option or the --binary-list option, and be excluded by the --exclude option or the --exclude-from-file option.

These two options are compatible. When added at the same time, besides the specific packages, GBS will build not only the related packages on which they depend, but also all the related packages that depend on them.

::

  $ gbs build -A i586 --binary-list=<pkg1>,<pkg2> --deps
  $ gbs build -A i586 --binary-list=<pkg1>,<pkg2> --rdeps
  $ gbs build -A i586 --binary-list=<pkg1>,<pkg2> --deps --rdeps

Other useful options
````````````````````

Install extra packages to build root
''''''''''''''''''''''''''''''''''''

`--extra-packs=<pkgs list sep by comma>` can be used to install extra packages:

::

  $ gbs build --extra-packs=vim,zypper,gcc,gdb ...

Keep all packages in build root
'''''''''''''''''''''''''''''''

Generally, `gbs build` will remove unnecessary packages in build root. While transferring to build another package, you can use `--keep-packs` to keep all unnecessary packages, and just install missing build required packages. This option can be used to speed up build multiple packages.

::

  $ gbs build --keep-packs

`--keep-packs` can be used to create one build root for building multiple packages. Once the build root is ready, you can use --noinit to build these packages quickly.

::

$ gbs build pkg1/ --keep-packs -A i586
$ gbs build pkg2/ --keep-packs -A i586
$ gbs build pkg3/ --keep-packs -A i586

Now, the build root (~/GBS-ROOT/local/scratch.i586.0) is ready for building pkg1, pkg2, and pkg3. You can use --noinit to build them offline, and don't need waste time to check repo updates and build root.

::

$ gbs build pkg1 --noinit
$ gbs build pkg2 --noinit
$ gbs build pkg3 --noinit


Fetch the project build conf and customize build root (for Advanced Users)
``````````````````````````````````````````````````````````````````````````

Project build conf describes the project build configurations for the project, including pre-defined macros/packages/flags in the build environment. In Tizen releases, the build conf is released together with the released repo. You can find an example at: http://download.tizen.org/releases/daily/trunk/ivi/latest/builddata/xxx-build.conf

- gbs build will fetch the build conf automatically

Starting from gbs 0.7.1, by default, gbs will fetch the build conf from a remote repo, if you specify the remote Tizen repo, and then store it in your temp environment. Here's the build log:

::

    $ gbs build -A i586
    info: generate repositories ...
    info: build conf has been downloaded at:
    /var/tmp/<user>-gbs/tizen2.0.conf
    info: generate tar ball: packaging/acpid-2.0.14.tar.bz2
    [sudo] password for <user>:

- build the package using your own project build conf, using the -D option


You can save it and modify it, and then use it for your purposes:

::

 cp /var/tmp/<user>-gbs/tizen2.0.conf ~/tizen2.0.conf
 $ gbs build -A i586 -D ~/tizen2.0.conf

If you need to customize the build config, refer to: http://en.opensuse.org/openSUSE:Build_Service_prjconf


GBS remotebuild
---------------

Use the `remotebuild` subcommand to push local git code to the remote OBS build server
to build. For instructions on using the `remotebuild` subcommand, use this command:

::

 $ gbs remotebuild --help

Before running gbs remotebuild, you need to prepare a git repository package. The packaging directory must exist and have a spec file in it. GBS uses the package name, version, and source tarball format defined in this spec file.
When it's ready, go to the top directory of git repository, and run gbs remotebuild, here's some examples

::

 $ gbs remotebuild
 $ gbs remotebuild -B Tizen:Main
 $ gbs remotebuild -B Tizen:Main -T home:<userid>:gbs
 $ gbs remotebuild -B Tizen:Main --status
 $ gbs remotebuild -B Tizen:Main --buildlog -R <repo> -A <arch>
 $ gbs remotebuild -B Tizen:Main --include-all

check build log and build status

gbs supports the developer checking the build log and build status using the `--buildlog` and `--status` options during gbs remotebuild. For example:

Step 1: Submit the changes to the remote OBS using `gbs remotebuild`. For example:

Submit package to `home:user:gbs:Tizen:Main`, build against Tizen:Main

::

    test@test-desktop:~/ail$ gbs remotebuild -B Tizen:Main --include-all
    info: Creating (native) source archive ail-0.2.29.tar.gz from 'c7309adbc60eae08782b51470c20aef6fdafccc0'
    info: checking status of obs project: home:test:gbs:Tizen:Main ...
    info: commit packaging files to build server ...
    info: local changes submitted to build server successfully
    info: follow the link to monitor the build progress:
      https://build.tizendev.org/package/show?package=ail&project=home:test:gbs:Tizen:Main

Step 2: Check the build status, example:

::

    # -B or -T options is needed if your target project is not home:user:gbs:Tizen:Main
    test@test-desktop:~/ail$ gbs remotebuild --status
    info: build results from build server:
    standard       i586           building
    standard       armv7el        building

The first column is repo name and the second column is arch. repo/arch can be used to get buildlog.

Step 3: Check the build log for special repo/arch

::

    test@test-desktop:~/ail$ gbs remotebuild --buildlog
    error: please specify arch(-A) and repository(-R)
    test@test-desktop:~/ail$ gbs remotebuild --buildlog -A i586 -R standard
    info: build log for home:test:gbs:Tizen:Main/ail/standard/i586
    ....


GBS submit
----------

gbs submit can help the user create/push tags to gerrit, which would trigger pushing code from gerrit to OBS.
You can get the usage of subcommand `submit` by:

::

 $ gbs submit --help


Examples
````````
1) Create a tag on a current working branch and submit it directly.

::

  $ gbs submit -m 'release for 0.1'

GBS would create an annotated tag named 'submit/${cur_branch_name}'/${date}.${time} on 'HEAD' commit, then submit it directly.

2) Use `-c` option to submit specified commit

::

  $ gbs submit -c <commit_ID> -m 'release for 0.2'

3) Use '--target' option to specify the target version to submit

::

  $ gbs submit --target=trunk -m 'release for 0.2.1'

**Note**: `--target` allows the user to specify the target version. By default, it is 'trunk'. The valid value of `--target` should be matched with the remote branch name. The backend service would use this branch info to create the SR and submit it to the correct OBS project.

4) use `-r` to specify remote gerrit server to submit. By default '-r' is 'origin'.

::

  $ gbs submit -r tizen:public/base/gcc -m 'release for 0.4'

5) If your gpg key has been set, you can use '-s' to create a signed tag.

::

  $ gbs submit -m 'release for 0.3' -s

GBS chroot
----------

The subcommand 'chroot' allows users to chroot to the buildroot directory, which is generated by `gbs build`. You can get the basic usage of gbs chroot using:

::

  $ gbs chroot --help

**Note**: The default location of the build root is located at: ~/GBS-ROOT/local/scratch.{arch}.*, which will be different if the -B option is specified while running gbs build

Examples:

- Create build root with more extra packages to the build root

::

  $ gbs build --extra-packs=zypper,vim -A i586 # install zypper,vim to build root

For more gbs build options, please refer to gbs build page.

- Chroot to buildroot, example: chroot to ~/GBS-ROOT/local/scratch.i586.0/

::

 $ gbs chroot ~/GBS-ROOT/local/scratch.i586.0/

- Chroot as 'root' user

::

 $ gbs chroot -r ~/GBS-ROOT/local/scratch.i586.0/

If gbs chroot failed with error:'su: user root does not exist', which is caused by tizen pacakge: `login`, which should be fixed from repository. Currently, you can add root user manually by:

::

  $sudo echo "root:x:0:0:root:/root:/bin/bash" >>path/to/buildroot/etc/passwd
  $sudo echo "root:x:0:" >>path/to/buildroot/etc/group

With this update, gbs chroot should work.

- Chroot and install more extra packages into buildroot directory for development purposes

::

  chroot as 'root':
  $ gbs chroot -r ~/GBS-ROOT/local/scratch.i586.0/
  Configure tizen repo in the chroot env:
  # zypper ar http://user:passwd@download.tizen.org/releases/daily/<release_id>/repos/main/ia32/packages tizen-main
  # zypper ar http://user:passwd@download.tizen.org/releases/daily/<release_id>/repos/base/ia32/packages tizen-base
  Install extra packages, for example, install gdb.
  # zypper refresh
  # zypper -n install gdb gcc

For https repositories, you need to specify 'ssl_verify=no'. For example:

::

  # zypper ar https://user:passwd@tizen.org/releases/daily/<release_id>/repos/main/ia32/packages/?ssl_verify=no tizen-main

Notes:

- If you want to use as 'root', you need specify '-r' option, then zypper can be used to install/remove packages
- If you want to install packages in the build root env, you need specify the '-n' option, such as: zypper -n install gdb

GBS import
----------

The subcommand will help to import source code or existing source rpm packages into the git repository. Most of the time, it is used for initializing a git repository or for upgrading packages. It supports these formats: source rpm, specfile, and tarball.

For instructions on using the `import` subcommand, use this command: `gbs import --help`

::

$ gbs import --help

Importing source packages
`````````````````````````

Import from a source rpm
''''''''''''''''''''''''

::

  $ gbs import sed-4.1.5-1/sed-4.1.5-1.src.rpm
  info: No git repository found, creating one.
  Initialized empty Git repository in /home/test/sed/.git/
  info: Tag upstream/4.1.5 not found, importing Upstream upstream sources
  info: Will create missing branch 'upstream'
  pristine-tar: committed sed-4.1.5.tar.gz.delta to branch pristine-tar
  info: Importing packaging files
  info: Will create missing branch 'master'
  info: Version '4.1.5-1' imported under 'sed'
  info: done.
  $ git tag
  upstream/4.1.5
  vendor/4.1.5-1
  $ cd sed && git branch
  * master
    pristine-tar
    upstream


Import from spec file
'''''''''''''''''''''

::

  $ gbs import sed-4.1.5-1/sed.spec
  info: No git repository found, creating one.
  Initialized empty Git repository in /home/test/sed/.git/
  info: Tag upstream/4.1.5 not found, importing Upstream upstream sources
  info: Will create missing branch 'upstream'
  pristine-tar: committed sed-4.1.5.tar.gz.delta to branch pristine-tar
  info: Importing packaging files
  info: Will create missing branch 'master'
  info: Version '4.1.5-1' imported under 'sed'
  info: done.
  $ cd sed && git branch
  * master
    pristine-tar
    upstream
  $ git tag
  upstream/4.1.5
  vendor/4.1.5-1

Special options for importing source packages
'''''''''''''''''''''''''''''''''''''''''''''

If the source package contains patches, gbs will try to apply patches on top of master branch:

::

  $ cat sed-patch/sed.spec
  ...
  URL:        http://sed.sourceforge.net/
  Source0:    ftp://ftp.gnu.org/pub/gnu/sed/sed-%{version}.tar.gz
  Source1001: packaging/sed.manifest
  Patch0:     0001-hello.patch
  %description
  ...
  $ gbs import sed-patch/sed.spec
  info: No git repository found, creating one.
  Initialized empty Git repository in /home/test/sed/.git/
  info: Tag upstream/4.1.5 not found, importing Upstream upstream sources
  info: Will create missing branch 'upstream'
  pristine-tar: committed sed-4.1.5.tar.gz.delta to branch pristine-tar
  info: Importing packaging files
  info: Will create missing branch 'master'
  info: Importing patches to 'master' branch
  info: Removing imported patch files from spec and packaging dir
  info: Version '4.1.5-1' imported under 'sed'
  info: done.
  $ cd sed && git log --oneline
  d94118f Autoremove imported patches from packaging
  5d1333f hello
  3a452d7 Imported vendor release 4.1.5-1
  12104af Imported Upstream version 4.1.5
  $ cat packaging/sed.spec
  ...
  URL:        http://sed.sourceforge.net/
  Source0:    ftp://ftp.gnu.org/pub/gnu/sed/sed-%{version}.tar.gz
  Source1001: packaging/sed.manifest
  %description
  ...

The `--no-patch-import` option disabled automatic patch import, i.e. gbs does not try to apply patches on top of the master branch. You should apply patches manually or mark them as manually maintained (see `manually maintained patches </documentation/reference/git-build-system/upstream-tarball-and-patch-generation-support>`_)

With `--native` command line option you can specify the package as a native package, with no separate upstream. No upstream git branch is created and it is assumed that all content, including packaging files are found in the source tarball inside the source package.

Using the `--allow-same-version` option you can re-import an already imported version of the package. This will not re-import the upstream sources, it'll only re-import the packaging files to the master branch.

You can use the `--packaging-dir` option to define the directory for packaging files, i.e. some other than the default 'packaging/'. This may be needed e.g. if the upstream source sources already have a directory named 'packaging'. If you use this option you sould also define this setting in the package-specific .gbs.conf file (in all relevant branches) so that the remote repository and all other users get the correct setting, too.

Importing upstream sources
``````````````````````````

Importing source tarball  can be used to upgrade a package. `gbs import` can only work if `upstream` branch exists. Once `gbs import` succeeded, new tarball will be unpacked and import to `upstream` branch. If `pristine-tar` branch exists, tarball is also be imported to pristine-tar branch.

::

  $ gbs import ../sed-4.2.0-1/sed-4.2.0.tar.gz
  What is the upstream version? [4.2.0]
  info: Importing '/home/test/sed-4.2.0-1/sed-4.2.0.tar.gz' to branch 'upstream'...
  info: Source package is sed
  info: Upstream version is 4.2.0
  pristine-tar: committed sed-4.2.0.tar.gz.delta to branch pristine-tar
  info: Successfully imported version 4.2.0 of /home/test/sed-4.2.0-1/sed-4.2.0.tar.gz
  info: done.
  test@test-desktop:~/sed$ git tag
  upstream/4.1.5
  upstream/4.2.0
  $ git log --oneline
   d3d25a7 Imported vendor release 4.1.5-1
   1f6acaa Imported Upstream version 4.1.5
  $ git checkout upstream && git log --oneline
   Switched to branch 'upstream'
   23220e6 Imported Upstream version 4.2.0
   1f6acaa Imported Upstream version 4.1.5
  $ git checkout pristine-tar && git log --oneline
   Switched to branch 'pristine-tar'
   7d44dad pristine-tar data for sed-4.2.0.tar.gz
   71ee336 pristine-tar data for sed-4.1.5.tar.gz

Special options for importing upstream sources
''''''''''''''''''''''''''''''''''''''''''''''

If you want to merge imported upstream branch to master automatically, `--merge` can be used:

::

  $ gbs import --merge ../sed-4.2.0-1/sed-4.2.0.tar.gz
  What is the upstream version? [4.2.0]
  info: Importing '/home/test/sed-4.2.0-1/sed-4.2.0.tar.gz' to branch 'upstream'...
  info: Source package is sed
  info: Upstream version is 4.2.0
  pristine-tar: committed sed-4.2.0.tar.gz.delta to branch pristine-tar
  info: Merging to 'master'
  Merge made by recursive.
  info: Successfully imported version 4.2.0 of /home/test/sed-4.2.0-1/sed-4.2.0.tar.gz
  info: done.
  $ git log --oneline
   cc58b4c Merge commit 'upstream/4.2.0'
   1f157c3 Imported Upstream version 4.2.0
   482ef23 Imported vendor release 4.1.5-1
   fc76416 Imported Upstream version 4.1.5

You can use the `--upstream-vcs-tag` option in case you track upstream git directly, but still want to import the official release tarballs. Using this option, you get the complete git history of the upstream git in to your upstream branch. And, the diff between the real upstream git tag and the release tarball (e.g. added autotools macros) is shown as one commit on top of the real upstream git tag.

Common options for importing source packages and upstream sources
`````````````````````````````````````````````````````````````````

This section describes the advanced command line options that are applicable for importing both source packages and upstream source archives.

The `--upstream-branch` option may be used to define the upstream branch name. If you do this, you sould also define that in the package-specific .gbs.conf file (in all relevant branches), similarly to the '--packaging-dir' option.

The `--no-pristine-tar` option disables the use of the pristine-tar tool. That is, gbs will not import the upstream
source tarball to pristine-tar branch.

With the `--filter` option one can filter out files from the upstream source archive. For example, you may need to filter out the .git directory from the upstream tarball (with `--filter=.git`). This option can be given multiple times.

GBS Export
----------


Use 'gbs export' to export git tree to tarball and spec file.  You can see how to use the `export` subcommand by using this command:

::

 $ gbs export --help

Examples:

- export source code to default packaging directory

::

  $ gbs export
  info: Generating patches from git (upstream/4.1.5..HEAD)
  info: Didn't find any old 'Patch' tags, adding new patches after the last 'Source' tag.
  info: Didn't find any old '%patch' macros, adding new patches after the last '%setup' macro
  pristine-tar: successfully generated /var/tmp/.gbs_export_UJn0nS/sed-4.1.5.tar.gz
  info: package files have been exported to:
       /home/test/sed/packaging/sed-4.1.5-1
  $ diff packaging/sed.spec packaging/sed-4.1.5-1/sed.spec
  11a12,13
  > # Patches auto-generated by git-buildpackage:
  > Patch0:     0001-hello.patch
  25a28,29
  > # 0001-hello.patch
  > %patch0 -p1


From the log we can see patches has been generated, and tarball is created from `pristine-tar` branch. `--no-patch-export` option can be used to disable this feature, and tarball will be generated from current branch directly.


- Use -o option to generate packaging files to specified path

::

 $ gbs export  -o ~/

- Using `--source-rpm` option to generate source RPM package:


::

 $ gbs export  -o ~/ --source-rpm

- Using `--spec` option, if there are multiple spec files

::

$ gbs export  --spec=dlog.spec

`--spec` only accept file name should not contains any path info. gbs will prefix `packaging` dir automatically.


GBS Changelog
-------------


Subcommand `changelog` is used to generate changelog file in ./packaging dir. It is mostly used for creating a changelog before submitting code.
You can get the usage of subcommand `changelog` by using '$ gbs changelog --help'

 $ gbs changelog --help

Examples:

::

 test@test-desktop:~/acpid$ gbs ch --since=bed424ad5ddf74f907de0c19043e486f36e594b9
 info: Change log has been updated.
 test@test-desktop:~/acpid$ head packaging/acpid.changes
 * Wed May 30 2012 xxxx <xxxx@example.com> 2.0.14@5c5f459
 - cleanup specfile for packaging
 * Wed May 30 2012 - xxxx <xxxx@example.com> - 2.0.10


GBS devel
---------

The `devel` subcommand is used in managing development branch(es) and exporting
patches to the an oprhan packaging branch. The `devel` subcommand is mostly
designed for package maintainers who are responsible for maintaining the
packaging branch (in the "orphan packaging branch" model). It has several
actions:
1. `start` for creating a development branch
2. `export` for exporting patches from a development branch to a packaging branch
3. `drop` for removing a development branch
4. `switch` for switching between packaging branch and development branch
5. `convert` for converting a package the "orphan packaging branch" model

Each upstream version will have a dedicated development branch, e.g.
`development/master/1.0` for upstream version 1.0.

For quick help on using the `devel` subcommand, use this command:
`gbs devel --help`

::

$ gbs devel --help

devel start: create a development branch
````````````````````````````````````````

The `start` action is used for creating a development branch. It takes the
upstream version as a base and applies all patches from the packaging branch on
top of that. In addition to this it imports the .gbs.conf from the packaging
branch. Before using `gbs devel` start you should have an orphan packaging
branch that contains all local changes as patches, in addition to the other
packaging files.

Example:

::

 $ git branch
 * tizen
   upstream
 $ gbs devel start
 info: Using 'packaging/dbus.spec' from 'working copy'
 info: Switching to branch 'development/tizen/1.0'
 info: Importing additional file(s) from branch 'tizen' into 'development/tizen/1.0'
 info: Trying to apply patches from branch 'tizen' onto '159fdbf680d2dcdd5f80568c3305e93114caddfa'
 info: Patches listed in 'dbus.spec' imported on 'development/tizen/1.0'
 info: Updating local .gbs.conf
 info: Committing local .gbs.conf to git
 $ git branch
 * development/tizen/1.0
   tizen
   upstream

The upstream version is embedded in the development branch name. Thus, when
doing a version bump, one should create a new development branch with `gbs
devel start`.


devel export: export patches to the packaging branch
````````````````````````````````````````````````````

The `export` action is used for managing patches in the packaging branch. It
generates patches (one-per-commit) from the development branch and updates the
spec file accordingly. It doesn't automatically commit the changes though -
the package maintainer needs to verify the changes and commit them manually.

Example:

::

 $ git branch
 * development/tizen/1.1
   upstream
   tizen
 $ gbs devel export
 info: Exporting patches to packaging branch
 info: On branch 'development/tizen/1.1', switching to 'tizen'
 info: Generating patches from git (6450890aa002b0868537ee50cc1aea177fdcc941..development/tizen/1.1)
 # On branch tizen
 # Changes not staged for commit:
 #   (use "git add/rm <file>..." to update what will be committed)
 #   (use "git checkout -- <file>..." to discard changes in working directory)
 #
 #   modified:   packaging/gbp-test.spec
 #
 # Untracked files:
 #   (use "git add <file>..." to include in what will be committed)
 #
 #   packaging/0004-New-commit.patch
 no changes added to commit (use "git add" and/or "git commit -a")


devel switch: switch between development and packaging branches
```````````````````````````````````````````````````````````````

The `switch` action is a simple helper for moving between the packaging and development branches.

Example:

::

 $ git branch
   development/tizen/1.1
 * tizen
   upstream
 $ gbs devel switch
 info: Switching to branch 'development/tizen/1.1'
 $ git branch
 * development/tizen/1.1
   tizen
   upstream
 $ gbs devel switch
 info: Switching to branch 'tizen'
 $ git branch
   development/tizen/1.1
 * tizen
   upstream


devel drop: delete the development branch
`````````````````````````````````````````

The `drop` action is a helper for removing the development branch.  You must be
on the packaging branch to delete the development branch. Note that it only
removes the development branch that the current (upstream) version points to,
e.g. if you have development/tizen/1.0 and development/tizen/2.0 only the
latter will be removed (assuming that the current version is 2.0).

Example:

::

 $ git branch
   development/tizen/1.1
 * tizen
   upstream
 $ gbs devel drop
 info: Dropped branch 'development/tizen/1.1'.
 $ git branch
 * tizen
   upstream



devel convert: convert a package for orphan-packaging model
```````````````````````````````````````````````````````````

The `convert` action is designed for converting a package from the
joint-packaging maintenance model and git-layout to the orphan-packaging model.
It takes the content of the packaging directory, auto-generates patches and
puts these into a new orphan packaging branch. Thus, it basically contains the
output of `gbs export` minus the source code tarball.

With the `--retain-history` option gbs tries to preserve the history of the
local changes. Basically, for each commit in the old (joint-packaging) branch a
corresponding commit in the new orphan packaging branch is created.

Example:

::

 $ git branch
 * tizen
   upstream
 $ gbs devel convert
 info: Converting package to orphan-packaging git layout
 info: Importing packaging files from branch 'tizen' to 'tizen-orphan'
 info: Generating patches from git (04e9d5867181807acae3b89f8ebc1f517c246933..d2ab912babf1ee161004b041ca2bd70f3ff7de0c)
 info: Package successfully converted to orphan-packaging.
 info: You're now on the new 'tizen-orphan' packaging branch (the old packaging branch 'tizen' was left intact).
 info: Please check all files and test building the package!
 info: You can now create the development branch with 'gbs devel start'
 $ git branch
   tizen
 * tizen-orphan
   upstream

The `convert` action only create the orphan packaging branch. Thus, you need to
create the development branch with `gbs devel start`.


an example workflow:
````````````````````

An indicative example workflow:

::

 $ # maintainer: create upstream branch and packaging branch (initial packaging)
 ...
 $ # maintainer: push packaging and upstream branches (and tags) to Git/Gerrit
 $ git push --tags origin upstream master
 $ # maintainer: start development branch
 $ gbs devel start
 $ # maintainer: push development branch to Git/Gerrit
 $ git push origin development/master/1.0
 $ # developer: clone package
 $ gbs clone git://review.tizen.org/example.git
 $ # developer: modify code, test, commit on development branch
 $ ...
 $ gbs build
 $ # developer: push changes for review
 $ git push origin development/master/1.0:refs/for/development/master/1.0
 $ # maintainer: after review, merge changes in Gerrit
 $ # maintainer: generate patches, update packaging/release branch
 $ gbs devel export
 $ git add .
 $ git commit -m"New change"
 $ # maintainer: push packaging branch for review
 $ git push master:refs/for/master
 $ # maintainer: once merged, submit for integration
 $ gbs submit


FAQ
===

This section contains frequently asked questions.

Installation Related Issues
---------------------------

Q: On openSUSE, with correct proxy setting, zypper refresh/install does not work with http://download.tizen.org/tools/latest-release/openSUSE_{version}.
A: This may be caused by the proxy server. Try running the commands below to clean the cache:

::

 # clean the cache from proxy server or remote http server.
 $ wget --no-cache http://download.tizen.org/tools/latest-release/openSUSE_{version}/repodata/repomd.xml
 $ zypper refresh
 $ zypper install gbs

Q: I installed gbs from the official repo, but it is trying to use source code from /usr/local/lib/python*.

A: This may be because you have installed GBS from source code before. Please remove it and re-install.

Q: How do I update GBS and its dependencies?

Refer to `Installing Development Tools`_.

gbs build Related Issues
------------------------
Q: How can I make my local repo have higher priority than the remote repo?

A: It depends on the order of repos, the first repo will have the highest priority. In v0.10 and higher, GBS automatically puts local repos before remote repos.

Q: 'gbs build' report build expansion error: nothing provides X needed by Y.

A: The package you are trying to build is missing a dependency in the repo you specified. You may need to configure/add an additional repository. Try using the release repo, instead of the snapshot repo.

Q: 'gbs build' exits unexpectedly when installing packages to create build root.

A: This may be caused by a remote repo having been changed. You can specify `--clean` while running gbs build, like:

::

 $ gbs build -A <arch> --clean ...

Q: 'gbs build' exits unexpectedly with errors: file XXXX from install of YYYYY conflicts with file from package ZZZZZ.

A: This may be caused by a remote repo having been changed. You can specify `--clean` while running gbs build, like:

::

 $ gbs build -A <arch> --clean ...

Q: 'gbs build' exits with errors: have choice for `XXXX` needed by packagename: package1 package2.

A: This may be caused by a remote repo having two packages provide `XXXX`, and gbs don't know which one to use. In this case, you need download the build config and add one line like this:

::

 Prefer: package1

or

::

 Prefer: package2

To see how to download and customize build config, please refer to the gbs build usage page.

gbs Remote build Related Issues
-------------------------------

Q: I cannot access the remote build server (OBS) during a remote build

A: This requires that you have an username and passwd and that you set them correctly in the configuration file. Also, make sure the build server api and proxy settings are correct for your environment.
Proxy Related Issues

Q: export no_proxy="localhost; 127.0.0.1; .company.com" does not work on Ubuntu

A: Please set no_proxy as ".company.com" directly, and try again.

Q: 'gbs build' returns '500 Can't connect to xxx'

A: The proxy environment variable may have a trailing '/'. Remove the '/' from whatever is setting your environment variables and it should work. This is a known bug in the perl library. This issue is fixed in gbs 0.11.

Q: 'gbs build' returns '500 SSL negotiation failed error'

A: This is caused by the proxy server setting. The proxy you specified cannot forward SSL correctly. Try using another proxy.

gbs chroot Related Issues
-------------------------------

Q: 'gbs chroot -r <build_root>' report error: 'su: user root does not exist'.

A: This is caused by missing `login` package while creating build root. You can fix by updating /etc/passwd and /etc/group to add `root` user:

::

  $ echo "root:x:0:0:root:/root:/bin/bash" >>path/to/buildroot/etc/passwd
  $ echo "root:x:0:" >>path/to/buildroot/etc/group

Others
------

Q: [Fedora] gbs show error: "<user> is not in the sudoers file.  This incident will be reported".

A: Update /etc/sudoers to give <user> sudo permission.

Reporting issues
================

Please report bugs or feature requests at `JIRA <http://en.wikipedia.org/wiki/JIRA>`_: https://bugs.tizen.org.

Detailed steps:

- Click "create issue"
- Select Projects: "Development Tools"
- Select Components: "GBS"

Source Code
===========

The source code is tracked at: https://github.com/01org/gbs


License
=======

::

 Copyright (c) 2012 Intel, Inc.
 This program is free software; you can redistribute it and/or modify it
 under the terms of the GNU General Public License as published by the Free
 Software Foundation; version 2 of the License
 This program is distributed in the hope that it will be useful, but
 WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
 or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License
 for more details.
 You should have received a copy of the GNU General Public License along
 with this program; if not, write to the Free Software Foundation, Inc., 59
 Temple Place - Suite 330, Boston, MA 02111-1307, USA.

.. _`Setting up Development Environment`: https://source.tizen.org/documentation/developer-guide/environment-setup
.. _`Installing Development Tools`: https://source.tizen.org/documentation/developer-guide/installing-development-tools
