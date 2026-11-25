#!/bin/bash
# Encode a rendered PNG or EXR sequence into a ProRes master and an H.264 deliverable.
# Usage: ue/encode.sh renders/draft1080 [fps]
set -euo pipefail
DIR="$1"; FPS="${2:-24}"
NAME="$(basename "$DIR")"
EXT=png; ls "$DIR"/flythrough.*.exr >/dev/null 2>&1 && EXT=exr
ffmpeg -y -loglevel error -framerate "$FPS" -i "$DIR/flythrough.%04d.$EXT" \
    -c:v prores_ks -profile:v 3 -pix_fmt yuv422p10le "renders/pantheon_${NAME}_prores.mov"
ffmpeg -y -loglevel error -i "renders/pantheon_${NAME}_prores.mov" \
    -c:v libx264 -preset slow -crf 16 -pix_fmt yuv420p -movflags +faststart "renders/pantheon_${NAME}.mp4"
ffprobe -v error -show_entries format=duration:stream=width,height,nb_frames,r_frame_rate -of compact "renders/pantheon_${NAME}.mp4"
