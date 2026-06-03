#!/usr/bin/env python3
"""Migrate StockBench data cache to a shared cache directory.

Copies storage/cache entries used by data_hub while intentionally excluding the
LLM cache. This is intended for Fedora/Linux and WSL worktree setups where data
cache should be shared but logs, reports, tmp files, and LLM cache stay local.
"""

from __future__ import annotations

import argparse
import os
import platform
import re
import shlex
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

EXCLUDED_NAMES = {"llm"}
DEFAULT_TARGET = "~/.cache/stockbench/data-cache"
ENV_NAME = "STOCKBENCH_DATA_CACHE_DIR"
SHELL_BLOCK_START = "# >>> stockbench data cache >>>"
SHELL_BLOCK_END = "# <<< stockbench data cache <<<"


@dataclass
class CopyStats:
    copied_files: int = 0
    skipped_files: int = 0
    copied_dirs: int = 0
    errors: int = 0


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def is_wsl() -> bool:
    if platform.system().lower() != "linux":
        return False
    try:
        text = Path("/proc/version").read_text(encoding="utf-8", errors="ignore").lower()
        return "microsoft" in text or "wsl" in text
    except Exception:
        return False


def expand_path(value: str) -> Path:
    expanded = os.path.expandvars(os.path.expanduser(str(value)))

    # Convenience for WSL users who paste a Windows path such as
    # C:\Users\name\AppData\Local\stockbench\data-cache.
    if platform.system().lower() != "windows":
        match = re.match(r"^([A-Za-z]):[\\/](.*)$", expanded)
        if match:
            drive = match.group(1).lower()
            rest = match.group(2).replace("\\", "/")
            expanded = f"/mnt/{drive}/{rest}"

    return Path(expanded).resolve(strict=False)


def default_target() -> Path:
    return expand_path(os.getenv(ENV_NAME) or DEFAULT_TARGET)


def infer_shell_profile() -> Path:
    shell = Path(os.getenv("SHELL", "")).name.lower()
    home = Path.home()
    if shell == "zsh":
        return home / ".zshrc"
    if shell == "bash":
        return home / ".bashrc"
    return home / ".profile"


def shell_export_block(target: Path) -> str:
    return (
        f"{SHELL_BLOCK_START}\n"
        f"export {ENV_NAME}={shlex.quote(str(target))}\n"
        f"{SHELL_BLOCK_END}\n"
    )


def persist_shell_env(target: Path, profile: Path) -> None:
    profile = expand_path(str(profile))
    block = shell_export_block(target)
    text = ""
    if profile.exists():
        text = profile.read_text(encoding="utf-8", errors="ignore")

    pattern = re.compile(
        re.escape(SHELL_BLOCK_START) + r".*?" + re.escape(SHELL_BLOCK_END) + r"\n?",
        flags=re.DOTALL,
    )
    if pattern.search(text):
        new_text = pattern.sub(block, text)
    else:
        sep = "" if not text or text.endswith("\n") else "\n"
        new_text = f"{text}{sep}{block}"

    profile.parent.mkdir(parents=True, exist_ok=True)
    profile.write_text(new_text, encoding="utf-8")
    print(f"persisted: {ENV_NAME} in {profile}")


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def iter_cache_entries(source: Path) -> list[Path]:
    if not source.exists():
        return []
    entries = []
    for entry in sorted(source.iterdir(), key=lambda p: p.name):
        if entry.name in EXCLUDED_NAMES:
            continue
        entries.append(entry)
    return entries


