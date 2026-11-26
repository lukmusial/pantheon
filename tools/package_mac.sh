#!/bin/bash
# Package the walk-through as a Mac app and a disk image:
#   tools/package_mac.sh [version]          (default 1.0.0)
# 1. a Shipping build (RunUAT BuildCookRun); world textures are capped at 2048 px for the Mac app by
#    ue/Pantheon/Config/DefaultDeviceProfiles.ini, and the unused NNE plugins are off in the .uproject;
# 2. the program's symbol tables stripped (about 115 MB);
# 3. Contents/Resources/CREDITS.txt: docs/app_credits.txt and the source lists of the statues,
#    paintings and eagle;
# 4. signed again ad hoc, with the app sandbox as its only entitlement (no Developer ID: the first launch
#    needs "Open Anyway", explained in the disk image);
# 5. dist/Pantheon.app (the previous one moved to dist/Pantheon.prev.app) and
#    dist/Pantheon-<version>-mac.dmg with the app, a link to Applications, the credits and how to open it.
set -euo pipefail
VERSION=${1:-1.0.0}
ROOT=$(cd "$(dirname "$0")/.." && pwd)
UAT="/Users/Shared/Epic Games/UE_5.9/Engine/Build/BatchFiles/RunUAT.sh"
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

"$UAT" BuildCookRun -project="$ROOT/ue/Pantheon/Pantheon.uproject" -platform=Mac -clientconfig=Shipping \
    -build -cook -stage -pak -iostore -compressed -nop4 -utf8output -unattended > "$WORK/build.log" 2>&1 \
    || { tail -30 "$WORK/build.log"; exit 1; }
grep -q "BUILD SUCCESSFUL" "$WORK/build.log" || { tail -30 "$WORK/build.log"; exit 1; }

APP="$WORK/Pantheon.app"
ditto "$ROOT/ue/Pantheon/Saved/StagedBuilds/Mac/Pantheon-Mac-Shipping.app" "$APP"
strip -x "$APP/Contents/MacOS/Pantheon-Mac-Shipping" 2>/dev/null
{
    cat "$ROOT/docs/app_credits.txt"
    for f in assets/statues/manifest.md assets/paintings/sources.md assets/eagle/photos/SOURCES.md; do
        printf '\n\n==== %s ====\n\n' "$f"
        cat "$ROOT/$f"
    done
} > "$APP/Contents/Resources/CREDITS.txt"
cat > "$WORK/sandbox.entitlements" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict><key>com.apple.security.app-sandbox</key><true/></dict></plist>
EOF
codesign --force -s - --entitlements "$WORK/sandbox.entitlements" "$APP"
codesign --verify --deep "$APP"

mkdir -p "$ROOT/dist"
if [ -d "$ROOT/dist/Pantheon.app" ]; then
    rm -rf "$ROOT/dist/Pantheon.prev.app"
    mv "$ROOT/dist/Pantheon.app" "$ROOT/dist/Pantheon.prev.app"
fi
ditto "$APP" "$ROOT/dist/Pantheon.app"

DMG="$WORK/dmg"
mkdir -p "$DMG"
ditto "$APP" "$DMG/The Pantheon.app"
ln -s /Applications "$DMG/Applications"
cp "$APP/Contents/Resources/CREDITS.txt" "$DMG/Credits.txt"
cat > "$DMG/How to open.txt" <<'EOF'
The Pantheon, c. 126 AD - for Macs with Apple silicon, macOS 14 or later.

1. Drag "The Pantheon" onto Applications.
2. The app is not notarised by Apple, so the first time macOS will refuse to open it. Open it once,
   choose Done, then go to System Settings > Privacy & Security, scroll down and choose "Open Anyway".
   (Or, in Terminal: xattr -dr com.apple.quarantine "/Applications/The Pantheon.app")

Keys: W A S D and the mouse to walk and look, Shift to walk briskly, F to fly, Tab for the next
viewpoint, G for the ghosts, H for help, Esc to quit.
EOF
hdiutil create -volname "The Pantheon" -srcfolder "$DMG" -fs APFS -format ULMO -ov \
    "$ROOT/dist/Pantheon-$VERSION-mac.dmg" > /dev/null
hdiutil verify "$ROOT/dist/Pantheon-$VERSION-mac.dmg" > /dev/null
du -sh "$ROOT/dist/Pantheon.app" "$ROOT/dist/Pantheon-$VERSION-mac.dmg"
