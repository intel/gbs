#!/bin/sh
set -x

git_url=`git config remote.origin.url`

prj_name=`basename $git_url`

pkg=$1

pkg_name=`basename $pkg`

echo $prj_name

#curl -i -Fjson='{"parameter": [{"name":"pkg", "value":"'$prj_name'"},{"name":"tag", "value":"'$tag'"}]}' -FSubmit=Build "http://gerrit2.bj.intel.com:8082/job/upload/build" -v

curl -i -Fname=pkg.tar.bz2 -Ffile0=@"$pkg" -Fjson='{"parameter": [{"name": "pkg.tar.bz2", "file": "file0"},{"name":"pkg", "value":"'$pkg_name'"}]}' -FSubmit=Build "http://gerrit2.bj.intel.com:8082/job/uploader/build" -v