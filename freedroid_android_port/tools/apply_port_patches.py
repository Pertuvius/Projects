#!/usr/bin/env python3
"""Apply small, idempotent SDL-Android compatibility edits to FreedroidRPG."""
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
        print(f"Checking source file {path}: exists={path.exists()}, is_file={path.is_file()}", flush=True)
        if not path.is_file():
            raise SystemExit(f"Required source file is missing: {path}")
        for old, new, expected in edits:
            if replace_exact(path, old, new, expected=expected):
                applied.append(f"{relative}: {old} -> {new}")
    return applied


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    args = parser.parse_args()
    root = args.source.absolute()
    print(f"Python source root: arg={args.source!s} arg_exists={args.source.exists()} root={root!s} root_exists={root.exists()} root_is_dir={root.is_dir()}", flush=True)
    changes = patch_source(root)
    if changes:
        print("Applied Android SDL compatibility changes:")
        for change in changes:
            print("  -", change)
    else:
        print("Android SDL compatibility changes already applied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
