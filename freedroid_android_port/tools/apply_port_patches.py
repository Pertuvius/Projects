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


def patch_source(root: Path) -> list[str]:
    applied: list[str] = []
    targets = {
        "src/init.c": [
            ("SDL_ListModes(NULL, SDL_FULLSCREEN|SDL_HWSURFACE)",
             "SDL_ListModes(NULL, SDL_FULLSCREEN)", 1),
        ],
        "src/graphics.c": [
            ("SDL_CreateRGBSurface(SDL_HWSURFACE,", "SDL_CreateRGBSurface(0,", 1),
            ("SDL_SRCALPHA | SDL_RLEACCEL", "SDL_SRCALPHA", 2),
        ],
        "src/image.c": [
            ("SDL_SRCALPHA | SDL_RLEACCEL", "SDL_SRCALPHA", 2),
        ],
    }
    for relative, edits in targets.items():
        path = root / relative
        if not path.is_file():
            raise SystemExit(f"Required source file is missing: {path}")
        for old, new, expected in edits:
            if replace_exact(path, old, new, expected=expected):
                applied.append(f"{relative}: {old} -> {new}")
    return applied


def disable_unused_audio_modules(project_root: Path) -> list[str]:
    """Keep runtime modules with optional media dependencies out of this silent build."""
    changed: list[str] = []
    guard = "ifeq ($(FREEDROID_OPTIONAL_MEDIA_ENABLED),1)"
    for module in ("sdl_mixer", "sdl_sound", "sdl_ttf", "flac", "fontconfig", "sndfile", "theora", "tremor"):
        path = project_root / "jni" / module / "Android.mk"
        if not path.is_file():
            raise SystemExit(f"Required SDL runtime module file is missing: {path}")
        text = path.read_text(encoding="utf-8")
        if guard in text:
            continue
        text = f"{guard}\n{text.rstrip()}\n\nendif # FREEDROID_OPTIONAL_MEDIA_ENABLED\n"
        path.write_text(text, encoding="utf-8")
        changed.append(f"{module}: optional media module guarded")
    return changed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--runtime-project", type=Path, required=True)
    args = parser.parse_args()

    changes = patch_source(args.source.absolute())
    changes.extend(disable_unused_audio_modules(args.runtime_project.absolute()))
    if changes:
        print("Applied Android compatibility changes:")
        for change in changes:
            print("  -", change)
    else:
        print("Android compatibility changes already applied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())