def copy_entry(source_entry: Path, target_entry: Path, *, overwrite: bool, dry_run: bool) -> CopyStats:
    stats = CopyStats()

    if source_entry.is_dir():
        for root, dirs, files in os.walk(source_entry):
            root_path = Path(root)
            relative_root = root_path.relative_to(source_entry)
            target_root = target_entry / relative_root

            if dry_run:
                stats.copied_dirs += 1
            else:
                try:
                    target_root.mkdir(parents=True, exist_ok=True)
                    stats.copied_dirs += 1
                except Exception as exc:
                    print(f"error: cannot create directory {target_root}: {exc}", file=sys.stderr)
                    stats.errors += 1
                    continue

            dirs[:] = [dirname for dirname in dirs if dirname not in EXCLUDED_NAMES]

            for filename in files:
                src_file = root_path / filename
                dst_file = target_root / filename
                if dst_file.exists() and not overwrite:
                    stats.skipped_files += 1
                    continue
                if dry_run:
                    stats.copied_files += 1
                    continue
                try:
                    dst_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src_file, dst_file)
                    stats.copied_files += 1
                except Exception as exc:
                    print(f"error: cannot copy {src_file} -> {dst_file}: {exc}", file=sys.stderr)
                    stats.errors += 1
    elif source_entry.is_file():
        if target_entry.exists() and not overwrite:
            stats.skipped_files += 1
        elif dry_run:
            stats.copied_files += 1
        else:
            try:
                target_entry.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_entry, target_entry)
                stats.copied_files += 1
            except Exception as exc:
                print(f"error: cannot copy {source_entry} -> {target_entry}: {exc}", file=sys.stderr)
                stats.errors += 1

    return stats


def add_stats(total: CopyStats, part: CopyStats) -> None:
    total.copied_files += part.copied_files
    total.skipped_files += part.skipped_files
    total.copied_dirs += part.copied_dirs
    total.errors += part.errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Copy StockBench data cache from storage/cache to a shared directory, "
            "excluding storage/cache/llm."
        )
    )
    parser.add_argument(
        "--source",
        default=str(repo_root() / "storage" / "cache"),
        help="source cache directory, default: <repo>/storage/cache",
    )
    parser.add_argument(
        "--target",
        default=None,
        help=f"target shared data cache directory, default: ${ENV_NAME} or {DEFAULT_TARGET}",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="overwrite files that already exist in the target",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="show what would be copied without writing files",
    )
    parser.add_argument(
        "--persist-shell",
        action="store_true",
        help="append/update a managed STOCKBENCH_DATA_CACHE_DIR export block in the shell profile",
    )
    parser.add_argument(
        "--shell-profile",
        default=None,
        help="shell startup file to update with --persist-shell; default infers from $SHELL",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source = expand_path(args.source)
    target = expand_path(args.target) if args.target else default_target()

    if not source.exists():
        print(f"source cache directory does not exist: {source}", file=sys.stderr)
        return 1
    if not source.is_dir():
        print(f"source is not a directory: {source}", file=sys.stderr)
        return 1

    source_abs = source.resolve(strict=False)
    target_abs = target.resolve(strict=False)
    if source_abs == target_abs:
        print("source and target are the same; nothing to migrate", file=sys.stderr)
        return 1
    if is_relative_to(target_abs, source_abs):
        print("target must not be inside source cache directory", file=sys.stderr)
        return 1

    if is_wsl() and str(target_abs).startswith("/mnt/"):
        print(
            "warning: target is under /mnt in WSL; many small cache files may be slower than using $HOME/.cache",
            file=sys.stderr,
        )

    entries = iter_cache_entries(source)
    if not entries:
        print(f"no data cache entries found under {source}")
        return 0

    mode = "dry-run" if args.dry_run else "copy"
    print(f"mode: {mode}")
    print(f"source: {source_abs}")
    print(f"target: {target_abs}")
    print("excluded: llm")
    print("entries:")
    for entry in entries:
        print(f"  - {entry.name}")

    total = CopyStats()
    for entry in entries:
        part = copy_entry(entry, target / entry.name, overwrite=args.overwrite, dry_run=args.dry_run)
        add_stats(total, part)

    print("summary:")
    print(f"  copied files: {total.copied_files}")
    print(f"  skipped existing files: {total.skipped_files}")
    print(f"  touched directories: {total.copied_dirs}")
    print(f"  errors: {total.errors}")

    if args.persist_shell:
        if args.dry_run:
            profile = expand_path(args.shell_profile) if args.shell_profile else infer_shell_profile()
            print("persist shell dry-run:")
            print(f"  profile: {profile}")
            print(shell_export_block(target_abs).rstrip())
        elif total.errors:
            print("skip shell persistence because migration had errors", file=sys.stderr)
        else:
            profile = expand_path(args.shell_profile) if args.shell_profile else infer_shell_profile()
            persist_shell_env(target_abs, profile)
    elif not args.dry_run:
        print("next step:")
        print(f"  export {ENV_NAME}=\"{target_abs}\"")
        print("  # or rerun with --persist-shell to update your shell profile")

    return 1 if total.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
