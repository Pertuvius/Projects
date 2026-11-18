#!/bin/sh
# Prepare patched source and game data before the Android NDK build.
set -eu
APP_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
SOURCE_DIR=${FREEDROID_SOURCE_DIR:-"$APP_DIR/freedroidRPG-1.0"}
PATCHER="$APP_DIR/tools/apply_port_patches.py"

if [ ! -d "$SOURCE_DIR/src" ] || [ ! -f "$SOURCE_DIR/configure" ] || [ ! -d "$SOURCE_DIR/data" ] || [ ! -d "$SOURCE_DIR/lua_modules" ]; then
  echo "FreedroidRPG source not found at $SOURCE_DIR" >&2
  echo "Extract the official 1.0 source archive to that exact directory." >&2
  exit 2
fi

echo "Pre-build source root: $SOURCE_DIR"
for required in configure src/init.c src/graphics.c src/image.c; do
  if [ -e "$SOURCE_DIR/$required" ]; then
    echo "Present before patching: $required"
  else
    echo "Missing before patching: $required" >&2
  fi
done
stat -c 'Shell sees %n inode=%i type=%F' "$SOURCE_DIR/src/init.c"
python3 -c 'import os,sys; p=sys.argv[1]; print("Python sees", repr(p), "exists=", os.path.exists(p), "realpath=", os.path.realpath(p))' "$SOURCE_DIR/src/init.c"
python3 "$PATCHER" --source "$SOURCE_DIR"
PROJECT_ROOT=$(CDPATH= cd -- "$APP_DIR/../../.." && pwd -P)
APP_MAKEFILE="$PROJECT_ROOT/jni/Application.mk"
if [ ! -f "$APP_MAKEFILE" ]; then
  echo "Runtime Application.mk not found: $APP_MAKEFILE" >&2
  exit 4
fi
if ! grep -q '^APP_ALLOW_MISSING_DEPS := true$' "$APP_MAKEFILE"; then
  cat >> "$APP_MAKEFILE" <<'APP_MK_EOF'
# This app omits audio; ignore unresolved dependencies of unused shared-runtime modules.
APP_ALLOW_MISSING_DEPS := true
APP_MK_EOF
fi
grep '^APP_ALLOW_MISSING_DEPS := true$' "$APP_MAKEFILE"


# The SDL Android runtime automatically extracts this first-run data ZIP into
# app-private storage. This is convenient for sideloaded test APKs. For a Play
# release, host the ZIP and replace the local filename in AndroidAppSettings.cfg
# with its HTTPS URL (the game data is larger than 150 MB).
mkdir -p "$APP_DIR/AndroidData"
DATA_ZIP="$APP_DIR/AndroidData/freedroid-data.zip"
if [ ! -s "$DATA_ZIP" ] || [ "${FREEDROID_REPACK_DATA:-0}" = 1 ]; then
  command -v zip >/dev/null 2>&1 || { echo "zip is required to package data/ and lua_modules/." >&2; exit 3; }
  TMP="$DATA_ZIP.tmp"
  rm -f "$TMP"
  (cd "$SOURCE_DIR" && zip -q -r -9 "$TMP" data lua_modules)
  mv "$TMP" "$DATA_ZIP"
fi

echo "FreedroidRPG source patched; data archive ready: $DATA_ZIP"
