#!/bin/bash

USAGE="Usage:
    gbs packaging [-s] [git-tag/commit-id] [-t release-tag] [-f specfile]

Packaging master branch, convert the files to release branch
from the given tag or commit-id, by default using HEAD.

Options:
    -s    silence remove patch without question
    -t    specify the tag for the major release, source package
          will be generated at this tag. By default it's the most
          recent tag found near HEAD or the given base tag/commit-id.
    -f    specify the spec file in case of multiple ones exist in one project
    -h    print this help info
"

INFO_COLOR='\e[0;32m' # green
WARN_COLOR='\e[0;33m' # yellow
ERR_COLOR='\e[0;31m' # red
ASK_COLOR='\e[0;34m' # blue
NO_COLOR='\e[0m'


die()
{
    echo -e "${ERR_COLOR}Fatal Error:"
    echo -e "    " "$@${NO_COLOR}"
    echo ""
    exit 
}

info_msg()
{
    echo -e "${INFO_COLOR}$@ ${NO_COLOR}"
}

# Run under release branch, update spec file version, input: new_version, spec
# Global env: version
update_version()
{
    
    # Validation check
    grep "^Version:" $spec > /dev/null ||die 'Invalid spec file: no "Version" directive defined'

    cp $spec $spec.origin
    
    sed -i "s/\(^Version:[\t ]*\).*/\1$version/g" $spec

}

format_patches()
{
    tag=$1
    git_obj=$2

    git checkout $git_obj 
    patch_list=$(git format-patch $tag -o tizen-patches/)

    if [ -n "$patch_list" ]; then
        info_msg "Patch list:"
        for patch in $patch_list
        do
            echo "    " $(basename $patch)
        done
        echo ""
    fi
}

# Run under release branch, update patch list in spec file: input: git_obj
# Global env: spec, patch_list, silence_remove
#
# Work process:
#      1. distinguish the patch(es) need kept 
#      2. remove the other(dropped)
#      3. insert the new added
#
update_patches()
{
    if [ -z "$spec" ]; then
        die "no spec file found, abort!"
    fi

    # Find the patches to be kept
    for patch in $patch_list
    do
        line=$(grep "Patch[0-9]\+:.*$(basename ${patch%.patch}|sed 's/[0-9]*-//')" $spec)
        if [ -n "$line" ]; then
            sed -i "s/$line/#PATCHKEPT#$line/" $spec
        else
            newadd_patch="$newadd_patch $patch"
        fi
    done

    # Remove old patches
    toberemove_patch=$(grep "^Patch[0-9]\+:" $spec |awk '{print $2}')

    if [ -n "$toberemove_patch" ]; then
        echo "----------------------------------------"
        info_msg "The following patches were removed:"
        for patch in $toberemove_patch
        do
            if [ -z "$silence_remove" ];then
                echo -n -e "${ASK_COLOR}Remove patch: $patch? ${NO_COLOR}(Y/n)"
                read yn
            else
                info_msg "Remove patch: $patch ?(Y/n)"y
                yn=$silence_remove
            fi

            case $yn in
                [Nn]* )
                    info_msg "Patch $patch kept."
                    ;;
                * )
                    sed -i "/^Patch[0-9]*:.*$patch/ d" $spec
                    git rm $patch
                    info_msg "Patch $patch removed."
                    ;;
            esac
        done
        echo "----------------------------------------"
    fi

    # Recover the kept patches
    sed -i "s/^#PATCHKEPT#//g" $spec

    # Remove the install part
    install_list=$(grep "^%patch[0-9]\+" $spec|cut -d ' ' -f1|sed 's/%p/P/')
    for install in $install_list
    do
        grep "$install:" $spec > /dev/null
        if [  "$?" != "0"  ]; then
            sed -i "/$(grep -i "$install\ -p" $spec)/ d" $spec
        fi
    done

    # Trying to insert the new add patch
    # no new patch 
    if [  -n "$newadd_patch" ]; then
        # Find the insert line num
        line_num=$(grep "^Patch[0-9]\+" $spec -n|tail -1|cut -d':' -f1)
        # No patch. Insert after Source
        if [ -z "$line_num" ]; then
            line_num=$(grep "^Source[0-9]\+" $spec -n|tail -1|cut -d':' -f1)
            num=0
        else
            # The first patch number
            num=$(grep "^Patch[0-9]\+" $spec |sed -n 's/Patch\([0-9]*\):.*/\1/' |sort -n |tail -1)
            num=$(expr $num + 1)
        fi

        [ -n "$line_num" ] || die "Can not insert the patch"
        line_num=$(expr $line_num + 1)
        sed -i "$line_num i "##PATCH_ADD##"" $spec

        for patch in $newadd_patch
        do
            # Patch defination string
            PATCH="$PATCH""Patch$num:    $(basename $patch)\n"
            # Patch installation string
            INSTALL="$INSTALL""%patch$num -p1\n"
            num=`expr $num + 1`
        done

        # Insert the new add patch
        sed -i "s/##PATCH_ADD##/$PATCH/" $spec

        # Locate the line num of the patches installation command
        line_num=$(grep -n "^%patch[0-9]\+"  $spec |tail -1|cut -d':' -f1)
        # No found. trying to insert before %build
        if [ -z "$line_num" ]; then
            line_num=$(grep -n "%build" $spec |tail -1|cut -d':' -f1)
        else
            line_num=$(expr $line_num + 1)
        fi

        [ -n "$line_num" ] || die "Can not update %patch commands of spec file, please do it manually."

        sed -i "$line_num i "##PATCH_INSTALL##"" $spec

        sed -i "s/##PATCH_INSTALL##/$INSTALL/" $spec
        echo "----------------------------------------"
        info_msg "The following patches were added:"
        for patch in $newadd_patch
        do
            echo "    " $(basename $patch)
            mv $patch .
            git add $(basename $patch)
        done
        echo "----------------------------------------"
    fi # end of insert new add patch section

}

