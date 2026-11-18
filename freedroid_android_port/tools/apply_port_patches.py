#!/usr/bin/env python3
"""Apply idempotent SDL-Android compatibility edits to FreedroidRPG and runtime."""
from __future__ import annotations

import argparse
from pathlib import Path


def replace_exact(path: Path, old: str, new: str, *, expected: int = 1) -> bool:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count == 0 and new in text:
        return False  # Already patched.
    if count != expected:
        raise SystemExit(
            f"Patch mismatch in {path}: expected {expected} occurrence(s) of {old!r}, found {count}. "
            "Check the source version before continuing."
        )
    path.write_text(text.replace(old, new), encoding="utf-8")
    return True


def insert_before_once(path: Path, marker: str, insertion: str, sentinel: str) -> bool:
    text = path.read_text(encoding="utf-8")
    if sentinel in text:
        return False
    if text.count(marker) != 1:
        raise SystemExit(f"Patch mismatch in {path}: expected one insertion marker {marker!r}")
    path.write_text(text.replace(marker, insertion + marker), encoding="utf-8")
    return True

def patch_source(root: Path) -> list[str]:
    applied: list[str] = []
    targets = {
        "src/init.c": [
            ("SDL_ListModes(NULL, SDL_FULLSCREEN|SDL_HWSURFACE)",
             "SDL_ListModes(NULL, SDL_FULLSCREEN)", 1),
            ("S_IREAD | S_IWRITE | S_IEXEC",
             "S_IRUSR | S_IWUSR | S_IXUSR", 1),
        ],
        "src/graphics.c": [
            ("SDL_CreateRGBSurface(SDL_HWSURFACE,", "SDL_CreateRGBSurface(0,", 1),
            ("SDL_SRCALPHA | SDL_RLEACCEL", "SDL_SRCALPHA", 2),
        ],
        "src/image.c": [
            ("SDL_SRCALPHA | SDL_RLEACCEL", "SDL_SRCALPHA", 2),
        ],
        "externals/lua/lua.mk": [
            ("CFLAGS= -O2 -Wall -Wextra $(SYSCFLAGS) $(MYCFLAGS)",
             "CFLAGS= -O2 -Wall -Wextra -fPIC $(SYSCFLAGS) $(MYCFLAGS)", 1),
        ],
    }
    locale_source = root / "src/misc.c"
    locale_fallback = "#ifndef LOCALEDIR\n#define LOCALEDIR \"\"\n#endif\n\n"
    if insert_before_once(locale_source, "void init_data_dirs_path(void)", locale_fallback, "#ifndef LOCALEDIR"):
        applied.append("src/misc.c: define empty LOCALEDIR fallback when NLS is disabled")
    for relative, edits in targets.items():
        path = root / relative
        if not path.is_file():
            raise SystemExit(f"Required source file is missing: {path}")
        for old, new, expected in edits:
            if replace_exact(path, old, new, expected=expected):
                applied.append(f"{relative}: {old} -> {new}")
    return applied


def configure_runtime_modules(project_root: Path) -> list[str]:
    """Limit NDK modules and skip unused media makefiles for this silent build."""
    changes: list[str] = []
    guard = "ifeq ($(FREEDROID_OPTIONAL_MEDIA_ENABLED),1)"
    optional_modules = ("sdl_mixer", "sdl_sound", "sdl_ttf", "flac", "fontconfig", "sndfile", "theora", "tremor")
    for module in optional_modules:
        path = project_root / "jni" / module / "Android.mk"
        if not path.is_file():
            raise SystemExit(f"Required SDL runtime module file is missing: {path}")
        text = path.read_text(encoding="utf-8")
        if guard not in text:
            text = f"{guard}\n{text.rstrip()}\n\nendif # FREEDROID_OPTIONAL_MEDIA_ENABLED\n"
            path.write_text(text, encoding="utf-8")
            changes.append(f"{module}: optional media module guarded")

    settings = project_root / "jni" / "Settings.mk"
    if not settings.is_file():
        raise SystemExit(f"Generated SDL runtime settings are missing: {settings}")
    lines = settings.read_text(encoding="utf-8").splitlines()
    starts = [i for i, line in enumerate(lines) if line.startswith("APP_MODULES :=")]
    if len(starts) != 1:
        raise SystemExit(f"Expected one APP_MODULES assignment in {settings}, found {len(starts)}")
    start = starts[0]
    end = start
    while lines[end].rstrip().endswith("\\"):
        end += 1
        if end >= len(lines):
            raise SystemExit(f"Unterminated APP_MODULES assignment in {settings}")
    current = " ".join(lines[start:end + 1]).split(":=", 1)[1].replace("\\", " ").split()
    required = ["sdl-1.2", "sdl_native_helpers", "jpeg", "png", "sdl_image", "sdl_gfx"]
    missing = [module for module in required if module not in current]
    if missing:
        raise SystemExit(f"Required modules missing from APP_MODULES in {settings}: {', '.join(missing)}")
    replacement = "APP_MODULES := " + " ".join(required)
    if lines[start:end + 1] != [replacement]:
        lines[start:end + 1] = [replacement]
        settings.write_text("\n".join(lines) + "\n", encoding="utf-8")
        changes.append(f"APP_MODULES restricted to {' '.join(required)}")
    return changes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--runtime-project", type=Path, required=True)
    args = parser.parse_args()

    changes = patch_source(args.source.absolute())
    changes.extend(configure_runtime_modules(args.runtime_project.absolute()))
    if changes:
        print("Applied Android compatibility changes:")
        for change in changes:
            print("  -", change)
    else:
        print("Android compatibility changes already applied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())