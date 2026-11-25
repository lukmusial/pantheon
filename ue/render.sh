#!/bin/bash
# Render the flythrough with a Movie Render Queue preset.
# Usage: ue/render.sh MRQ_Stills | MRQ_Draft1080 | MRQ_Final4K
# Output goes to renders/stills, renders/draft1080 or renders/final4k.
# PANTHEON_SEQ=SEQ_Vertical renders the portrait film (presets MRQ_Vert*).
# PANTHEON_MAP, PANTHEON_SEQ_DIR: another level and the folder of its sequence and presets (F3 tests).
# Offscreen: no window, so the render never takes focus (user rule).
set -euo pipefail
PRESET="${1:-MRQ_Stills}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
UE="/Users/Shared/Epic Games/UE_5.9/Engine/Binaries/Mac/UnrealEditor.app/Contents/MacOS/UnrealEditor"
DIR="${PANTHEON_SEQ_DIR:-/Game/Cinematics}"
"$UE" "$ROOT/ue/Pantheon/Pantheon.uproject" "${PANTHEON_MAP:-/Game/Maps/Pantheon}" -game \
    -LevelSequence="$DIR/${PANTHEON_SEQ:-SEQ_Flythrough}" \
    -MoviePipelineConfig="$DIR/$PRESET" \
    -RenderOffscreen -windowed -resx=1280 -resy=720 -unattended -nosplash -nop4 -NoLoadingScreen -log \
    -stdout -FullStdOutLogOutput "${@:2}"
