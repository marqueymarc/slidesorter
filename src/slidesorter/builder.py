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
import sys
from urllib.parse import quote


def default_state_root() -> Path:
    override = os.environ.get("SLIDESORTER_STATE_DIR")
    if override:
        return Path(override).expanduser()
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "SlideSorter"
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "SlideSorter"
    return Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "slidesorter"


DEFAULT_GALLERY_ROOT = default_state_root() / "default"
ASSET_ROOT = Path(__file__).with_name("assets")
VIDEO_EXTENSIONS = {".mov", ".mp4", ".m4v", ".avi", ".mts", ".m2ts", ".3gp", ".mkv"}
PICTURE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".heif", ".tif", ".tiff", ".bmp"
}
ASSET_FILES = ("index.html", "app.css", "app.js", "viewer.html", "history.html", "history.js")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--media-root", type=Path, required=True)
    parser.add_argument("--gallery-root", type=Path, default=DEFAULT_GALLERY_ROOT)
    parser.add_argument("--title", default="Media Library")
    parser.add_argument("--source-label", help="Defaults to the media root directory name")
    parser.add_argument("--staged-name", default="Staged", help="Directory name under the media root")
    parser.add_argument("--removed-name", default="Removed", help="Directory name under the media root")
    parser.add_argument("--staged-root", type=Path)
    parser.add_argument("--removed-root", type=Path)
    parser.add_argument("--media-mode", choices=("videos", "pictures", "both"), default="both")
    parser.add_argument("--thumbnail-width", type=int, default=720)
    parser.add_argument("--thumbnail-policy", choices=("lazy", "eager"), default="lazy")
    parser.add_argument("--workers", type=int, default=4)
    return parser.parse_args(argv)


def resolve_action_root(media_root: Path, explicit: Path | None, fallback_name: str) -> Path:
    value = explicit if explicit is not None else Path(fallback_name)
    if not value.is_absolute():
        value = media_root / value
    return value.expanduser().resolve()


def validate_roots(media_root: Path, staged_root: Path, removed_root: Path) -> None:
    if not media_root.is_dir():
        raise SystemExit(f"Media root is not a directory: {media_root}")
    if staged_root == removed_root:
        raise SystemExit("Staged and Removed must be different directories")
    for label, root in (("Staged", staged_root), ("Removed", removed_root)):
        if root == media_root or media_root.is_relative_to(root):
            raise SystemExit(f"{label} cannot be the media root or one of its parents")


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
    gallery_root = args.gallery_root.expanduser().resolve()
    source_label = args.source_label or media_root.name
    staged_root = resolve_action_root(media_root, args.staged_root, args.staged_name)
    removed_root = resolve_action_root(media_root, args.removed_root, args.removed_name)
    validate_roots(media_root, staged_root, removed_root)
    if args.thumbnail_width < 160 or args.thumbnail_width > 2400:
        raise SystemExit("Thumbnail width must be between 160 and 2400 pixels")
    for asset in ASSET_FILES:
        if not (ASSET_ROOT / asset).is_file():
            raise SystemExit(f"Gallery asset is missing: {ASSET_ROOT / asset}")

    gallery_root.mkdir(parents=True, exist_ok=True)
    thumbs = gallery_root / "thumbs"
    thumbs.mkdir(exist_ok=True)
    excluded = tuple(
        root for root in (staged_root, removed_root) if root.is_relative_to(media_root)
    )
    media_files = discover_media(media_root, excluded, selected_extensions(args.media_mode))

    results: dict[Path, tuple[Path, str | None]] = {
        media: (thumbnail_path_for(media, thumbs, args.thumbnail_width), None) for media in media_files
    }
    if args.thumbnail_policy == "eager":
        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
            futures = {
                pool.submit(
                    thumbnail_for,
                    media,
                    thumbs,
                    args.thumbnail_width,
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
        "version": 3,
        "generated_at": generated_at,
        "title": args.title,
        "source_label": source_label,
        "media_mode": args.media_mode,
        "items": items,
    }
    config = {
        "version": 3,
        "media_root": str(media_root),
        "gallery_root": str(gallery_root),
        "title": args.title,
        "source_label": source_label,
        "staged_root": str(staged_root),
        "removed_root": str(removed_root),
        "staged_name": staged_root.name,
        "removed_name": removed_root.name,
        "media_mode": args.media_mode,
        "thumbnail_width": args.thumbnail_width,
        "thumbnail_policy": args.thumbnail_policy,
        "workers": max(1, args.workers),
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
                "thumbnail_policy": args.thumbnail_policy,
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