# Get the source tarball md5sum from remote source server, input: tag
# Golbal evn: srctar_md5sum
get_srctar_md5sum()
{
    version=$1
    project=$2
    commitid=$3
    info_msg "Getting md5sum value for package $project at ref $tag, from server ..."
    string=$(curl -L -k -s -i -u$user:$passwd -Fjson='{"parameter": [{"name": "version", "value": "'$version'"},{"name":"project", "value":"'$project'"},{"name":"parameters","value":"commitid='$commitid'"}]}' -FSubmit=Build "$HUDSON_SERVER/job/packaging/build")
    sleep 2

    echo $string|grep '302' > /dev/null
    if [ $? != 0 ]; then
        echo $string
        die "Server Error, please check your gbs configuration."
    fi
    
    last_id=`curl -L -k -s -u$user:$passwd "$HUDSON_SERVER/job/packaging/lastBuild/buildNumber"`
    result_json=`curl -L -k -s -u$user:$passwd "$HUDSON_SERVER/job/packaging/$last_id/api/json"`
    last_prj=`echo $result_json|python -mjson.tool |grep "project" -A1|tail -1|cut -d'"' -f4`
    last_user=`echo $result_json|python -mjson.tool |grep "userName" |cut -d'"' -f4`
    # In case the last commit is not made by the user, supposed the last job triggered by '$user' is the one.
    if [ "$last_prj" != "$project" -o "$last_user" != "$user" ]; then
        echo "Your request has been put in waiting queue of server, waiting to active ..."
        while [ true ]
        do
            ret_id=$(curl -L -k -s -u$user:$passwd "$HUDSON_SERVER/job/packaging/lastBuild/buildNumber") 
            if [ "$last_id" != "$ret_id" ]; then
                result_json=`curl -L -k -s -u$user:$passwd "$HUDSON_SERVER/job/packaging/$ret_id/api/json"`
                last_prj=`echo $result_json|python -mjson.tool |grep "project" -A1|tail -1|cut -d'"' -f4`
                last_user=`echo $result_json|python -mjson.tool |grep "userName" |cut -d'"' -f4`
                if [ "$last_prj" == "$project" -o "$last_user" != "$user" ]; then
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
        result_json=`curl -L -k -s -u$user:$passwd "$HUDSON_SERVER/job/packaging/$build_id/api/json"`
        status=$(echo $result_json|python -mjson.tool |grep "building.*false")
        if [ -n "$status" ]; then
            break
        fi
        echo -n '.'
        sleep 1
    done
    echo ""
    # Execuation result
    result_json=`curl -L -k -s -u$user:$passwd "$HUDSON_SERVER/job/packaging/$build_id/api/json"`
    result=`echo $result_json|python -mjson.tool |grep result|cut -d '"' -f4`
    
    if [  x$result != xSUCCESS ]; then
        echo -e "${ERR_COLOR}==== LOG FROM REMOTE SERVER ============${NO_COLOR}"
        curl -L -k -s -u$user:$passwd "$HUDSON_SERVER/job/packaging/$build_id/consoleText"
        echo -e "${ERR_COLOR}========================================${NO_COLOR}"
        die 'Remote Server Exception'
    else

        srctar_md5sum=$(curl -L -k -s -u$user:$passwd "$HUDSON_SERVER/job/packaging/$build_id/consoleText" | sed -n 's/.*#!#\(.*\)#!#.*/\1/p')
        info_msg "md5sum output:"
        echo "    "  "$srctar_md5sum"
        echo ""
    fi
}

