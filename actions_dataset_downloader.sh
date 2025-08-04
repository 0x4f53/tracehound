#!/bin/bash
set -e
wget -O 14796970_repositories.json.gz "https://zenodo.org/records/14796970/files/repositories.json.gz"
gunzip 14796970_repositories.json.gz
jq -r '._id' 14796970_repositories.json > repolist.txt
rm 14796970_repositories.json