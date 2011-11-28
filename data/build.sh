#!/bin/bash


die()
{
    echo "Fatal Error:"
    echo "    " $1
    exit 
}

git branch -a|sed -e '/^[^*]/d' -e 's/* \(.*\)/\1/'|grep "release" > /dev/null 2>&1 || die "Please run this command under release branch"

git status|grep "modified">/dev/null 2>&1 &&die "Please save you local changes before this command, eg git commit"


git_url=`git config remote.origin.url`

prj_name=`basename $git_url`


tar jcf package.tar.bz2 `git ls-files`
user=`git config tizen.username`
passwd=`git config tizen.password`
HUDSON_SERVER=`git config tizen.hudson`

if ! [[ $user && $passwd && $HUDSON_SERVER  ]]; then
    echo "-------------------------------------"
    echo "[tizen]"
    echo "        username = USERNAME"
    echo "        password = CLEAR PASSWORD"
    echo "        hudson = HUDSON Server"
    echo "-------------------------------------"
    die "No tizen configuration found, please add the above section to your git config file (~/.gitconfig or .git/config)"
fi

echo "Submiting your changes to build server"

curl -s -i -u$user:$passwd -Fname=package.tar.bz2 -Ffile0=@package.tar.bz2 -Fjson='{"parameter": [{"name": "package.tar.bz2", "file": "file0"},{"name":"pkg", "value":"'$prj_name'"},{"name":"obsproject","value":"'$t'"}]}' -FSubmit=Build "$HUDSON_SERVER/job/build/build" 

sleep 0.5
last_id=`curl -s -u$user:$passwd "$HUDSON_SERVER/job/build/lastBuild/buildNumber"`

# In case the last commit is not made by the user, supposed the last job triggered by '$user' is the one. 
while [ ture ]
do
    result_json=`curl -s -u$user:$passwd "$HUDSON_SERVER/job/build/$last_id/api/json"`
    username=`echo $result_json|python -mjson.tool |grep "userName" |cut -d'"' -f4`
    if [ x$username != x$user ]; then
        last_id=`expr $last_id - 1`
    else
        build_id=$last_id
        break
    fi
done

    # Waiting until the job finished
while [ Ture ]
do
    result_json=`curl -s -u$user:$passwd "$HUDSON_SERVER/job/build/$build_id/api/json"`
    status=$(echo $result_json|python -mjson.tool |grep "building.*false")
    if [ -n "$status" ]; then
        break
    fi
    
    length=`curl -s -u$user:$passwd "$HUDSON_SERVER/rest/projects/build/$build_id/console/" | cut -d ',' -f2|cut -d ':' -f2`
    curl -s -u$user:$passwd "$HUDSON_SERVER/rest/projects/build/$build_id/console/content" -d 'length'=$length -d 'offset'=$offset -G
    string=`curl -s -u$user:$passwd "$HUDSON_SERVER/rest/projects/build/$build_id/console/content" -d 'length'=$length -d 'offset'=$offset -G`
    offset=$length
done
echo ""

result=`echo $result_json|python -mjson.tool |grep result|cut -d '"' -f4`

if [  x$result != xSUCCESS ]; then
    echo -e "${ERR_COLOR}=====LOG FROM REMOTE SERVER=============${NO_COLOR}"
    curl -s -u$user:$passwd "$HUDSON_SERVER/job/build/$build_id/consoleText"
    echo -e "${ERR_COLOR}========================================${NO_COLOR}"
    die 'Remote Server Exception'
else
    curl -s -u$user:$passwd "$HUDSON_SERVER/job/build/$build_id/consoleText"
fi

rm package.tar.bz2
