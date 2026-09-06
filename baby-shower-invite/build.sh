#!/usr/bin/env bash
# Builds the invitation video from scratch.
#
#   ./build.sh
#
# Requires node with playwright available (NODE_PATH is set below for the
# globally installed copy) and an ffmpeg with libx264 + aac.
set -euo pipefail
cd "$(dirname "$0")"

export NODE_PATH="${NODE_PATH:-/opt/node22/lib/node_modules}"
FFMPEG="${FFMPEG_BIN:-$(command -v ffmpeg || echo /usr/local/lib/python3.11/dist-packages/imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2)}"

mkdir -p out

echo "==> soundtrack"
python3 music.py

echo "==> frames + silent video"
node render.js

echo "==> poster still"
node render.js --poster 14.4

echo "==> muxing audio"
"$FFMPEG" -y -hide_banner -loglevel error \
  -i out/silent.mp4 -i out/music.wav \
  -c:v copy -c:a aac -b:a 192k -ac 2 -ar 44100 \
  -movflags +faststart -shortest \
  out/simran-akshat-baby-shower.mp4

echo "==> done"
ls -la out/simran-akshat-baby-shower.mp4 out/poster.png
