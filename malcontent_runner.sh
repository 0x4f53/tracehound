#!/bin/bash
# install docker first!!!!
set -e

docker pull cgr.dev/chainguard/malcontent:latest

INPUT_DIR="cache/"
OUTPUT_DIR="output/"

find "$INPUT_DIR" -type f | while read -r file; do
    rel_path="${file#$INPUT_DIR/}"
    out_path="$OUTPUT_DIR/${rel_path}.json"
    if [ -f "$out_path" ]; then
        echo "Skipping $file, output already exists."
        continue
    fi
    mkdir -p "$(dirname "$out_path")"
    docker run --rm -v "$(pwd)":/src cgr.dev/chainguard/malcontent \
        --format=json --min-risk=high analyze "/src/$file" > "$out_path"
done

# grep -rl "high" output/