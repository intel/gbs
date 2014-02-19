GBS - Git Build System
======================

Overview
--------
GBS means "git build system" and it's used to building Tizen source packages.

GBS support the following major features:
* gbs build  : build rpm package from git repository locally
* gbs remotebuild : build rpm package from git repository on OBS
* gbs import : import source rpm or specfile to git repository
* gbs changelog   : generate changelog from git commits to changelog file
* gbs submit : maintain the changelogs file, sanity check etc.
* gbs export : export git tree as tar ball, format of tar ball is from spec

Resource
--------
 * REPO: https://download.tizen.org/tools/
 * DOCS: https://source.tizen.org/documentation/reference/git-build-system
 * CODE: https://review.tizen.org/gerrit/#/admin/projects/tools/gbs
         https://github.com/01org/gbs
 * BUGS: https://bugs.tizen.org/jira
 * HELP: general@lists.tizen.org


License
-------
GBS is Open Source and distributed under the GPLv2 License.


Contacts
--------
When you found a bug, you can file this bug in our official bug tracker:
https://bugs.tizen.org/jira
