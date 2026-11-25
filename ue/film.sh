#!/bin/bash
# Record a film from the game itself (not Movie Render Queue): the walk-through's -PantheonFilm mode
# flies the camera keys in ue/films/<name>.txt and saves every frame, then ffmpeg encodes them.
# Usage: ue/film.sh <name> <width> <height> [suffix] [quality 1-3] [fps] [speed]
#   ue/film.sh ghosts 1920 1080 h      -> renders/game_ghosts_h/frame.*.png, renders/pantheon_game_ghosts_h.mp4
#   ue/film.sh ghosts 1080 1920 v      -> the upright cut from the same keys
#   ue/film.sh ghosts 1920 1080 h 3 30 1.3   -> the same film 30 % faster (136 s of keys in 105 s)
# Record into an empty frames folder: a shorter film must not end with the tail of a longer one
# (the script stops if frames are already there).
# Offscreen: no window, so the recording never takes focus (user rule). Game time advances one film
# frame per rendered frame, so the film's speed does not depend on the machine's.
set -euo pipefail
NAME="$1"; W="$2"; H="$3"; SUFFIX="${4:-h}"; QUALITY="${5:-3}"; FPS="${6:-30}"; SPEED="${7:-1}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
UE="/Users/Shared/Epic Games/UE_5.9/Engine/Binaries/Mac/UnrealEditor.app/Contents/MacOS/UnrealEditor"
OUT="$ROOT/renders/game_${NAME}_${SUFFIX}"
mkdir -p "$OUT"
if ls "$OUT" | grep -q '^frame\.'; then
    echo "frames of an earlier recording are in $OUT: move them away first" >&2
    exit 1
fi
"$UE" "$ROOT/ue/Pantheon/Pantheon.uproject" -game -RenderOffscreen -windowed -ResX="$W" -ResY="$H" \
    -PantheonFilm="$ROOT/ue/films/$NAME.txt" -PantheonFilmOut="$OUT" -PantheonFilmFps="$FPS" -PantheonFilmSpeed="$SPEED" \
    -PantheonQuality="$QUALITY" -unattended -nosplash -NoLoadingScreen -log > "$OUT/record.log" 2>&1
echo "frames: $(ls "$OUT" | grep -c '^frame\.')"
MP4="$ROOT/renders/pantheon_game_${NAME}_${SUFFIX}.mp4"
ffmpeg -y -loglevel error -framerate "$FPS" -i "$OUT/frame.%05d.png" \
    -c:v libx264 -preset slow -crf 16 -pix_fmt yuv420p -movflags +faststart "$MP4"
ffprobe -v error -show_entries format=duration:stream=width,height,nb_frames,r_frame_rate -of compact "$MP4"
