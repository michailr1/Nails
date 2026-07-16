#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _mtime(path: Path) -> datetime:
    return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)


def _remove(path: Path, *, apply: bool) -> None:
    print(f"REMOVE {path}")
    if not apply:
        return
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink(missing_ok=True)


def _keep_latest(paths: list[Path], count: int) -> set[Path]:
    return set(sorted(paths, key=_mtime, reverse=True)[:count])


def _daily_retention(root: Path, *, apply: bool) -> None:
    daily = sorted((root / "daily").glob("nails-*.sql.gz"), key=_mtime, reverse=True)
    by_day: dict[str, list[Path]] = defaultdict(list)
    for path in daily:
        stamp = path.name.removeprefix("nails-")[:8]
        by_day[stamp].append(path)
    kept_days = set(sorted(by_day, reverse=True)[:5])
    keep = {max(by_day[day], key=_mtime) for day in kept_days}
    for path in daily:
        if path not in keep:
            _remove(path, apply=apply)


def _generation_retention(root: Path, name: str, count: int, *, apply: bool) -> None:
    paths = list((root / name).glob("nails-*.sql.gz"))
    keep = _keep_latest(paths, count)
    for path in paths:
        if path not in keep:
            _remove(path, apply=apply)


def _predeploy_retention(root: Path, now: datetime, *, apply: bool) -> None:
    paths = list(root.glob("nails-before-deploy-*.sql.gz"))
    keep: set[Path] = {path for path in paths if now - _mtime(path) <= timedelta(hours=24)}
    older_by_day: dict[str, list[Path]] = defaultdict(list)
    for path in paths:
        age = now - _mtime(path)
        if timedelta(hours=24) < age <= timedelta(days=5):
            older_by_day[_mtime(path).date().isoformat()].append(path)
    for day in sorted(older_by_day, reverse=True):
        keep.add(max(older_by_day[day], key=_mtime))
    for path in paths:
        if path not in keep:
            _remove(path, apply=apply)


def _runtime_retention(runtime_root: Path, now: datetime, *, apply: bool) -> None:
    successful = [
        path
        for path in runtime_root.iterdir()
        if path.name.startswith("deploy-success-")
        or (path.name.startswith("deploy-") and not path.name.startswith("deploy-failed-"))
    ] if runtime_root.exists() else []
    keep = _keep_latest(successful, 2)
    for path in successful:
        if path not in keep:
            _remove(path, apply=apply)
    for path in runtime_root.glob("deploy-failed-*") if runtime_root.exists() else []:
        if now - _mtime(path) > timedelta(days=3):
            _remove(path, apply=apply)


def _log_retention(root: Path, now: datetime, *, apply: bool) -> None:
    for path in (root / "logs").glob("*"):
        if path.is_file() and now - _mtime(path) > timedelta(days=14):
            _remove(path, apply=apply)


def apply_retention(root: Path, runtime_root: Path, *, apply: bool, now: datetime) -> None:
    _daily_retention(root, apply=apply)
    _generation_retention(root, "weekly", 3, apply=apply)
    _generation_retention(root, "monthly", 12, apply=apply)
    _predeploy_retention(root, now, apply=apply)
    _runtime_retention(runtime_root, now, apply=apply)
    _log_retention(root, now, apply=apply)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    apply_retention(
        args.root,
        args.runtime_root,
        apply=args.apply,
        now=datetime.now(timezone.utc),
    )


if __name__ == "__main__":
    main()
