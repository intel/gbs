#!/bin/bash
USAGE="usage:
    tizenpkg build [target OBS project]

Build package at remote build server, the default target OBS project
is home:<user_id>:branches:Trunk

options:
    -v/--verbose   verbose mode
    -h/--help      print this info
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
        -v|--verbose) verbose=true
            ;;
        -h|--help) echo "$USAGE"
            exit
            ;;
        *) target_obsproject=$1
            break
            ;;
    esac
    shift
done

git branch -a|sed -e '/^[^*]/d' -e 's/* \(.*\)/\1/'|grep "release" > /dev/null 2>&1 || die "Please run this command under release branch"

git status|grep "modified">/dev/null 2>&1 &&echo "Warning: You local changes doesn't commit yet."

# Get project name from git url
git_url=`git config remote.origin.url`
echo $git_url|grep ^ssh > /dev/null
if [ $? == 0 ]; then
    prj_name=`basename $git_url`
else
    prj_name=$(echo $git_url|cut -d ':' -f2)
fi

# tar the local changes
tar jcf package.tar.bz2 `git ls-files`

# get user name/passwd from tizenpkg.conf
user=$(tizenpkg cfg user)
passwd=$(tizenpkg cfg passwd)
HUDSON_SERVER=$(tizenpkg cfg src_server)
passwdx=$(tizenpkg cfg passwdx)
echo "Submiting your changes to build server"

ret_string=$(curl -i -s -u$user:$passwd -Fname=package.tar.bz2 -Ffile0=@package.tar.bz2 -Fjson='{"parameter": [{"name": "package.tar.bz2", "file": "file0"},{"name":"pkg", "value":"'$prj_name'"},{"name":"parameters","value":"obsproject='$target_obsproject';passwdx='$passwdx'"}]}' -FSubmit=Build "$HUDSON_SERVER/job/build/build")

echo $ret_string|grep '302' > /dev/null

if [ $? != 0 ]; then
    echo $ret_string
    die "Server Error, please check your tizenpkg configuration"
fi

sleep 2

last_id=`curl -s -u$user:$passwd "$HUDSON_SERVER/job/build/lastBuild/buildNumber"`
result_json=`curl -s -u$user:$passwd "$HUDSON_SERVER/job/build/$last_id/api/json"`
last_prj=`echo $result_json|python -mjson.tool |grep "pkg" -A1|tail -1|cut -d'"' -f4`
last_user=`echo $result_json|python -mjson.tool |grep "userName" |cut -d'"' -f4`
    # In case the last commit is not made by the user, supposed the last job triggered by '$user' is the one.
if [ "$last_prj" != "$prj_name" -o "$last_user" != "$user" ]; then
    echo "Your request has been put in queue waiting to process"
    while [ true ]
    do
        ret_id=$(curl -s -u$user:$passwd "$HUDSON_SERVER/job/build/lastBuild/buildNumber") 
        if [ "$last_id" != "$ret_id" ]; then
            result_json=`curl -s -u$user:$passwd "$HUDSON_SERVER/job/build/$ret_id/api/json"`
            last_prj=`echo $result_json|python -mjson.tool |grep "pkg" -A1|tail -1|cut -d'"' -f4`
            last_user=`echo $result_json|python -mjson.tool |grep "userName" |cut -d'"' -f4`
            if [ "$last_prj" == "$prj_name" -o "$last_user" != "$user" ]; then
                last_id=$ret_id
                echo ''
                break
            fi
            last_id=$ret_id
        else
            echo -n .
            sleep 1
        fi
    done
fi

build_id=$last_id

offset=0
while :
do
    result_json=`curl -s -u$user:$passwd "$HUDSON_SERVER/job/build/$build_id/api/json"`
    status=$(echo $result_json|python -mjson.tool |grep "building.*false")
    if [ -n "$status" ]; then
        break
    fi

    if [ -n "$verbose" ]; then
        length=`curl -s -u$user:$passwd "$HUDSON_SERVER/rest/projects/build/$build_id/console/" | cut -d ',' -f2|cut -d ':' -f2`
        curl -s -u$user:$passwd "$HUDSON_SERVER/rest/projects/build/$build_id/console/content" -d 'length'=$length -d 'offset'=$offset -G
        offset=$length
    else
        echo -n '.'
    fi
    sleep 1

done
echo ""

result=`echo $result_json|python -mjson.tool |grep result|cut -d '"' -f4`

if [  x$result != xSUCCESS ]; then
    curl -u$user:$passwd "$HUDSON_SERVER/job/build/$build_id/consoleText" -G
    die 'Remote Server Exception'
else
    echo "Your local changes has been submitted to build server."
fi

rm package.tar.bz2
