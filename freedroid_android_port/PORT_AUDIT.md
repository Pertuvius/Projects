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

The initial CI iterations fixed Android SDK package installation, the release archive's lowercase top-level directory, recursive submodule timeout, missing SDL2/SDL_image submodules and a mixed-line-ending issue in the pre-build hook. Run 44298627146 confirmed the game source patches and data ZIP complete, then exposed the runtime's optional audio module dependencies.

Runs 44299493923 through 44300323953 showed the runtime's SDL_mixer, SDL_sound, SDL_ttf and sndfile modules reference missing Ogg/FLAC or FreeType/Harfbuzz dependencies. Run 44301163799 exposed a temporary makefile-format assumption in the attempted workaround. Run 44302573245's diagnostic showed the actual cause: the runtime-generated `APP_MODULES` included ogg, FLAC, Vorbis and FreeType even though the app's `COMPILED_LIBRARIES` was only `sdl_image sdl_gfx`. Run 44303528051 confirmed that `APP_MODULES` narrowing removes the top-level ogg target, but NDK still validates included `sdl_mixer` makefiles and reported its missing ogg dependency. The hook now both narrows `APP_MODULES` to SDL 1.2, runtime helpers, JPEG/PNG, SDL_image and SDL_gfx and guards the unused media makefiles. Run 44303946632 passed runtime module checks and reached configure, which rejected `--prefix=.`. `AndroidBuild.sh` now uses an absolute build-local install prefix; the next run must verify configure, compilation, NDK linking and APK packaging.

No game native library or APK has completed a successful build. Device launch, controls, save paths, lifecycle/resume, performance and playability remain unverified.