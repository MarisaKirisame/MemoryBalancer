#!/bin/bash

set -e
set -x

generate_results () {
    all_dir=$( ls -d $PWD/log/*/);
    for dir in $all_dir;
    do 
        echo "Processing $dir"
        python3 python/gen.py --dir=$dir
        echo "Done"
    done
}


generate_results