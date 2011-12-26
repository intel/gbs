#!/bin/bash
USAGE="usage:
    gbs import [-h] [-p project] <tarball>

Import/upload new tarballs for current pkg

Options:
    -p/--project    specify the target project
    -h/--help      print this info
"

INFO_COLOR='\e[0;32m' # green
WARN_COLOR='\e[0;33m' # yellow
ERR_COLOR='\e[0;31m' # red
ASK_COLOR='\e[0;34m' # blue
NO_COLOR='\e[0m'

die()
{
    echo "Fatal Error:"
    echo -e "${ERR_COLOR}$@${NO_COLOR}"
    echo ""
    echo "$USAGE"
    exit 
}

info_msg()
{
    echo -e "${INFO_COLOR}$@ ${NO_COLOR}"
}

while :
do
    case $1 in
        -v|-d|--verbose) verbose=true
            ;;
        -p|--project) target_project=$2
            shift
            ;;
        -h|--help) echo "$USAGE"
            exit
            ;;
        [a-zA-Z0-9\.]*) source_tarball=$1
            ;;
        *)
            break
            ;;
    esac
    shift
done

[ $# == 0 ] || die "Invalid parameters."

# get user name/passwd from gbs.conf
user=$(gbs cfg user)
passwd=$(gbs cfg passwd)
HUDSON_SERVER=$(gbs cfg src_server)
passwdx=$(gbs cfg passwdx)

source_tarball_name=$(basename $source_tarball)

if [ -z "$target_project" ]; then
# Get project name from git url
    git_url=`git config remote.origin.url`
    echo $git_url|grep ^ssh > /dev/null
    if [ $? == 0 ]; then
        target_project=`basename $git_url`
    else
        target_project=$(echo $git_url|cut -d ':' -f2)
    fi
fi

if [ -z "$target_project" ]; then
    die "No target project found, please specify it by use -t parameter."
fi

# Only compressed data file support
file $source_tarball|grep "compressed data" > /dev/null || die "Invalid file type: $(file $source_tarball|cut -d':' -f2) \n    Only compressed data file supported."

info_msg "Computing the MD5 checksums of $source_tarball..."
md5checksum=$(md5sum $source_tarball|awk '{print $1}')
echo "Result: " $md5checksum

info_msg "Checking your tar ball importing permission... "
ret_string=$(curl -L -k -s -i -u$user:$passwd -Fjson='{"parameter": [{"name":"pkg", "value":"'$source_tarball_name'"},{"name":"parameters","value":"target_project='$target_project';md5checksum='$md5checksum'"}]}' -FSubmit=Build "$HUDSON_SERVER/job/authen/build")

echo $ret_string|grep '302' > /dev/null

if [ $? != 0 ]; then
    echo $ret_string
    die "Server Error, please check your gbs configuration"
fi

last_id=`curl -L -k -s -u$user:$passwd "$HUDSON_SERVER/job/authen/lastBuild/buildNumber"`
result_json=`curl -L -k -s -u$user:$passwd "$HUDSON_SERVER/job/authen/$last_id/api/json"`
last_prj=`echo $result_json|python -mjson.tool |grep "pkg" -A1|tail -1|cut -d'"' -f4`
last_user=`echo $result_json|python -mjson.tool |grep "userName" |cut -d'"' -f4`
    # In case the last commit is not made by the user, supposed the last job triggered by '$user' is the one.
if [ "$last_prj" != "$source_tarball_name" -o "$last_user" != "$user" ]; then
    while [ true ]
    do
        ret_id=$(curl -L -k -s -u$user:$passwd "$HUDSON_SERVER/job/authen/lastBuild/buildNumber") 
        if [ "$last_id" != "$ret_id" ]; then
            result_json=`curl -L -k -s -u$user:$passwd "$HUDSON_SERVER/job/authen/$ret_id/api/json"`
            last_prj=`echo $result_json|python -mjson.tool |grep "pkg" -A1|tail -1|cut -d'"' -f4`
            last_user=`echo $result_json|python -mjson.tool |grep "userName" |cut -d'"' -f4`
            if [ "$last_prj" == "$source_tarball_name" -o "$last_user" != "$user" ]; then
                last_id=$ret_id
                echo ''
                break
            fi
            last_id=$ret_id
        else
            echo -n .
        fi
    done
fi

build_id=$last_id
    # Waiting until the job finished
while [ true ]
do
    result_json=`curl -L -k -s -u$user:$passwd "$HUDSON_SERVER/job/authen/$build_id/api/json"`
    status=$(echo $result_json|python -mjson.tool |grep "building.*false")
    if [ -n "$status" ]; then
        build_result=$(echo $result_json|python -mjson.tool |grep "result"|cut -d'"' -f4)
        break
    fi
    echo -n '.'
    sleep 0.5
done

if [  x$build_result != xSUCCESS ]; then
    echo -e "${ERR_COLOR}==== LOG FROM REMOTE SERVER ============${NO_COLOR}"
    curl -L -k -s -u$user:$passwd "$HUDSON_SERVER/job/authen/$build_id/consoleText"
    echo -e "${ERR_COLOR}========================================${NO_COLOR}"
    die 'Remote Server Exception'
else
    srctar_md5sum=$(curl -L -k -s -u$user:$passwd "$HUDSON_SERVER/job/authen/$build_id/consoleText" | sed -n 's/.*#!#\(.*\)#!#.*/\1/p')
    if [ -n "$srctar_md5sum" ]; then
        info_msg "The file already exist"
        echo "    " "$srctar_md5sum"
        echo ""
        exit 0
    fi
fi


info_msg "Authentication passed."

info_msg "Uploading $source_tarball to the source server...."
ret_string=$(curl -L -k -i -# -u$user:$passwd -Fname=source_tarball -Ffile0=@$source_tarball -Fjson='{"parameter": [{"name": "source_tarball", "file": "file0"},{"name":"pkg", "value":"'$source_tarball_name'"},{"name":"parameters","value":"target_project='$target_project'"}]}' -FSubmit=Build "$HUDSON_SERVER/job/import/build")

echo $ret_string|grep '302' > /dev/null

if [ $? != 0 ]; then
    echo $ret_string
    die "Internal server Error, please report this bug to tizen-distro@linux.intel.com"
fi

sleep 1

last_id=`curl -L -k -s -u$user:$passwd "$HUDSON_SERVER/job/import/lastBuild/buildNumber"`
result_json=`curl -L -k -s -u$user:$passwd "$HUDSON_SERVER/job/import/$last_id/api/json"`
last_prj=`echo $result_json|python -mjson.tool |grep "pkg" -A1|tail -1|cut -d'"' -f4`
last_user=`echo $result_json|python -mjson.tool |grep "userName" |cut -d'"' -f4`
    # In case the last commit is not made by the user, supposed the last job triggered by '$user' is the one.
if [ "$last_prj" != "$source_tarball_name" -o "$last_user" != "$user" ]; then
    echo "Your request has been put in queue waiting to process"
    while [ true ]
    do
        ret_id=$(curl -L -k -s -u$user:$passwd "$HUDSON_SERVER/job/import/lastBuild/buildNumber") 
        if [ "$last_id" != "$ret_id" ]; then
            result_json=`curl -L -k -s -u$user:$passwd "$HUDSON_SERVER/job/import/$ret_id/api/json"`
            last_prj=`echo $result_json|python -mjson.tool |grep "pkg" -A1|tail -1|cut -d'"' -f4`
            last_user=`echo $result_json|python -mjson.tool |grep "userName" |cut -d'"' -f4`
            if [ "$last_prj" == "$source_tarball_name" -o "$last_user" != "$user" ]; then
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

echo 'Serve is processing your request, waiting for the result ...'
    # Waiting until the job finished
while [ true ]
do
    result_json=`curl -L -k -s -u$user:$passwd "$HUDSON_SERVER/job/import/$build_id/api/json"`
    status=$(echo $result_json|python -mjson.tool |grep "building.*false")
    if [ -n "$status" ]; then
        break
    fi
    echo -n '.'
    sleep 1
done
echo ""
    
# Execuation result
result_json=`curl -L -k -s -u$user:$passwd "$HUDSON_SERVER/job/import/$build_id/api/json"`
result=`echo $result_json|python -mjson.tool |grep result|cut -d '"' -f4`

if [  x$result != xSUCCESS ]; then
    echo -e "${ERR_COLOR}==== LOG FROM REMOTE SERVER ============${NO_COLOR}"
    curl -L -k -s -u$user:$passwd "$HUDSON_SERVER/job/import/$build_id/consoleText"
    echo -e "${ERR_COLOR}========================================${NO_COLOR}"
    die 'Remote Server Exception'
else
    srctar_md5sum=$(curl -L -k -s -u$user:$passwd "$HUDSON_SERVER/job/import/$build_id/consoleText" | sed -n 's/.*#!#\(.*\)#!#.*/\1/p')
    info_msg "md5sum output:"
    echo "    "  "$srctar_md5sum"
    echo ""
fi

