#!/bin/bash
USAGE="usage:
    tizenpkg build [target OBS project]
Build package at remote build server, the default target OBS project
is home:<user_id>:branches:Trunk

options:
    -h    print this info
"

die()
{
    echo "Fatal Error:"
    echo -e "${ERR_COLOR}$@${NO_COLOR}"
    echo ""
    echo "$USAGE"
    exit 
}

while :
do
    case $1 in
        -h) echo "$USAGE"
            exit
            ;;
        *) target_obsproject=$1
            break
            ;;
    esac
    shift
done

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

curl -s -i -u$user:$passwd -Fname=package.tar.bz2 -Ffile0=@package.tar.bz2 -Fjson='{"parameter": [{"name": "package.tar.bz2", "file": "file0"},{"name":"pkg", "value":"'$prj_name'"},{"name":"obsproject","value":"'$target_obsproject'"}]}' -FSubmit=Build "$HUDSON_SERVER/job/build/build" 

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

offset=0
while [ Ture ]
do
    result_json=`curl -s -u$user:$passwd "$HUDSON_SERVER/job/build/$build_id/api/json"`
    status=$(echo $result_json|python -mjson.tool |grep "building.*false")
    if [ -n "$status" ]; then
        break
    fi
    
    length=`curl -s -u$user:$passwd "$HUDSON_SERVER/rest/projects/build/$build_id/console/" | cut -d ',' -f2|cut -d ':' -f2`
    curl -s -u$user:$passwd "$HUDSON_SERVER/rest/projects/build/$build_id/console/content" -d 'length'=$length -d 'offset'=$offset -G
    offset=$length
done
echo ""

result=`echo $result_json|python -mjson.tool |grep result|cut -d '"' -f4`

if [  x$result != xSUCCESS ]; then
    die 'Remote Server Exception'
else
    echo ""
fi

rm package.tar.bz2
