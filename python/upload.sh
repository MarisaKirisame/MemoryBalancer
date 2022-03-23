#!/bin/sh
set -o errexit -o xtrace

# DIR=$1
# TIME=$(date +%s)

#./clean_log

python3 python/gen.py --no-open
last=`ls "out" | sort -r | head -1`
result_dir="out/$last"
#echo "**creating $last directory"
#ssh "uwplse.org" "mkdir /var/www/membalancer/$last"
echo "** uploading files to membalancer.uwplse.org/$last **"
scp -r $result_dir "uwplse.org:/var/www/membalancer"
echo "** uploaded files **"
if command -v nightly-results &>/dev/null; then
    nightly-results url "http://membalancer.uwplse.org/$last"
fi