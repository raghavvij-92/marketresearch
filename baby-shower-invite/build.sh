#!/usr/bin/env bash
# Builds the invitation video, in every palette.
#
#   ./build.sh                    all themes
#   ./build.sh blue-pink          just one
#
# Requires node with playwright available (NODE_PATH is set below for the
# globally installed copy) and an ffmpeg with libx264 + aac.
set -euo pipefail
cd "$(dirname "$0")"

export NODE_PATH="${NODE_PATH:-/opt/node22/lib/node_modules}"
FFMPEG="${FFMPEG_BIN:-$(command -v ffmpeg || echo /usr/local/lib/python3.11/dist-packages/imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2)}"

ALL_THEMES=(ivory-sage blue-pink blush-gold powder-mint lilac-butter midnight-gold)
if [ "$#" -gt 0 ]; then THEMES=("$@"); else THEMES=("${ALL_THEMES[@]}"); fi

mkdir -p out

# the soundtrack is the same for every palette, so it is made once
echo "==> soundtrack"
python3 music.py

for THEME in "${THEMES[@]}"; do
  echo
  echo "############ $THEME ############"

  echo "==> frames + silent video"
  node render.js --theme "$THEME"

  echo "==> poster still"
  node render.js --theme "$THEME" --poster 14.4

  echo "==> muxing audio"
  "$FFMPEG" -y -hide_banner -loglevel error \
    -i "out/silent-$THEME.mp4" -i out/music.wav \
    -c:v copy -c:a aac -b:a 192k -ac 2 -ar 44100 \
    -movflags +faststart -shortest \
    "out/simran-akshat-baby-shower-$THEME.mp4"

  echo "==> silent version, for adding your own audio"
  # stripped from the finished file rather than re-encoded, so the picture is
  # bit-identical to the version with music
  "$FFMPEG" -y -hide_banner -loglevel error \
    -i "out/simran-akshat-baby-shower-$THEME.mp4" \
    -map 0:v -c:v copy -an -movflags +faststart \
    "out/simran-akshat-baby-shower-$THEME-no-audio.mp4"

  # a small JPEG of the poster, for the contact sheet in the README
  "$FFMPEG" -y -hide_banner -loglevel error \
    -i "out/poster-$THEME.png" -vf scale=540:-1 -q:v 3 "out/poster-$THEME.jpg"
done

# a single side-by-side of every palette, for choosing between them
if [ "${#THEMES[@]}" -eq "${#ALL_THEMES[@]}" ]; then
  echo
  echo "==> theme comparison sheet"
  "$FFMPEG" -y -hide_banner -loglevel error \
    -i out/poster-ivory-sage.jpg   -i out/poster-blue-pink.jpg \
    -i out/poster-blush-gold.jpg   -i out/poster-powder-mint.jpg \
    -i out/poster-lilac-butter.jpg -i out/poster-midnight-gold.jpg \
    -filter_complex "[0]scale=250:-1[a];[1]scale=250:-1[b];[2]scale=250:-1[c];\
[3]scale=250:-1[d];[4]scale=250:-1[e];[5]scale=250:-1[f];\
[a][b][c][d][e][f]xstack=inputs=6:layout=0_0|w0_0|w0+w1_0|0_h0|w0_h0|w0+w1_h0" \
    -frames:v 1 -update 1 -q:v 3 out/theme-comparison.jpg
fi

echo
echo "==> done"
ls -la out/simran-akshat-baby-shower-*.mp4
