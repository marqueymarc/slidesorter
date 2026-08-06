#!/usr/bin/env python3
"""Build a reusable SlideSorter photo and video review gallery."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
from subprocess import DEVNULL, run
from urllib.parse import quote

from .actions import (
    DestinationAction,
    actions_from_raw,
    legacy_actions,
    validate_actions,
)
from .state import (
    APPEARANCE_MODES,
    DEFAULT_PROFILE,
    StateCompatibilityError,
    automatic_state_dir,
    ensure_compatible_state,
    platform_state_root,
    state_identity,
    validate_appearance,
    validate_profile,
)


def default_state_root() -> Path:
    """Backward-compatible name for the platform fallback state root."""

    return platform_state_root()


ASSET_ROOT = Path(__file__).with_name("assets")
VIDEO_EXTENSIONS = {".mov", ".mp4", ".m4v", ".avi", ".mts", ".m2ts", ".3gp", ".mkv"}
PICTURE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".heif", ".tif", ".tiff", ".bmp"
}
ASSET_FILES = (
    "index.html", "app.css", "appearance.js", "app.js", "viewer.html", "history.html", "history.js", "pointer-probe.html", "favicon.svg",
)
DEFAULT_HISTORY_RETENTION_DAYS = 90


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--media-root", type=Path, required=True)
    parser.add_argument("--gallery-root", type=Path)
    parser.add_argument(
        "--profile",
        default=DEFAULT_PROFILE,
        help="Named state profile when --gallery-root is omitted (default: %(default)s)",
    )
    parser.add_argument("--title")
    parser.add_argument("--source-label", help="Defaults to the media root directory name")
    parser.add_argument("--staged-name", default="Staged", help="Directory name under the media root")
    parser.add_argument("--removed-name", default="Removed", help="Directory name under the media root")
    parser.add_argument("--staged-root", type=Path)
    parser.add_argument("--removed-root", type=Path)
    parser.add_argument(
        "--actions-json",
        help="JSON array of ordered destination labels and roots; normally managed in Settings",
    )
    parser.add_argument(
        "--keep-structure",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Preserve each source-relative path beneath its destination",
    )
    parser.add_argument("--media-mode", choices=("videos", "pictures", "both"))
    parser.add_argument("--appearance", choices=tuple(sorted(APPEARANCE_MODES)))
    parser.add_argument("--thumbnail-width", type=int)
    parser.add_argument("--thumbnail-policy", choices=("lazy", "eager"))
    parser.add_argument("--workers", type=int)
    parser.add_argument(
        "--history-retention-days",
        type=int,
        default=None,
        help="Days to keep Purged history records after reconciliation",
    )
    return parser.parse_args(argv)


def validate_roots(media_root: Path, staged_root: Path, removed_root: Path) -> None:
    """Backward-compatible validator for the original two destinations."""

    try:
        validate_actions(
            media_root,
            (
                DestinationAction("stage", "Stage", staged_root),
                DestinationAction("remove", "Remove", removed_root),
            ),
        )
    except ValueError as error:
        raise SystemExit(str(error)) from error


def remembered_config(gallery_root: Path, media_root: Path) -> dict[str, object] | None:
    try:
        raw = json.loads((gallery_root / "gallery-config.json").read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, TypeError):
        return None
    if not isinstance(raw, dict):
        return None
    try:
        remembered_root = Path(str(raw.get("media_root", ""))).expanduser().resolve()
    except (OSError, RuntimeError):
        return None
    return raw if remembered_root == media_root else None


def configured_actions(
    args: argparse.Namespace,
    media_root: Path,
    remembered: dict[str, object] | None,
) -> tuple[DestinationAction, ...]:
    try:
        if args.actions_json:
            return actions_from_raw(media_root, json.loads(args.actions_json))
        if args.staged_root is not None or args.removed_root is not None:
            return legacy_actions(
                media_root,
                args.staged_root,
                args.removed_root,
                args.staged_name,
                args.removed_name,
            )
        if remembered and isinstance(remembered.get("actions"), list):
            return actions_from_raw(media_root, remembered["actions"])
        if remembered:
            return legacy_actions(
                media_root,
                remembered.get("staged_root"),
                remembered.get("removed_root"),
                str(remembered.get("staged_name", args.staged_name)),
                str(remembered.get("removed_name", args.removed_name)),
            )
        return legacy_actions(media_root, None, None, args.staged_name, args.removed_name)
    except (ValueError, json.JSONDecodeError) as error:
        raise SystemExit(str(error)) from error


def selected_extensions(mode: str) -> set[str]:
    if mode == "videos":
        return VIDEO_EXTENSIONS
    if mode == "pictures":
        return PICTURE_EXTENSIONS
    return VIDEO_EXTENSIONS | PICTURE_EXTENSIONS


def discover_media(media_root: Path, excluded_roots: tuple[Path, ...], extensions: set[str]) -> list[Path]:
    found: list[Path] = []
    for current_text, directory_names, file_names in os.walk(media_root):
        current = Path(current_text)
        directory_names[:] = [
            name
            for name in directory_names
            if not any((current / name).resolve() == excluded for excluded in excluded_roots)
        ]
        for name in file_names:
            path = current / name
            if path.suffix.lower() in extensions:
                found.append(path)
    return sorted(found, key=lambda path: (path.stat().st_mtime, str(path).casefold()))


def human_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024 or unit == "TiB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    raise AssertionError("unreachable")


def thumbnail_path_for(media: Path, thumbs: Path, width: int) -> Path:
    stat = media.stat()
    fingerprint = f"{media}:{stat.st_size}:{stat.st_mtime_ns}:{width}"
    return thumbs / f"{hashlib.sha256(fingerprint.encode()).hexdigest()[:24]}.jpg"


def thumbnail_for(media: Path, thumbs: Path, width: int, kind: str) -> tuple[Path, str | None]:
    thumb = thumbnail_path_for(media, thumbs, width)
    if thumb.exists() and thumb.stat().st_size:
        return thumb, None
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return thumb, "ffmpeg is not installed"
    offsets = ("1", "0") if kind == "video" else ("0",)
    for offset in offsets:
        command = [
            ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-ss", offset,
            "-i", str(media), "-frames:v", "1", "-vf", f"scale={width}:-2",
            "-q:v", "3", "-y", str(thumb),
        ]
        completed = run(command, stdout=DEVNULL, stderr=DEVNULL)
        if completed.returncode == 0 and thumb.exists() and thumb.stat().st_size:
            return thumb, None
    if kind == "picture":
        sips = shutil.which("sips")
        if sips:
            completed = run(
                [sips, "-s", "format", "jpeg", "-Z", str(width), str(media), "--out", str(thumb)],
                stdout=DEVNULL,
                stderr=DEVNULL,
            )
            if completed.returncode == 0 and thumb.exists() and thumb.stat().st_size:
                return thumb, None
    return thumb, "Thumbnail unavailable"


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    media_root = args.media_root.expanduser().resolve()
    try:
        profile = validate_profile(args.profile)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    gallery_root = (
        args.gallery_root.expanduser().resolve()
        if args.gallery_root is not None
        else automatic_state_dir(media_root, profile).resolve()
    )
    try:
        ensure_compatible_state(gallery_root, media_root, profile)
    except StateCompatibilityError as error:
        raise SystemExit(str(error)) from error
    remembered = remembered_config(gallery_root, media_root) or {}
    title = args.title or str(remembered.get("title", "Media Library"))
    source_label = args.source_label or str(remembered.get("source_label", media_root.name))
    media_mode = args.media_mode or str(remembered.get("media_mode", "both"))
    try:
        appearance = validate_appearance(args.appearance or remembered.get("appearance", "system"))
    except ValueError as error:
        raise SystemExit(str(error)) from error
    thumbnail_width = args.thumbnail_width or int(remembered.get("thumbnail_width", 720))
    thumbnail_policy = args.thumbnail_policy or str(remembered.get("thumbnail_policy", "lazy"))
    workers = args.workers or int(remembered.get("workers", 4))
    actions = configured_actions(args, media_root, remembered)
    keep_structure = (
        bool(remembered.get("keep_structure", True))
        if args.keep_structure is None and remembered
        else args.keep_structure is not False
    )
    history_retention_days = (
        int(remembered.get("history_retention_days", DEFAULT_HISTORY_RETENTION_DAYS))
        if args.history_retention_days is None and remembered
        else DEFAULT_HISTORY_RETENTION_DAYS if args.history_retention_days is None
        else args.history_retention_days
    )
    if history_retention_days < 0 or history_retention_days > 3650:
        raise SystemExit("History retention must be between 0 and 3650 days")
    if thumbnail_width < 160 or thumbnail_width > 2400:
        raise SystemExit("Thumbnail width must be between 160 and 2400 pixels")
    for asset in ASSET_FILES:
        if not (ASSET_ROOT / asset).is_file():
            raise SystemExit(f"Gallery asset is missing: {ASSET_ROOT / asset}")

    gallery_root.mkdir(parents=True, exist_ok=True)
    thumbs = gallery_root / "thumbs"
    thumbs.mkdir(exist_ok=True)
    excluded = tuple(
        root
        for root in (*[action.root for action in actions], gallery_root)
        if root.is_relative_to(media_root)
    )
    media_files = discover_media(media_root, excluded, selected_extensions(media_mode))

    results: dict[Path, tuple[Path, str | None]] = {
        media: (thumbnail_path_for(media, thumbs, thumbnail_width), None) for media in media_files
    }
    if thumbnail_policy == "eager":
        with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            futures = {
                pool.submit(
                    thumbnail_for,
                    media,
                    thumbs,
                    thumbnail_width,
                    "video" if media.suffix.lower() in VIDEO_EXTENSIONS else "picture",
                ): media
                for media in media_files
            }
            for number, future in enumerate(as_completed(futures), start=1):
                media = futures[future]
                try:
                    results[media] = future.result()
                except Exception as error:
                    results[media] = (thumbs / "missing.jpg", str(error))
                if number % 25 == 0 or number == len(media_files):
                    print(f"thumbnails={number}/{len(media_files)}", flush=True)

    items: list[dict[str, object]] = []
    for media in media_files:
        relative_path = media.relative_to(media_root)
        relative = relative_path.as_posix()
        stat = media.stat()
        thumb, problem = results[media]
        kind = "video" if media.suffix.lower() in VIDEO_EXTENSIONS else "picture"
        encoded_id = "/".join(quote(part, safe="") for part in relative.split("/"))
        items.append(
            {
                "id": relative,
                "name": media.name,
                "folder": "" if relative_path.parent == Path(".") else relative_path.parent.as_posix(),
                "kind": kind,
                "size": stat.st_size,
                "size_label": human_size(stat.st_size),
                "modified": stat.st_mtime,
                "modified_label": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d"),
                "media_url": f"/media/{encoded_id}",
                "thumbnail_url": f"/thumbnail/{encoded_id}?v={thumb.stem}",
                "thumbnail_cache_url": f"/gallery/thumbs/{thumb.name}",
                "viewer_url": f"/gallery/viewer.html?id={quote(relative, safe='')}&kind={kind}",
                "thumbnail_problem": problem,
            }
        )

    generated_at = datetime.now().astimezone().isoformat()
    catalog = {
        "version": 5,
        "generated_at": generated_at,
        "title": title,
        "source_label": source_label,
        "media_mode": media_mode,
        "appearance": appearance,
        "actions": [action.public_dict() for action in actions],
        "items": items,
    }
    config = {
        "version": 5,
        "media_root": str(media_root),
        "gallery_root": str(gallery_root),
        "state_identity": state_identity(media_root, profile),
        "title": title,
        "source_label": source_label,
        "actions": [action.config_dict() for action in actions],
        "keep_structure": keep_structure,
        "history_retention_days": history_retention_days,
        "media_mode": media_mode,
        "appearance": appearance,
        "thumbnail_width": thumbnail_width,
        "thumbnail_policy": thumbnail_policy,
        "workers": max(1, workers),
    }
    counts = {
        "pictures": sum(item["kind"] == "picture" for item in items),
        "videos": sum(item["kind"] == "video" for item in items),
    }

    for asset in ASSET_FILES:
        shutil.copy2(ASSET_ROOT / asset, gallery_root / asset)
    (gallery_root / "catalog.json").write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
    (gallery_root / "gallery-config.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    (gallery_root / "manifest.json").write_text(
        json.dumps(
            {
                "created_at": generated_at,
                "items": len(items),
                **counts,
                "thumbnail_policy": thumbnail_policy,
                "thumbnails_ready": sum(thumb.exists() for thumb, _ in results.values()),
                "thumbnail_failures": sum(bool(item["thumbnail_problem"]) for item in items),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        f"gallery={gallery_root} items={len(items)} pictures={counts['pictures']} "
        f"videos={counts['videos']} thumbnail_failures={sum(bool(item['thumbnail_problem']) for item in items)}"
    )


if __name__ == "__main__":
    main()
