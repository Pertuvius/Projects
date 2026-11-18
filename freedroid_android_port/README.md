# FreedroidRPG Android port overlay (development scaffold)

This overlay targets the **SDL 1.2 Android runtime** in [`pelya/commandergenius`](https://github.com/pelya/commandergenius), not an SDL2 rewrite. It keeps FreedroidRPG's existing C engine and Lua game data, and asks the Android runtime to provide SDL 1.2, touch-to-mouse input, lifecycle integration, and the APK/AAB wrapper.

## Status

- Source audit completed against the public FreedroidRPG 1.0 code mirror.
- Android SDL runtime and its custom Autotools build hooks identified.
- A deterministic, idempotent compatibility patcher is included.
- ARM64 build scripts and runtime configuration are included.
- This is an initial integration scaffold; it is not a tested binary until the GitHub Actions build succeeds.
- The workflow uploads an APK artifact only if APK packaging completes successfully; no APK is committed to the repository.

## Why this route

FreedroidRPG already uses SDL 1.2 APIs. The Android runtime has an SDL 1.2 implementation and a documented custom-build-script path for Autotools projects. This avoids a first-pass conversion to SDL2. The initial build disables OpenGL and sound to reduce the native dependency surface; audio can be enabled once the first boot works.

## Directory layout

1. Clone `https://github.com/pelya/commandergenius` (branch `sdl_android`) into a working directory. The runtime keeps SDL 1.2 and SDL_gfx in its main repository. The NDK scans Android makefiles from SDL2_image too, so initialize SDL2, SDL2_image and its libjpeg/libpng submodules; unrelated game submodules are not needed for FreedroidRPG:

   ```sh
   git clone --branch sdl_android https://github.com/pelya/commandergenius.git
   git -C commandergenius submodule update --init --depth 1 project/jni/sdl2 project/jni/sdl2_image
   git -C commandergenius/project/jni/sdl2_image submodule update --init --depth 1 external/jpeg external/libpng
   ```

2. Copy this overlay's `AndroidAppSettings.cfg`, `AndroidBuild.sh`, `AndroidPreBuild.sh`, `icon.png` and `tools/` directory into:

   `commandergenius/project/jni/application/freedroidrpg/`
3. Download the official [FreedroidRPG 1.0 source archive](https://ftp.osuosl.org/pub/freedroid/freedroidRPG-1.0/freedroidRPG-1.0.tar.gz) (227 MB) and extract it as:

   `commandergenius/project/jni/application/freedroidrpg/freedroidRPG-1.0/`

   The extracted release archive must contain `configure`, `src/`, `data/` and `lua_modules/`. It may omit the Autotools input file (configure.ac) included in a developer checkout. The workflow normalizes the archive directory name to `freedroidRPG-1.0` before building.
4. Make sure Android SDK, NDK, Java, Gradle, Python 3, GNU make, Autotools, `pkg-config` and `zip` are installed. Set `ANDROID_HOME` / `ANDROID_SDK_ROOT` and `ANDROID_NDK_HOME` as expected by that repository.
5. Run `./build.sh debug freedroidrpg` from the repository root. The build script selects this app, generates the Android project settings from `AndroidAppSettings.cfg`, runs `AndroidPreBuild.sh`, builds the SDL 1.2, SDL_image and SDL_gfx Android modules, then invokes `AndroidBuild.sh` to cross-compile the original C game for `arm64-v8a`.

The pre-build hook narrows the generated `APP_MODULES` list to SDL 1.2, the runtime helpers, JPEG/PNG, SDL_image and SDL_gfx. The runtime otherwise adds optional audio and font modules that this game build does not use.
## What the patcher changes

`tools/apply_port_patches.py` makes only Android software-surface compatibility edits:

- Removes `SDL_HWSURFACE` from the SDL fullscreen-mode query.
- Uses a software `SDL_CreateRGBSurface()` instead of requesting `SDL_HWSURFACE`.
- Removes `SDL_RLEACCEL` from all four `SDL_SetAlpha()` calls. The SDL Android runtime documents that RLE acceleration is unsupported.

The patcher checks exact occurrence counts and is idempotent; it stops rather than silently editing an unexpected source version.

## Rendering, input and data

- Landscape, 16-bit software video and automatic screen resizing are enabled.
- The app uses the runtime's two-button touchscreen mouse: tap/drag for the primary pointer and long-press for the secondary button. An on-screen directional pad is enabled for keyboard-style navigation.
- Desktop OpenGL is disabled at configure time. FreedroidRPG already falls back to its SDL software renderer when compiled without `HAVE_LIBGL`.
- Sound is disabled for the first build. This avoids bringing SDL_mixer, Ogg/Vorbis and their Android modules into the first compile.
- `AndroidPreBuild.sh` creates `AndroidData/freedroid-data.zip` from the original `data/` and `lua_modules/` directories. The runtime extracts that ZIP into app-private storage on first launch, where the game's normal data-path discovery can find it.

The data ZIP is large. This local-asset configuration is intended for sideloaded development builds. Before a Google Play release, host the ZIP over HTTPS and change `AppDataDownloadUrl` in `AndroidAppSettings.cfg` to the download URL; alternatively configure the runtime's install-time asset pack and add explicit asset-pack extraction/copying before startup.

## Remote build option (avoids installing the Android toolchain locally)

The root-level `.github/workflows/build-freedroid-android.yml` runs on pushes to `freedroid-android-port` ; its manual dispatch event is available after this workflow file exists on the repository default branch. A matching template is included at `ci/build-android.yml.example`. It sets up Java/Android SDK/NDK on Ubuntu, downloads the official game source and SDL Android runtime, then uploads the debug APK as a workflow artifact. The first run is an integration test; report an APK only if the artifact upload succeeds.

## Build output

The custom script should produce:

`project/jni/application/freedroidrpg/libapplication-arm64-v8a.so`

The Android packaging script then combines it with the SDL runtime and Android app wrapper. The first acceptance test is an APK that opens the original game's title screen. Movement, dialogs, saving, resume-from-background, sound and performance must then be tested on real hardware.

## Known risks / next engineering steps

1. The public Android SDL runtime is a community port; its current NDK/Gradle compatibility must be confirmed on the build machine.
2. Some original menu/config code assumes a desktop mouse and keyboard. Touch-to-mouse is a first pass; a better mobile HUD may be needed.
3. The initial build intentionally has no sound. Once the game starts, add `sdl_mixer`, Ogg/Vorbis (or Tremor) and configure audio output.
4. SDL software rendering may be slower than the original desktop OpenGL renderer. Benchmark on the target phone before investing in an OpenGL ES / GL4ES renderer.
5. Confirm the licence of every bundled asset and translation, preserve notices and provide corresponding source under GPL-2.0-or-later where applicable before any commercial distribution.

## Reproducibility

Run the patcher more than once; the second invocation should report that changes are already applied. The scripts are POSIX shell and can be syntax-checked with `sh -n`. No generated APK or device test is claimed by this repository overlay.
