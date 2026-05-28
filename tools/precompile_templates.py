#!/usr/bin/env python3
"""Precompile utemplate templates in the app/templates folder."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Precompile utemplate templates stored in the app/templates folder."
    )
    parser.add_argument(
        "template_dir",
        nargs="?",
        default="app/templates",
        help="Template directory to scan for .tpl files (default: app/templates)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force recompilation of all templates by removing existing compiled modules first.",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Recursively compile .tpl files in subdirectories.",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(root / "app"))

    try:
        from utemplate import recompile
    except ImportError as exc:
        raise SystemExit(
            "Unable to import utemplate from app/; make sure you run this from the repository root. "
            + str(exc)
        )

    template_dir = Path(args.template_dir)
    if not template_dir.is_absolute():
        template_dir = (root / template_dir).resolve()

    if not template_dir.exists() or not template_dir.is_dir():
        raise SystemExit(f"Template directory does not exist: {template_dir}")

    # Load app package from root/app so templates directory can be imported as a namespace package.
    app_root = root / "app"
    sys.path.insert(0, str(app_root))
    working_dir = Path.cwd()
    try:
        from utemplate import recompile
    except ImportError as exc:
        raise SystemExit(
            "Unable to import utemplate from app/; make sure you run this from the repository root. "
            + str(exc)
        )

    pattern = "**/*.tpl" if args.recursive else "*.tpl"
    templates = sorted(template_dir.glob(pattern))

    if not templates:
        print(f"No template files found in {template_dir}.")
        return 0

    # The loader expects template paths relative to the template directory, and it
    # resolves template files relative to the current working directory.
    import builtins
    import os

    orig_open = builtins.open

    def utf8_open(file, mode='r', *args, **kwargs):
        if 'b' in mode:
            return orig_open(file, mode, *args, **kwargs)
        if 'encoding' not in kwargs:
            kwargs['encoding'] = 'utf-8'
        return orig_open(file, mode, *args, **kwargs)

    builtins.open = utf8_open
    try:
        os.chdir(app_root)
        loader = recompile.Loader(None, "templates")

        for template_path in templates:
            relative_name = str(template_path.relative_to(template_dir)).replace("\\", "/")
            if args.force:
                compiled = template_dir / relative_name.replace('.', '_')
                compiled = compiled.with_suffix('.py')
                if compiled.exists():
                    compiled.unlink()
            print(f"Compiling {relative_name}...")
            loader.load(relative_name)
    finally:
        builtins.open = orig_open
        os.chdir(working_dir)

    print(f"Precompiled {len(templates)} template(s) in {template_dir}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
