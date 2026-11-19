#!/bin/bash
# publish.sh FILE... -> force-pushes FILES as the only content of orphan branch "media" and prints raw URLs.
set -e
FILES=(); for f in "$@"; do FILES+=("$(readlink -f "$f")"); done
R=/home/claude/media_push; rm -rf $R; mkdir -p $R; cd $R
git init -q; git checkout -q --orphan media
for f in "${FILES[@]}"; do cp "$f" .; done
git add -A; git -c user.name=Claude -c user.email=noreply@anthropic.com commit -qm "media $(date -u +%F)"
git remote add origin https://github.com/adityabakshi613-stack/shorts-media
git push -q -f origin media 2>&1 | grep -v "^remote:" || true
SHA=$(git rev-parse HEAD); for f in "$@"; do echo "https://raw.githubusercontent.com/adityabakshi613-stack/shorts-media/$SHA/$(basename "$f")"; done
