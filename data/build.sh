#!/bin/sh

die()
{
    echo "Fatal Error:"
    echo "    " $1
    exit 
}

git branch -a|sed -e '/^[^*]/d' -e 's/* \(.*\)/\1/'|grep "\-release" > /dev/null 2>&1 || die "Please run this command under release branch"

git status|grep "modified">/dev/null 2>&1 &&die "Please save you local changes before this command, eg git commit"


git_url=`git config remote.origin.url`

prj_name=`basename $git_url`


tar jcf package.tar.bz2 `git ls-files`

#json="{\"parameter\":[{\"name\":\"jobParameters\",\"value\":\"\"}]}"
#curl -X POST "http://gerrit2.bj.intel.com:8082/job/submit_testing/buildWithParameters?pkg=curl&rev=$1" -v

curl -i -Fname=package.tar.bz2 -Ffile0=@package.tar.bz2 -Fjson='{"parameter": [{"name": "package.tar.bz2", "file": "file0"},{"name":"pkg", "value":"'$prj_name'"}]}' -FSubmit=Build "http://gerrit2.bj.intel.com:8082/job/build/build" -v

