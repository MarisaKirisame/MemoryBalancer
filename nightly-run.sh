#!/bin/bash

set -e
set -x

#cleanup
mkdir -p log

rm -f /tmp/membalancer_socket

#sync with the main branch (for custom branches)
#git pull --rebase origin main

mem_balancer_dir=$PWD
cd $mem_balancer_dir

repeats=$1

export PATH="$PWD/../depot_tools:$PATH"
# ./clean_log
# ./clean_out
# echo "** Pulling latest changes in MemoryBalancer and v8 **"
# git submodule init
# git submodule update
# git submodule sync
# echo "** pulling changes in MemoryBalancer"

# echo "** pulling changes in v8 **"
# cd ../v8/src
# git stash
# git checkout STABLE
# git pull origin STABLE
# gclient sync -f --no-history

# echo "** pulling changes in chrome **"
# cd $mem_balancer_dir
# cd "../chromium/src"
# git checkout STABLE
# git pull
#gclient sync -f --no-history
#cd "v8"
#git pull origin STABLE
#cd "../"
#echo "** building chrome **"
#autoninja -C out/Release chrome

# echo "** cloning membalancer-paper **"
# cd $mem_balancer_dir
# cd "../"
# [ ! -d "membalancer-paper" ] && git clone git@github.com:cputah/membalancer-paper.git

cd $mem_balancer_dir
echo "** building v8 **"
make clean
make v8
echo "** building memorybalancer **"
make

# pip3 install pyppeteer
# pip3 install dominate

# yg_semispace_sizes=( 1 2 3 4 5 6 7 8 9 10 )
yg_semispace_sizes=( 4 )
# # acdc_benchmark=( "acdc_1" "acdc_2" "acdc_3" "acdc_4" "acdc_all" )
acdc_benchmark=( "acdc_1" )
for i in $( eval echo {1..$repeats} ) 
do
    echo "** running acdc **"
    for acdc_bm in "${acdc_benchmark[@]}"
    do 
        # echo "ACDC: $i"
        python3 python/eval.py "acdc" $acdc_bm 4
    done
done


# benchmarks=( "pdfjs.js"  "splay.js"  "typescript.js"  "box2d.js"  "earley-boyer.js" )
# echo "** running js **"
# for i in $( eval echo {1..$repeats} ) 
# do 
#     for bm in "${benchmarks[@]}"
#     do 
#         for yg_size in "${yg_semispace_sizes[@]}"
#         do 
#             python3 python/eval.py "jetstream" $bm $yg_size
#             echo "done"
#         done
#     done
# done

# benchmarks=( "all" "pdfjs.js"  "splay.js"  "typescript.js"  "box2d.js"  "earley-boyer.js" )
# echo "** running js **"
# for i in $( eval echo {1..$repeats} ) 
# do 
#     for bm in "${benchmarks[@]}"
#     do 
#         for yg_size in "${yg_semispace_sizes[@]}"
#         do 
#             python3 python/eval.py "jetstream" $bm $yg_size
#             echo "done"
#         done
#     done
# done




# result_dir=`ls "out" | sort -r | head -1`
# python3 python/gen.py --action=open --dir="$result_dir"
# echo "** uploading results **"

# if command -v nightly-results &>/dev/null; then
#     nightly-results url "http://membalancer.uwplse.org/$result_dir"
# fi
