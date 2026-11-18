#!/bin/sh
# Cross-compile FreedroidRPG as libapplication.so for the SDL 1.2 Android runtime.
set -eu

ABI=${1:?usage: AndroidBuild.sh <abi> [autoconf-host]}
HOST=${2:-aarch64-linux-android}
case "$ABI" in
  arm64-v8a) DEFAULT_HOST=aarch64-linux-android ;;
  armeabi-v7a) DEFAULT_HOST=arm-linux-androideabi ;;
  x86) DEFAULT_HOST=i686-linux-android ;;
  x86_64) DEFAULT_HOST=x86_64-linux-android ;;
  *) echo "Unsupported ABI: $ABI" >&2; exit 2 ;;
esac
[ -n "${2:-}" ] || HOST=$DEFAULT_HOST

APP_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
PROJECT_DIR=$(CDPATH= cd -- "$APP_DIR/../../.." && pwd -P)
SOURCE_DIR=${FREEDROID_SOURCE_DIR:-"$APP_DIR/freedroidRPG-1.0"}
BUILD_DIR="$APP_DIR/build/$ABI"
LIB_DIR="$PROJECT_DIR/obj/local/$ABI"
ENV_WRAPPER="$APP_DIR/../setEnvironment-$ABI.sh"
SDL_CONFIG="$APP_DIR/android-tools/sdl-config"

if [ ! -x "$ENV_WRAPPER" ]; then
  echo "Missing Android cross-compiler wrapper: $ENV_WRAPPER" >&2
  exit 3
fi
if [ ! -f "$SOURCE_DIR/configure" ]; then
  echo "Missing $SOURCE_DIR/configure. Extract the official FreedroidRPG 1.0 source archive there first." >&2
  exit 4
fi
if [ ! -f "$LIB_DIR/libsdl-1.2.so" ] || [ ! -f "$LIB_DIR/libsdl_image.so" ] || [ ! -f "$LIB_DIR/libsdl_gfx.so" ]; then
  echo "SDL 1.2, SDL_image and SDL_gfx Android modules are not built for $ABI." >&2
  echo "Run the Commandergenius NDK first pass/build.sh after registering this app." >&2
  exit 5
fi

# The upstream configure.ac tests for the desktop library spellings. These
# link-time aliases point at the Android modules; the ELF SONAME remains the
# real lower-case module name used by the APK loader.
ln -sf libsdl_image.so "$LIB_DIR/libSDL_image.so"
ln -sf libsdl_gfx.so "$LIB_DIR/libSDL_gfx.so"

mkdir -p "$APP_DIR/android-tools" "$BUILD_DIR"
cat > "$SDL_CONFIG" <<'SDL_CONFIG_EOF'
#!/bin/sh
set -eu
: "${FREEDROID_ANDROID_PROJECT:?FREEDROID_ANDROID_PROJECT not set}"
: "${FREEDROID_ANDROID_ABI:?FREEDROID_ANDROID_ABI not set}"
PROJECT="$FREEDROID_ANDROID_PROJECT"
ABI="$FREEDROID_ANDROID_ABI"
JNI="$PROJECT/jni"
LIBDIR="$PROJECT/obj/local/$ABI"
case "${1:---cflags}" in
  --version) echo 1.2.15 ;;
  --cflags)
    printf '%s\n' "-I$JNI/sdl-1.2/include -I$JNI/sdl_image -I$JNI/sdl_image/include -I$JNI/png/include/android -I$JNI/sdl_gfx -I$JNI/sdl_gfx/include"
    ;;
  --libs|--static-libs)
    printf '%s\n' "-L$LIBDIR -lsdl-1.2"
    ;;
  --prefix) printf '%s\n' "$JNI/sdl-1.2" ;;
  --exec-prefix) printf '%s\n' "$JNI/sdl-1.2" ;;
  --cflags-only-I) printf '%s\n' "-I$JNI/sdl-1.2/include" ;;
  --libs-only-L) printf '%s\n' "-L$LIBDIR" ;;
  --libs-only-l) printf '%s\n' "-lsdl-1.2" ;;
  *) echo "Unknown sdl-config option: $1" >&2; exit 1 ;;
esac
SDL_CONFIG_EOF
chmod +x "$SDL_CONFIG"

export APILEVEL=24
export SHARED_LIBRARY_NAME=libapplication.so
export FREEDROID_ANDROID_PROJECT="$PROJECT_DIR"
export FREEDROID_ANDROID_ABI="$ABI"
export SDL_CONFIG
export PKG_CONFIG=${PKG_CONFIG:-$(command -v pkg-config || true)}
if [ -z "$PKG_CONFIG" ]; then
  echo "pkg-config is required by FreedroidRPG's configure script." >&2
  exit 6
fi
export LDFLAGS="-L$LIB_DIR ${LDFLAGS:-}"
# Dependencies required by the configure probes and the software-rendered game.
export LIBS="-lsdl-1.2 -ljpeg -lpng -lz ${LIBS:-}"

cd "$BUILD_DIR"
if [ ! -f Makefile ] || [ ! -f config.status ] || [ "$SOURCE_DIR/configure" -nt config.status ]; then
  "$ENV_WRAPPER" "$SOURCE_DIR/configure" \
    --srcdir="$SOURCE_DIR" \
    --host="$HOST" \
    --prefix="$BUILD_DIR/install" \
    --disable-opengl \
    --disable-sound \
    --with-embedded-lua \
    --disable-nls \
    --disable-backtrace \
    --disable-dev-tools \
    --disable-rtprof \
    --with-open-cmd=true
fi

LUA_CC=$("$ENV_WRAPPER" sh -c 'printf "%s" "$CC"')
LUA_AR=$("$ENV_WRAPPER" sh -c 'printf "%s" "$AR"')
LUA_RANLIB=$("$ENV_WRAPPER" sh -c 'printf "%s" "$RANLIB"')
if [ -z "$LUA_CC" ] || [ -z "$LUA_AR" ] || [ -z "$LUA_RANLIB" ]; then
  echo "Could not read Android cross tools from $ENV_WRAPPER" >&2
  exit 8
fi
echo "Lua cross compiler: $LUA_CC"
JOBS=${BUILD_NUM_CPUS:-$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo 4)}
"$ENV_WRAPPER" make -C externals/lua clean CC="$LUA_CC" AR="$LUA_AR rcu" RANLIB="$LUA_RANLIB"
"$ENV_WRAPPER" make -j"$JOBS" -C externals/lua CC="$LUA_CC" AR="$LUA_AR rcu" RANLIB="$LUA_RANLIB" MYCFLAGS="-fPIC"
"$ENV_WRAPPER" make -j"$JOBS" -C src


BUILT="$BUILD_DIR/src/freedroidRPG"
if [ ! -f "$BUILT" ]; then
  echo "Build did not produce $BUILT" >&2
  exit 7
fi
cp "$BUILT" "$APP_DIR/libapplication-$ABI.so"
echo "Built $APP_DIR/libapplication-$ABI.so"
