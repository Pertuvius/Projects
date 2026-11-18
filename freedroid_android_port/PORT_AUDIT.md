# FreedroidRPG → Android: source audit and implementation decisions

## Confirmed game source characteristics

The audited game source is the FreedroidRPG 1.0 codebase (public source mirror: https://github.com/oxgersa/freedroidRPG). It is a C/SDL 1.2 game with Lua scripting and game data under `data/` and `lua_modules/`. Its Autotools configuration requires SDL 1.2, SDL_image, SDL_gfx, libjpeg, libpng and zlib. OpenGL and SDL_mixer/audio are optional; Lua can be built from the bundled source.

Relevant source files and facts:

- `configure.ac`: has `--disable-opengl`, `--disable-sound`, `--with-embedded-lua`, `--disable-nls`, `--disable-backtrace`, `--disable-dev-tools` and `--disable-rtprof` options.
- `src/system.h`: includes SDL 1.2, SDL_image, and (when detected) SDL_gfx headers.
- `src/graphics.c`: software renderer exists; it uses `SDL_SetVideoMode()` without `SDL_HWSURFACE` in the non-OpenGL path. It also used `SDL_HWSURFACE` for a temporary RGB surface and `SDL_RLEACCEL` on alpha surfaces.
- `src/image.c`: used `SDL_RLEACCEL` in two places.
- `src/init.c`: queries fullscreen modes with `SDL_FULLSCREEN|SDL_HWSURFACE`.
- `src/input.c`: processes mouse motion/buttons and keyboard events. An Android SDL runtime can map touch to the mouse, with long-press as the secondary button.
- `src/misc.c`: searches for `lua_modules/FDdialog.lua` to identify the game data root. The Android runtime's local first-run ZIP extraction can place `data/` and `lua_modules/` into its private working directory, preserving this discovery logic.

## Android runtime integration

Runtime repository: https://github.com/pelya/commandergenius (branch `sdl_android`). Its README documents an SDL 1.2 Android backend, software-video requirements, touch-to-mouse controls, Android app settings, and a custom build script for Autotools projects. The runtime's `project/jni/sdl_image/Android.mk` and `sdl_gfx/Android.mk` build Android modules named `sdl_image` and `sdl_gfx`; those are listed in `CompiledLibraries` in the provided app settings.

The port keeps the game's SDL 1.2 API rather than converting it to SDL2. The first pass disables OpenGL and sound. The Android custom build script cross-compiles the game for `arm64-v8a`, links against SDL 1.2, SDL_image and SDL_gfx, and renames the result to the library filename expected by the Android wrapper.

## Android-specific source changes

`tools/apply_port_patches.py` applies these exact source changes, with occurrence-count checks:

1. Change the fullscreen mode query to `SDL_ListModes(NULL, SDL_FULLSCREEN)`.
2. Change the software-renderer's temporary RGB surface to `SDL_CreateRGBSurface(0, ...)`.
3. Remove `SDL_RLEACCEL` from all four alpha-setting calls in `graphics.c` and `image.c`.

The Android SDL runtime's README explicitly states that the software path should not request `SDL_HWSURFACE` in `SDL_SetVideoMode()`/`SDL_CreateRGBSurface()` and that `SDL_RLEACCEL` is unsupported. These edits satisfy those documented constraints without rewriting game logic.

## Data-size and distribution consideration

FreedroidRPG data is large (Debian's 1.0 data package reports roughly 223 MB compressed and 249 MB installed). The development configuration packages `data/` and `lua_modules/` into a first-run ZIP in `AndroidData/`. For a production Play Store release, the runtime README recommends hosting data files larger than 150 MB and using an HTTPS data URL; an install-time asset-pack implementation is another distribution option but needs a defined extraction path before the game's normal filesystem loader can consume it.

## Build verification

GitHub Actions run 44289307035 downloaded the SDL Android runtime and FreedroidRPG 1.0 source, ran the pre-build hook, applied the compatibility patches, and created AndroidData/freedroid-data.zip. Its NDK first pass stopped on the shared runtime's unused SDL 1.2 mixer reference to an undefined ogg module.

Run 44290864690 stopped at the same NDK check because the pre-build hook was not executable in that commit. The hook's executable bit was restored afterward.

Run 44291736680 confirmed the hook runs, then found the release archive omits configure.ac. Run 44292411160 passed the hook's source checks but the patcher rejected the source root. The redundant root check is removed. Run 44293218737 then reported src/init.c missing under that root. Run 44294073282 passed CI checks for these files before build.sh, but the pre-build hook later found src/init.c missing. Run 44294915473 confirmed the shell sees all three C files immediately before invoking Python, yet Python still reports src/init.c missing. The patcher now logs Path.exists() and Path.is_file() for each target to identify the mismatch.

No game native library or APK has completed a successful build. Device launch, controls, save paths, lifecycle/resume, performance and playability remain unverified.