update_sources()
{
    srctar_md5sum=$@
    cp sources sources.origin
    sed -i "/[0-9a-f]*\ *$project-.*/d" sources
    echo "$1" >> sources
}

while :
do
    case $1 in
        -s) silence_remove="Y";;
        -f) spec="$2"
            shift
            ;;
        -t) tag="$2"
            shift
            ;;
        -h) echo "$USAGE"
            exit
            ;;
        [0-9a-zA-Z]*)
            git_obj=$1
            ;;
        *) break ;;

    esac
    shift
done

if [ -z "$git_obj" ]; then
    git_obj=$(git log --format="%h" -n 1)

fi


#git branch -a|sed -e '/^[^*]/d' -e 's/* \(.*\)/\1/'|grep "master" > /dev/null 2>&1 || die "Please run this command under master branch"

git rev-parse $git_obj > /dev/null 2>&1|| die "Invalid git object $git_obj"
git describe $git_obj --tags >/dev/null || die "No tags found"

if [ -z "$tag" ];then
    tag=$(git describe $git_obj --abbrev=0 --tags)
fi

commitid=$(git rev-list -1 $tag)
version=${tag#v}

user=$(gbs cfg user)
passwd=$(gbs cfg passwd)
HUDSON_SERVER=$(gbs cfg src_server)

git_url=`git config remote.origin.url`
echo $git_url|grep ^ssh  > /dev/null
if [ $? == 0 ]; then
    project=`basename $git_url`
else
    project=$(echo $git_url|cut -d ':' -f2)
fi

info_msg "Packaging for major release ${tag}"
srctar_md5sum=""
get_srctar_md5sum $version $project $commitid

info_msg "Generating patches from $tag to $git_obj ..."
#info_msg " stored under tizen-patches dir"
format_patches $tag $git_obj

info_msg "Switch to release branch"
git checkout release ||die "No release branch found."

# Ask user specify one spec file if found more than one
if [ -z "$spec" -a $(ls *.spec|wc -l) -gt '1' ]; then
    echo -e "${ASK_COLOR}Found multiple spec files, please select one${NO_COLOR}"
    while :
    do
        ls *.spec|grep spec -n
        read -p "which?" num
        case $num in
            [0-9])
                if [ $num -gt $(ls *.spec|wc -l) ]; then
                    continue
                fi
                spec=$(ls *.spec|grep spec -n|sed -n "/$num/ p"|cut -d ":" -f2 )
                break
                ;;
            *)
                echo "${ASK_COLOR}Please select one using number${NO_COLOR}"
                ;;
        esac
    done
fi

# Get spec file if not specified
if [ -z "$spec" ]; then
    spec=$(ls *.spec)
fi

info_msg 'Updating the "sources" file ...'
update_sources "$srctar_md5sum"

info_msg "Updating version info in spec file ..."
update_version

info_msg "Updating patches in spec file ..."
update_patches

# cleanup
rm tizen-patches -r

info_msg "You're in release branch now."
info_msg "All the changes in release branch are done automatically, please confirm them and do commit."
