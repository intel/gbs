#!/bin/bash
# copy this file to /etc/bash_completion.d/
# or copy it to your home directory, rename it as .gbs.bash and add '. .gbs.bash' to ~/.bashrc

__gbscomp ()
{
    local cur_="${3-$cur}"

    case "$cur_" in
        --*=)
            COMPREPLY=()
            ;;
        *)
            local IFS=$'\n'
            COMPREPLY=($(compgen -P "${2-}"\
                -W "$(__gbscomp_1 "${1-}" "${4-}")"\
                -- "$cur_"))
            ;;
    esac
}

__gbscomp_1 ()
{
    local c IFS=$' \t\n'
    for c in $1; do
        c="$c$2"
        case $c in
            --*=*|*.) ;;
            *) c="$c " ;;
        esac
        printf '%s\n' "$c"
    done
}

__gbs_main ()
{
    COMPREPLY=()
    local cur prev cword cfgdir=/usr/share/gbs
    local -a words
    if declare -F _get_comp_words_by_ref &>/dev/null ; then
        _get_comp_words_by_ref cur prev words cword
    else
        cur=$2 prev=$3 words=("${COMP_WORDS[@]}") cword=$COMP_CWORD
    fi

    local i c=1 command
    while [ $c -lt $cword ]; do
        i="${words[c]}"
        case "$i" in
            --help) command="help"; break;;
        -c) let c++ ;;
        -*) ;;
        *) command="$i"; break;;
        esac
        let c++
    done

    __gbs && return
}

__gbs_find_on_cmdline ()
{
    local word subcommand c=1
    while [ $c -lt $cword ]; do
        word="${words[c]}"
        for subcommand in $1; do
            if [ "$subcommand" = "$word" ]; then
                echo "$subcommand"
                return
            fi
        done
        let c++
    done
}

__gbs ()
{
    subcommands="
        build remotebuild submit import export changelog chroot clone pull
    "
    common_opts="--upstream-tag= --upstream-branch= --squash-patches-until=
        --packaging-dir= --no-patch-export"
    lb_opts="
        --arch= --repository= --dist= --buildroot= --clean
        --include-all --extra-packs= --spec= --commit= --cache
        --skip-conf-repos --profile= --noinit --keep-packs
        --clean-repos --define
    "
    rb_opts="
        --base-obsprj= --target-obsprj= --spec= --commit= --include-all
        --status --buildlog --profile= --arch= --repository=
    "
    sr_opts="
        --msg= --target= --commit= --spec= --sign --user-key= --remote= --tag=
    "
    im_opts="
        --merge --upstream-branch= --author-email= --author-name= --no-pristine-tar
        --packaging-dir= --upstream-vcs-tag= --allow-same-version --native
        --filter=  --no-patch-import
    "
    ex_opts="
        --source-rpm --include-all --commit= --spec= --outdir=
    "
    ch_opts="--message= --since= --packaging-dir="
    cr_opts="--root"
    lbex_opts="--no-configure --exclude-from-file= --exclude= --binary-list= --threads=\
        --incremental --overwrite --clean-once --debug $lb_opts"
    cl_opts="--upstream-branch= --all --depth="
    pull_opts="--upstream-branch= --force --depth="

    subcommand="$(__gbs_find_on_cmdline "$subcommands")"
    if [ -z "$subcommand" ]; then
        case  $cur in
            --*)
                __gbscomp "--version --help --verbose --debug"
                ;;
            *)
                __gbscomp "$subcommands"
                ;;
        esac
    else
        case "${subcommand},$cur" in
            build,--*)
                __gbscomp "$lb_opts $lbex_opts $common_opts"
                ;;
            remotebuild,--*)
                __gbscomp "$rb_opts $common_opts"
                ;;
            import,--*)
                __gbscomp "$im_opts"
                ;;
            export,--*)
                __gbscomp "$ex_opts $common_opts"
                ;;
            submit,--*)
                __gbscomp "$sr_opts"
                ;;
            changelog,--*)
                __gbscomp "$ch_opts"
                ;;
            chroot,--*)
                __gbscomp "$cr_opts"
                ;;
            clone,--*)
                __gbscomp "$cl_opts"
                ;;
            pull,--*)
                __gbscomp "$pull_opts"
                ;;
            *)
                COMPREPLY=()
                ;;
            esac
    fi
}
complete -F __gbs_main -o bashdefault -o default -o nospace gbs
