#!/bin/bash

if [ -z $1 ]
	then
		dest=$pwd
	else
		dest=$1
fi

script_dir=$(echo $(dirname $0))

if [ $script_dir = "." ]
	then
		script_dir=$PWD
fi

echo "Setting up ssh-agent..."
eval $(ssh-agent)
ssh-add ~/.ssh/id_rsa


echo "**********Installing libncurses5-dev*********"

sudo apt-get install  libtinfo5 libncurses5 libtinfo-dev libncurses5-dev=6.0+20161126-1+deb9u2


echo "Cloning depot_tools..."
#directory where the build scripts are present
cd $dest
git clone https://chromium.googlesource.com/chromium/tools/depot_tools.git
export PATH="$dest/depot_tools:$PATH"
# echo "TEST: $PATH"

# echo "TEST: dir of file: $script_dir"

echo "Cloning v8..."
cd $dest
sh "$script_dir/fetch.sh" v8
cd v8/src
# sudo apt-get install lsb-releas
# pip install urllib2

echo "	Installing build dependencies..."
./build/install-build-deps.sh
#creating config
echo "	Creating config"
tools/dev/v8gen.py x64.release.sample
echo "	Disabling pointer compression"
echo "v8_enable_pointer_compression = false" >>  out.gn/x64.release.sample
#building
echo "	building v8 v8_monolith"
ninja -C out.gn/x64.release.sample v8_monolith


 # echo "Cloning mem-balancer.."
# cd $dest
# git --recursive clone git@github.com:MarisaKirisame/MemoryBalancer.git
#
#
# echo "Cloning webkit"
# cd $dest
# git clone git@github.com:WebKit/WebKit.git
