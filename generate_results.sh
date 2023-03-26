#!/bin/bash

set -e
set -x

generate_results () {
    all_dir=$( ls -d $PWD/log/*/);
    for dir in $all_dir;
    do 
        echo $dir
        python3 python/gen.py --dir=$dir
    done
}


generate_results