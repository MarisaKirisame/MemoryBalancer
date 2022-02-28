#!/bin/bash

#pass root dir which contains both chromium and memorybalancer
if [ -z $1 ]
	then
		root_dir=$PWD
	else
		root_dir=$1
fi

# set -e
# echo "**Setting up ssh-agent**"
# eval $(ssh-agent)
# ssh-add ~/.ssh/id_rsa
#
# echo "**Pulling latest changes in MemoryBalancer**"
# cd "$root_dir/MemoryBalancer"
# git pull origin main
# make
#
# echo "**Running gclient sync**"
# cd "$root_dir/chromium"
# gclient sync --no-history
# autoninja -C out/Release chrome

echo "**Starting eval script**"
cd "$root_dir/MemoryBalancer"
python3 eval.py
