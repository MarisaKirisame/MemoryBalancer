#!/bin/bash

# #pass root dir which contains both chromium and memorybalancer
# if [ -z $1 ]
# 	then
# 		mem_balancer_dir=$PWD
# 	else
# 		mem_balancer_dir=$1
# fi


#cleanup

mkdir log

rm -f /tmp/membalancer_socket

#syncing with the main branch (for custom branches)
git pull --rebase origin main

mem_balancer_dir=$PWD
set -e
export PATH="$PWD/../depot_tools:$PATH"
#must be in MemoryBalancer
./clean_log
./clean_out
echo "** Pulling latest changes in MemoryBalancer and v8 **"
cd $mem_balancer_dir
git submodule init
git submodule update
git submodule sync
echo "** pulling changes in MemoryBalancer"



echo "** pulling changes in v8 **"
cd ../v8/src
git stash
git checkout 2020-12-24
git pull origin
gclient sync -f --no-history
cd $mem_balancer_dir


echo "** building v8 **"
make v8
echo "** building memorybalancer **"
make

pip3 install pyppeteer
pip3 install dominate

echo "** running eval **"
python3 python/eval.py "jetstream"
sh python/upload.sh




# echo "**Running gclient sync**"
# cd "../chromium/src"
# git checkout master
# git pull
# gclient sync -f --no-history
#
# echo "** building chrome **"
# autoninja -C out/Release chrome


#echo "**Starting eval script**"
#cd $mem_balancer_dir
# python3 eval.py
#sh python/upload.sh log
