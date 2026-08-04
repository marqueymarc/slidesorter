#!/usr/bin/env python3
"""Serve one configured SlideSorter gallery with recoverable file actions."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import threading
from urllib.parse import parse_qs, unquote, urlsplit
from uuid import uuid4

from .actions import (
    DestinationAction,
    action_presentation,
    actions_from_raw,
    legacy_actions,
    validate_actions,
)
from .builder import DEFAULT_GALLERY_ROOT, thumbnail_for


DEFAULT_CONFIG = DEFAULT_GALLERY_ROOT / "gallery-config.json"
VIDEO_EXTENSIONS = {".mov", ".mp4", ".m4v", ".avi", ".mts", ".m2ts", ".3gp", ".mkv"}
PICTURE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".heif", ".tif", ".tiff", ".bmp"
}
MEDIA_EXTENSIONS = VIDEO_EXTENSIONS | PICTURE_EXTENSIONS
MEDIA_MODES = {"videos", "pictures", "both"}
PUBLIC_GALLERY_FILES = {
    "index.html", "app.css", "app.js", "viewer.html", "history.html", "history.js",
    "catalog.json", "manifest.json",
}
DIRECTORY_PROMPTS = {
    "media_root": "Choose the root tree to scan",
    "action_root": "Choose a destination directory",
    "staged_root": "Choose the Stage directory",
    "removed_root": "Choose the Remove directory",
}


def validate_roots(media_root: Path, staged_root: Path, removed_root: Path) -> None:
    """Backward-compatible validator for the original two destinations."""

    validate_actions(
        media_root,
        (
            DestinationAction("stage", "Stage", staged_root),
            DestinationAction("remove", "Remove", removed_root),
        ),
    )


@dataclass(frozen=True)
class GalleryConfig:
    media_root: Path
    gallery_root: Path
    title: str
    source_label: str
    actions: tuple[DestinationAction, ...]
    keep_structure: bool
    media_mode: str
    thumbnail_width: int
    thumbnail_policy: str
    workers: int

    @classmethod
    def load(cls, path: Path) -> "GalleryConfig":
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as error:
            raise SystemExit(f"Gallery config not found: {path}. Run the gallery builder first.") from error
        media_root = Path(raw["media_root"]).expanduser().resolve()
        gallery_root = Path(raw["gallery_root"]).expanduser().resolve()
        try:
            if isinstance(raw.get("actions"), list):
                actions = actions_from_raw(media_root, raw["actions"])
            else:
                actions = legacy_actions(
                    media_root,
                    raw.get("staged_root"),
                    raw.get("removed_root"),
                    str(raw.get("staged_name", "Staged")),
                    str(raw.get("removed_name", "Removed")),
                )
        except ValueError as error:
            raise SystemExit(str(error)) from error
        mode = str(raw.get("media_mode", "videos"))
        if mode not in MEDIA_MODES:
            raise SystemExit(f"Unsupported media mode in config: {mode}")
        thumbnail_policy = str(raw.get("thumbnail_policy", "lazy"))
        if thumbnail_policy not in {"lazy", "eager"}:
            raise SystemExit(f"Unsupported thumbnail policy in config: {thumbnail_policy}")
        if not gallery_root.is_dir():
            raise SystemExit(f"Gallery root is not a directory: {gallery_root}")
        return cls(
            media_root=media_root,
            gallery_root=gallery_root,
            title=str(raw.get("title", "Media gallery")),
            source_label=str(raw.get("source_label", media_root.name)),
            actions=actions,
            keep_structure=bool(raw.get("keep_structure", True)),
            media_mode=mode,
            thumbnail_width=int(raw.get("thumbnail_width", 720)),
            thumbnail_policy=thumbnail_policy,
            workers=max(1, int(raw.get("workers", 4))),
        )

    @classmethod
    def from_settings(cls, current: "GalleryConfig", raw: dict[str, object]) -> "GalleryConfig":
        media_root = Path(str(raw.get("media_root", ""))).expanduser().resolve()
        actions = actions_from_raw(media_root, raw.get("actions"))
        mode = str(raw.get("media_mode", ""))
        if mode not in MEDIA_MODES:
            raise ValueError("Include must be Pictures, Videos, or Both")
        title = str(raw.get("title", "")).strip()
        source_label = str(raw.get("source_label", "")).strip()
        if not title or not source_label:
            raise ValueError("Gallery title and source label are required")
        keep_structure = raw.get("keep_structure", True)
        if not isinstance(keep_structure, bool):
            raise ValueError("Keep directory structure must be on or off")
        return cls(
            media_root=media_root,
            gallery_root=current.gallery_root,
            title=title,
            source_label=source_label,
            actions=actions,
            keep_structure=keep_structure,
            media_mode=mode,
            thumbnail_width=current.thumbnail_width,
            thumbnail_policy=current.thumbnail_policy,
            workers=current.workers,
        )

    @property
    def legacy_path(self) -> str | None:
        try:
            relative = self.gallery_root.relative_to(Path("/Volumes"))
        except ValueError:
            return None
        return "/" + relative.as_posix()

    @property
    def history_path(self) -> Path:
        return self.gallery_root / "action-history.json"

    @property
    def action_roots(self) -> tuple[Path, ...]:
        return tuple(action.root for action in self.actions)

    def action_for_id(self, action_id: object) -> DestinationAction:
        if not isinstance(action_id, str):
            raise ValueError("A destination action is required")
        action = next((candidate for candidate in self.actions if candidate.id == action_id), None)
        if action is None:
            raise ValueError("The selected destination is no longer configured")
        return action

    def public_settings(self) -> dict[str, object]:
        legacy_stage = next(
            (action for action in self.actions if action.id == "stage"),
            self.actions[0],
        )
        legacy_remove = next(
            (action for action in self.actions if action.id == "remove"),
            self.actions[min(1, len(self.actions) - 1)],
        )
        return {
            "media_root": str(self.media_root),
            "actions": [action.public_dict() for action in self.actions],
            "staged_root": str(legacy_stage.root),
            "removed_root": str(legacy_remove.root),
            "keep_structure": self.keep_structure,
            "media_mode": self.media_mode,
            "title": self.title,
            "source_label": self.source_label,
        }

    def rebuild_command(self) -> list[str]:
        return [
            sys.executable, "-m", "slidesorter.builder",
            "--media-root", str(self.media_root),
            "--gallery-root", str(self.gallery_root),
            "--title", self.title,
            "--source-label", self.source_label,
            "--actions-json", json.dumps([action.config_dict() for action in self.actions]),
            "--keep-structure" if self.keep_structure else "--no-keep-structure",
            "--media-mode", self.media_mode,
            "--thumbnail-width", str(self.thumbnail_width),
            "--thumbnail-policy", self.thumbnail_policy,
            "--workers", str(self.workers),
        ]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    return parser.parse_args(argv)


def safe_relative(value: str) -> PurePosixPath:
    normalized = value.replace("\\", "/")
    relative = PurePosixPath(normalized)
    if not normalized or relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
        raise ValueError("Invalid relative path")
    return relative


def inside(root: Path, relative: PurePosixPath) -> Path:
    candidate = (root / Path(*relative.parts)).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise ValueError("Path is outside the configured root") from error
    return candidate


def read_history(config: GalleryConfig) -> list[dict[str, object]]:
    try:
        payload = json.loads(config.history_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    except json.JSONDecodeError as error:
        raise RuntimeError("The move history file is damaged") from error
    if not isinstance(payload, list):
        raise RuntimeError("The move history file has an invalid format")
    return [entry for entry in payload if isinstance(entry, dict)]


def write_history(config: GalleryConfig, entries: list[dict[str, object]]) -> None:
    temporary = config.history_path.with_suffix(".json.tmp")
    cutoff = max(0, len(entries) - 500)
    retained = [
        entry for index, entry in enumerate(entries)
        if index >= cutoff or entry.get("status") in {"planned", "moved"}
    ]
    temporary.write_text(json.dumps(retained, indent=2) + "\n", encoding="utf-8")
    temporary.replace(config.history_path)


def existing_history_media(entry: dict[str, object]) -> Path | None:
    roots_and_values = (
        (entry.get("media_root"), entry.get("source")),
        (entry.get("action_root"), entry.get("destination")),
    )
    for root_value, path_value in roots_and_values:
        if not root_value or not path_value:
            continue
        root = Path(str(root_value)).resolve()
        candidate = Path(str(path_value)).resolve()
        if (
            candidate.suffix.lower() in MEDIA_EXTENSIONS
            and candidate.is_file()
            and candidate.is_relative_to(root)
        ):
            return candidate
    return None


def load_catalog(config: GalleryConfig) -> dict[str, object]:
    try:
        catalog = json.loads((config.gallery_root / "catalog.json").read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as error:
        raise RuntimeError("The media catalog is missing or damaged") from error
    if not isinstance(catalog, dict) or not isinstance(catalog.get("items"), list):
        raise RuntimeError("The media catalog has an invalid format")
    return catalog


def backfill_history_thumbnails(config: GalleryConfig) -> int:
    entries = read_history(config)
    changed = 0
    for entry in entries:
        if not entry.get("entry_id"):
            entry["entry_id"] = uuid4().hex
            changed += 1
        if entry.get("thumbnail_url"):
            continue
        media = existing_history_media(entry)
        if media is None or media.suffix.lower() not in MEDIA_EXTENSIONS:
            continue
        kind = "video" if media.suffix.lower() in VIDEO_EXTENSIONS else "picture"
        thumb, problem = thumbnail_for(
            media, config.gallery_root / "thumbs", config.thumbnail_width, kind
        )
        if not problem and thumb.is_file():
            entry["thumbnail_url"] = f"/gallery/thumbs/{thumb.name}"
            changed += 1
    if changed:
        write_history(config, entries)
    return changed


def display_time(value: object) -> str:
    try:
        return datetime.fromisoformat(str(value)).astimezone().strftime("%b %-d, %Y at %-I:%M %p")
    except (ValueError, TypeError):
        return ""


class GalleryHandler(SimpleHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "SlideSorter/4"

    @property
    def config(self) -> GalleryConfig:
        return self.server.gallery_config  # type: ignore[attr-defined]

    @property
    def config_path(self) -> Path:
        return self.server.config_path  # type: ignore[attr-defined]

    @property
    def gallery_lock(self) -> threading.RLock:
        return self.server.gallery_lock  # type: ignore[attr-defined]

    @property
    def thumbnail_lock(self) -> threading.RLock:
        return self.server.thumbnail_lock  # type: ignore[attr-defined]

    @property
    def catalog(self) -> dict[str, object]:
        return self.server.catalog  # type: ignore[attr-defined]

    def end_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        super().end_headers()

    def redirect(self, location: str) -> None:
        self.send_response(HTTPStatus.FOUND)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def request_file(self) -> tuple[Path, bool] | None:
        request_path = unquote(urlsplit(self.path).path)
        legacy = self.config.legacy_path
        if request_path == "/":
            self.redirect("/gallery/")
            return None
        if legacy and request_path.rstrip("/") == legacy:
            self.redirect("/gallery/")
            return None
        if request_path.startswith("/api/history-media/"):
            entry_id = request_path.removeprefix("/api/history-media/")
            return self.history_media_path(entry_id), True
        if request_path in {"/gallery", "/gallery/"}:
            return self.config.gallery_root / "index.html", False
        if request_path.startswith("/gallery/"):
            relative = safe_relative(request_path.removeprefix("/gallery/"))
            is_thumbnail = len(relative.parts) == 2 and relative.parts[0] == "thumbs" and relative.suffix.lower() == ".jpg"
            if not (len(relative.parts) == 1 and relative.name in PUBLIC_GALLERY_FILES) and not is_thumbnail:
                raise ValueError("This gallery asset is private")
            return inside(self.config.gallery_root, relative), False
        if request_path.startswith("/thumbnail/"):
            relative = safe_relative(request_path.removeprefix("/thumbnail/"))
            source = inside(self.config.media_root, relative)
            if source.suffix.lower() not in MEDIA_EXTENSIONS or not source.is_file():
                raise ValueError("Thumbnail source is not an existing media file")
            for action_root in self.config.action_roots:
                if action_root.is_relative_to(self.config.media_root) and source.is_relative_to(action_root):
                    raise ValueError("Destination thumbnails are private")
            kind = "video" if source.suffix.lower() in VIDEO_EXTENSIONS else "picture"
            with self.thumbnail_lock:
                thumb, problem = thumbnail_for(
                    source, self.config.gallery_root / "thumbs", self.config.thumbnail_width, kind
                )
            if problem or not thumb.is_file():
                raise FileNotFoundError
            return thumb, False
        if request_path.startswith("/media/"):
            relative = safe_relative(request_path.removeprefix("/media/"))
            media = inside(self.config.media_root, relative)
            if media.suffix.lower() not in MEDIA_EXTENSIONS:
                raise ValueError("Only configured media files can be served")
            for action_root in self.config.action_roots:
                if action_root.is_relative_to(self.config.media_root) and media.is_relative_to(action_root):
                    raise ValueError("Destination files are not exposed by this gallery")
            return media, True
        raise FileNotFoundError

    def send_head(self):
        self.byte_range: tuple[int, int] | None = None
        try:
            resolved = self.request_file()
            if resolved is None:
                return None
            path, is_media = resolved
            if not path.is_file():
                raise FileNotFoundError
            source = path.open("rb")
        except (FileNotFoundError, ValueError, OSError):
            self.send_error(HTTPStatus.NOT_FOUND, "File not found")
            return None
        stat = path.stat()
        size = stat.st_size
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        request_range = self.headers.get("Range") if is_media else None
        if request_range:
            try:
                start, end = self.parse_range(request_range, size)
            except ValueError:
                source.close()
                self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                self.send_header("Content-Range", f"bytes */{size}")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return None
            self.byte_range = (start, end)
            self.send_response(HTTPStatus.PARTIAL_CONTENT)
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.send_header("Content-Length", str(end - start + 1))
        else:
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Length", str(size))
        self.send_header("Content-Type", content_type)
        self.send_header("Last-Modified", self.date_time_string(stat.st_mtime))
        if is_media:
            self.send_header("Accept-Ranges", "bytes")
        if path.name in {"catalog.json", "gallery-config.json", "manifest.json", "action-history.json"}:
            self.send_header("Cache-Control", "no-store")
        elif path.parent == self.config.gallery_root and path.name in PUBLIC_GALLERY_FILES:
            self.send_header("Cache-Control", "no-cache")
        elif path.parent.name == "thumbs" and path.suffix.lower() == ".jpg":
            self.send_header("Cache-Control", "public, max-age=31536000, immutable")
        self.end_headers()
        return source

    @staticmethod
    def parse_range(header: str, size: int) -> tuple[int, int]:
        if not header.startswith("bytes=") or "," in header or size <= 0:
            raise ValueError
        start_text, end_text = header[6:].split("-", 1)
        if start_text:
            start = int(start_text)
            end = int(end_text) if end_text else size - 1
        else:
            length = int(end_text)
            if length <= 0:
                raise ValueError
            start = max(0, size - length)
            end = size - 1
        if start < 0 or start >= size or end < start:
            raise ValueError
        return start, min(end, size - 1)

    def copyfile(self, source, outputfile) -> None:
        if self.byte_range is None:
            try:
                shutil.copyfileobj(source, outputfile)
            except (BrokenPipeError, ConnectionResetError):
                pass
            return
        start, end = self.byte_range
        source.seek(start)
        remaining = end - start + 1
        while remaining:
            chunk = source.read(min(128 * 1024, remaining))
            if not chunk:
                break
            try:
                outputfile.write(chunk)
            except (BrokenPipeError, ConnectionResetError):
                break
            remaining -= len(chunk)

    def respond_json(self, status: HTTPStatus, payload: dict[str, object]) -> None:
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)

    def read_json_body(self, allow_empty: bool = False, max_length: int = 64 * 1024) -> dict[str, object]:
        length = int(self.headers.get("Content-Length", "0"))
        if allow_empty and length == 0:
            return {}
        if length <= 0 or length > max_length:
            raise ValueError("Invalid request body")
        body = json.loads(self.rfile.read(length))
        if not isinstance(body, dict):
            raise ValueError("Request body must be an object")
        return body

    def source_from_id(self, value: object) -> tuple[Path, PurePosixPath]:
        if not isinstance(value, str):
            raise ValueError("A relative media id is required")
        relative = safe_relative(value)
        source = inside(self.config.media_root, relative)
        for action_root in self.config.action_roots:
            if action_root.is_relative_to(self.config.media_root) and source.is_relative_to(action_root):
                raise ValueError("Items already inside a destination cannot be acted on here")
        if source.suffix.lower() not in MEDIA_EXTENSIONS or not source.is_file():
            raise ValueError("The requested source is not an existing picture or video")
        return source, relative

    def run_rebuild(self, config: GalleryConfig) -> tuple[bool, str]:
        rebuilt = subprocess.run(config.rebuild_command(), capture_output=True, text=True, timeout=900)
        message = rebuilt.stderr.strip() or rebuilt.stdout.strip()
        return rebuilt.returncode == 0, message

    def reload_runtime(self) -> None:
        config = GalleryConfig.load(self.config_path)
        catalog = load_catalog(config)
        self.server.gallery_config = config  # type: ignore[attr-defined]
        self.server.catalog = catalog  # type: ignore[attr-defined]

    def history_payload(self, limit: int = 200) -> dict[str, object]:
        entries = list(reversed(read_history(self.config)))[:limit]
        public_entries = []
        for entry in entries:
            public = dict(entry)
            public["created_label"] = display_time(entry.get("created_at"))
            public["undone_label"] = display_time(entry.get("undone_at"))
            public["kind"] = "video" if Path(str(entry.get("name", ""))).suffix.lower() in VIDEO_EXTENSIONS else "picture"
            public["media_url"] = f"/api/history-media/{entry.get('entry_id', '')}"
            fallback_label = "Remove" if entry.get("action") == "remove" else "Stage"
            label = str(entry.get("action_label", fallback_label))
            display, icon, tone = action_presentation(label)
            public["action_label"] = display
            public["action_icon"] = str(entry.get("action_icon", icon))
            public["action_tone"] = str(entry.get("action_tone", tone))
            public_entries.append(public)
        return {
            "entries": public_entries,
            "can_undo": any(entry.get("status") == "moved" for entry in read_history(self.config)),
        }

    def history_media_path(self, entry_id: str) -> Path:
        if not entry_id or not all(character.isalnum() for character in entry_id):
            raise ValueError("Invalid history media")
        with self.gallery_lock:
            entry = next(
                (candidate for candidate in read_history(self.config) if candidate.get("entry_id") == entry_id),
                None,
            )
            if entry is None:
                raise ValueError("History media not found")
            candidate = existing_history_media(entry)
            if candidate is not None:
                return candidate
        raise ValueError("History media is no longer available")

    def ordered_catalog_items(self, query: str, kind: str, sort: str) -> list[dict[str, object]]:
        query = query.strip().casefold()[:500]
        if kind not in {"both", "picture", "video"}:
            raise ValueError("Unknown media type filter")
        if sort not in {"oldest", "newest", "name", "size"}:
            raise ValueError("Unknown catalog sort")
        all_items = [item for item in self.catalog["items"] if isinstance(item, dict)]  # type: ignore[index]
        filtered = [
            item for item in all_items
            if (kind == "both" or item.get("kind") == kind)
            and (
                not query
                or query in f"{item.get('name', '')} {item.get('folder', '')}".casefold()
            )
        ]
        if sort == "newest":
            filtered.sort(key=lambda item: (-float(item.get("modified", 0)), str(item.get("id", "")).casefold()))
        elif sort == "name":
            filtered.sort(key=lambda item: str(item.get("name", "")).casefold())
        elif sort == "size":
            filtered.sort(key=lambda item: (-int(item.get("size", 0)), str(item.get("id", "")).casefold()))
        else:
            filtered.sort(key=lambda item: (float(item.get("modified", 0)), str(item.get("id", "")).casefold()))
        return filtered

    def catalog_payload(self, query_string: str) -> dict[str, object]:
        parameters = parse_qs(query_string)
        page = max(1, int(parameters.get("page", ["1"])[0]))
        page_size = max(25, min(500, int(parameters.get("page_size", ["100"])[0])))
        query = parameters.get("query", [""])[0]
        kind = parameters.get("kind", ["both"])[0]
        sort = parameters.get("sort", ["oldest"])[0]
        all_items = [item for item in self.catalog["items"] if isinstance(item, dict)]  # type: ignore[index]
        pictures = sum(item.get("kind") == "picture" for item in all_items)
        filtered = self.ordered_catalog_items(query, kind, sort)
        pages = max(1, (len(filtered) + page_size - 1) // page_size)
        page = min(page, pages)
        start = (page - 1) * page_size
        return {
            "version": self.catalog.get("version", 3),
            "title": self.catalog.get("title", self.config.title),
            "source_label": self.catalog.get("source_label", self.config.source_label),
            "media_mode": self.catalog.get("media_mode", self.config.media_mode),
            "actions": [action.public_dict() for action in self.config.actions],
            "keep_structure": self.config.keep_structure,
            "total": len(all_items),
            "filtered_total": len(filtered),
            "pictures": pictures,
            "videos": len(all_items) - pictures,
            "page": page,
            "page_size": page_size,
            "pages": pages,
            "items": filtered[start:start + page_size],
        }

    def catalog_range(self, body: dict[str, object]) -> None:
        anchor = body.get("anchor")
        target = body.get("target")
        if not isinstance(anchor, str) or not isinstance(target, str):
            raise ValueError("Range endpoints are required")
        ordered = self.ordered_catalog_items(
            str(body.get("query", "")), str(body.get("kind", "both")), str(body.get("sort", "oldest"))
        )
        positions = {item.get("id"): index for index, item in enumerate(ordered)}
        if anchor not in positions or target not in positions:
            raise ValueError("The range anchor is not in the current results")
        start, end = sorted((positions[anchor], positions[target]))
        if end - start + 1 > 50_000:
            raise ValueError("A selection range is limited to 50,000 items")
        ranged = ordered[start:end + 1]
        ids = [str(item["id"]) for item in ranged]
        selection_query = str(body.get("selection_query", "")).strip().casefold()[:500]
        selection_kind = str(body.get("selection_kind", "both"))
        if selection_kind not in {"both", "picture", "video"}:
            raise ValueError("Unknown selection type filter")
        matching_selection_ids = [
            str(item["id"])
            for item in ranged
            if (selection_kind == "both" or item.get("kind") == selection_kind)
            and (
                not selection_query
                or selection_query in f"{item.get('name', '')} {item.get('folder', '')}".casefold()
            )
        ]
        self.respond_json(
            HTTPStatus.OK,
            {"ids": ids, "count": len(ids), "matching_selection_ids": matching_selection_ids},
        )

    def do_GET(self) -> None:
        parsed = urlsplit(self.path)
        try:
            if parsed.path.startswith("/api/history-thumbnail/"):
                self.serve_history_thumbnail(parsed.path.removeprefix("/api/history-thumbnail/"))
                return
            if parsed.path == "/api/settings":
                self.respond_json(HTTPStatus.OK, self.config.public_settings())
                return
            if parsed.path == "/api/history":
                raw_limit = parse_qs(parsed.query).get("limit", ["200"])[0]
                limit = max(1, min(500, int(raw_limit)))
                self.respond_json(HTTPStatus.OK, self.history_payload(limit))
                return
            if parsed.path == "/api/catalog":
                self.respond_json(HTTPStatus.OK, self.catalog_payload(parsed.query))
                return
        except (ValueError, RuntimeError) as error:
            self.respond_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
            return
        super().do_GET()

    def serve_history_thumbnail(self, entry_id: str) -> None:
        if not entry_id or not all(character.isalnum() for character in entry_id):
            raise ValueError("Invalid history thumbnail")
        with self.gallery_lock:
            history = read_history(self.config)
            entry = next((candidate for candidate in history if candidate.get("entry_id") == entry_id), None)
            if entry is None:
                raise ValueError("History thumbnail not found")
            existing = entry.get("thumbnail_url")
            if isinstance(existing, str) and existing.startswith("/gallery/thumbs/"):
                self.redirect(existing)
                return
            media = existing_history_media(entry)
            if media is None or media.suffix.lower() not in MEDIA_EXTENSIONS:
                raise ValueError("History media is no longer available")
            kind = "video" if media.suffix.lower() in VIDEO_EXTENSIONS else "picture"
            with self.thumbnail_lock:
                thumb, problem = thumbnail_for(
                    media, self.config.gallery_root / "thumbs", self.config.thumbnail_width, kind
                )
            if problem or not thumb.is_file():
                raise ValueError("Could not create the history thumbnail")
            static_url = f"/gallery/thumbs/{thumb.name}"
            entry["thumbnail_url"] = static_url
            write_history(self.config, history)
            self.redirect(static_url)

    def do_POST(self) -> None:
        action = urlsplit(self.path).path
        allowed = {
            "/api/reveal", "/api/move", "/api/bulk-move", "/api/refresh",
            "/api/remove", "/api/stage", "/api/bulk-stage", "/api/bulk-remove",
            "/api/settings", "/api/undo", "/api/choose-directory",
            "/api/catalog-range",
        }
        if action not in allowed:
            self.respond_json(HTTPStatus.NOT_FOUND, {"error": "Unknown action"})
            return
        try:
            if action == "/api/choose-directory":
                self.choose_directory(self.read_json_body())
                return
            if action == "/api/reveal":
                source, _ = self.source_from_id(self.read_json_body().get("id"))
                self.reveal_media(source)
                self.respond_json(HTTPStatus.OK, {"revealed": str(source)})
                return
            if action == "/api/catalog-range":
                self.catalog_range(self.read_json_body())
                return
            with self.gallery_lock:
                if action == "/api/settings":
                    self.save_settings(self.read_json_body())
                elif action == "/api/refresh":
                    self.refresh_gallery()
                elif action == "/api/undo":
                    self.undo_move(self.read_json_body(allow_empty=True))
                elif action in {"/api/bulk-move", "/api/bulk-stage", "/api/bulk-remove"}:
                    body = self.read_json_body(max_length=8 * 1024 * 1024)
                    if action != "/api/bulk-move":
                        body["action_id"] = "remove" if action == "/api/bulk-remove" else "stage"
                    self.bulk_move(body)
                else:
                    body = self.read_json_body()
                    if action != "/api/move":
                        body["action_id"] = "remove" if action == "/api/remove" else "stage"
                    self.move_media(body)
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
            self.respond_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
        except subprocess.TimeoutExpired:
            self.respond_json(HTTPStatus.GATEWAY_TIMEOUT, {"error": "The gallery rebuild took too long"})
        except Exception as error:
            self.respond_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(error)})

    @staticmethod
    def reveal_media(source: Path) -> None:
        if sys.platform == "darwin":
            command = ["/usr/bin/open", "-R", str(source)]
        elif os.name == "nt":
            command = ["explorer", "/select,", str(source)]
        else:
            opener = shutil.which("xdg-open")
            if not opener:
                raise RuntimeError("Finder reveal is unavailable on this system")
            command = [opener, str(source.parent)]
        subprocess.run(command, check=True)

    def choose_directory(self, body: dict[str, object]) -> None:
        field = str(body.get("field", ""))
        if field not in DIRECTORY_PROMPTS:
            raise ValueError("Unknown directory setting")
        if sys.platform != "darwin":
            raise ValueError("The folder picker is macOS-only; enter the path directly")
        script = f'POSIX path of (choose folder with prompt "{DIRECTORY_PROMPTS[field]}")'
        chosen = subprocess.run(["/usr/bin/osascript", "-e", script], capture_output=True, text=True)
        if chosen.returncode != 0:
            self.respond_json(HTTPStatus.BAD_REQUEST, {"error": "No folder selected"})
            return
        path = chosen.stdout.strip()
        if path != "/":
            path = path.rstrip("/")
        self.respond_json(HTTPStatus.OK, {"path": path})

    def save_settings(self, body: dict[str, object]) -> None:
        new_config = GalleryConfig.from_settings(self.config, body)
        succeeded, detail = self.run_rebuild(new_config)
        if not succeeded:
            raise RuntimeError(detail or "The catalog rebuild failed; settings were not changed")
        self.reload_runtime()
        self.respond_json(HTTPStatus.OK, self.config.public_settings())

    def refresh_gallery(self) -> None:
        succeeded, detail = self.run_rebuild(self.config)
        if not succeeded:
            raise RuntimeError(detail or "Catalog rebuild failed")
        self.reload_runtime()
        self.respond_json(HTTPStatus.OK, {"gallery_refreshed": True})

    def destination_for(
        self,
        action: DestinationAction,
        source: Path,
        relative: PurePosixPath,
    ) -> Path:
        destination_relative = relative if self.config.keep_structure else PurePosixPath(source.name)
        return inside(action.root, destination_relative)

    def move_media(self, body: dict[str, object]) -> None:
        action = self.config.action_for_id(body.get("action_id"))
        source, relative = self.source_from_id(body.get("id"))
        destination = self.destination_for(action, source, relative)
        if destination.exists():
            raise ValueError(f"A file named {destination.name} already exists in {action.root}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        kind = "video" if source.suffix.lower() in VIDEO_EXTENSIONS else "picture"
        with self.thumbnail_lock:
            thumb, thumbnail_problem = thumbnail_for(
                source, self.config.gallery_root / "thumbs", self.config.thumbnail_width, kind
            )
        thumbnail_url = f"/gallery/thumbs/{thumb.name}" if not thumbnail_problem and thumb.is_file() else None
        now = datetime.now().astimezone().isoformat()
        display_label, icon, tone = action_presentation(action.label)
        entry: dict[str, object] = {
            "entry_id": uuid4().hex,
            "token": uuid4().hex,
            "action": action.id,
            "action_label": display_label,
            "action_icon": icon,
            "action_tone": tone,
            "name": source.name,
            "relative": relative.as_posix(),
            "source": str(source),
            "destination": str(destination),
            "media_root": str(self.config.media_root),
            "action_root": str(action.root),
            "created_at": now,
            "status": "planned",
            "thumbnail_url": thumbnail_url,
        }
        history = read_history(self.config)
        history.append(entry)
        write_history(self.config, history)
        try:
            shutil.move(str(source), str(destination))
        except Exception:
            entry["status"] = "failed"
            write_history(self.config, history)
            raise
        entry["status"] = "moved"
        write_history(self.config, history)
        succeeded, _ = self.run_rebuild(self.config)
        if succeeded:
            self.reload_runtime()
        else:
            self.catalog["items"] = [
                item for item in self.catalog["items"]  # type: ignore[index]
                if not isinstance(item, dict) or item.get("id") != relative.as_posix()
            ]
        payload: dict[str, object] = {
            "token": entry["token"], "name": source.name, "moved_to": str(destination),
            "destination_label": display_label,
            "gallery_refreshed": succeeded, "thumbnail_url": thumbnail_url,
        }
        if not succeeded:
            payload["warning"] = "The file was moved and can be undone, but the catalog refresh failed."
        self.respond_json(HTTPStatus.OK, payload)

    def resolve_bulk_items(self, body: dict[str, object]) -> list[dict[str, object]]:
        selection = body.get("selection")
        if not isinstance(selection, dict):
            raise ValueError("Bulk selection is missing")
        mode = selection.get("mode")
        catalog_items = [item for item in self.catalog["items"] if isinstance(item, dict)]  # type: ignore[index]
        if mode == "ids":
            raw_ids = selection.get("ids")
            if not isinstance(raw_ids, list) or not all(isinstance(item_id, str) for item_id in raw_ids):
                raise ValueError("Selected media ids are invalid")
            ids = set(raw_ids)
            if len(ids) > 50_000:
                raise ValueError("A bulk operation is limited to 50,000 items")
            items = [item for item in catalog_items if item.get("id") in ids]
        elif mode == "all":
            query = str(selection.get("query", "")).strip().casefold()[:500]
            kind = str(selection.get("kind", "both"))
            if kind not in {"both", "picture", "video"}:
                raise ValueError("Unknown media type filter")
            raw_excluded = selection.get("excluded", [])
            if not isinstance(raw_excluded, list) or not all(isinstance(item_id, str) for item_id in raw_excluded):
                raise ValueError("Selection exclusions are invalid")
            excluded = set(raw_excluded)
            raw_included = selection.get("included", [])
            if not isinstance(raw_included, list) or not all(isinstance(item_id, str) for item_id in raw_included):
                raise ValueError("Additional selected ids are invalid")
            included = set(raw_included)
            items = [
                item for item in catalog_items
                if item.get("id") in included
                or (
                    item.get("id") not in excluded
                    and (kind == "both" or item.get("kind") == kind)
                    and (
                        not query
                        or query in f"{item.get('name', '')} {item.get('folder', '')}".casefold()
                    )
                )
            ]
        else:
            raise ValueError("Unknown bulk selection mode")
        if not items:
            raise ValueError("No media is selected")
        if len(items) > 50_000:
            raise ValueError("A bulk operation is limited to 50,000 items")
        return items

    def bulk_move(self, body: dict[str, object]) -> None:
        action = self.config.action_for_id(body.get("action_id"))
        items = self.resolve_bulk_items(body)
        prepared: list[tuple[Path, Path, PurePosixPath, dict[str, object]]] = []
        for item in items:
            source, relative = self.source_from_id(item.get("id"))
            destination = self.destination_for(action, source, relative)
            if destination.exists():
                raise ValueError(f"A file with this preserved path already exists: {destination}")
            prepared.append((source, destination, relative, item))

        destination_paths = [destination for _, destination, _, _ in prepared]
        if len(destination_paths) != len(set(destination_paths)):
            raise ValueError(
                "This selection contains duplicate filenames. Enable Keep directory structure or move smaller groups."
            )

        token = uuid4().hex
        now = datetime.now().astimezone().isoformat()
        history = read_history(self.config)
        entries: list[dict[str, object]] = []
        display_label, icon, tone = action_presentation(action.label)
        for source, destination, relative, _ in prepared:
            entry_id = uuid4().hex
            entry: dict[str, object] = {
                "entry_id": entry_id,
                "token": token,
                "batch_size": len(prepared),
                "action": action.id,
                "action_label": display_label,
                "action_icon": icon,
                "action_tone": tone,
                "name": source.name,
                "relative": relative.as_posix(),
                "source": str(source),
                "destination": str(destination),
                "media_root": str(self.config.media_root),
                "action_root": str(action.root),
                "created_at": now,
                "status": "planned",
                "thumbnail_url": f"/api/history-thumbnail/{entry_id}",
            }
            entries.append(entry)
        history.extend(entries)
        write_history(self.config, history)

        moved = 0
        failure: str | None = None
        for index, ((source, destination, _, _), entry) in enumerate(zip(prepared, entries)):
            try:
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(source), str(destination))
                entry["status"] = "moved"
                moved += 1
                if moved % 25 == 0:
                    write_history(self.config, history)
            except Exception as error:
                entry["status"] = "failed"
                failure = str(error)
                for remaining in entries[index + 1:]:
                    remaining["status"] = "failed"
                break
        write_history(self.config, history)
        if moved == 0:
            raise RuntimeError(failure or "The bulk move failed before moving any media")

        succeeded, _ = self.run_rebuild(self.config)
        if succeeded:
            self.reload_runtime()
        else:
            moved_ids = {entry["relative"] for entry in entries if entry.get("status") == "moved"}
            self.catalog["items"] = [
                item for item in self.catalog["items"]  # type: ignore[index]
                if not isinstance(item, dict) or item.get("id") not in moved_ids
            ]
        payload: dict[str, object] = {
            "token": token,
            "count": moved,
            "requested": len(prepared),
            "destination": str(action.root),
            "destination_label": display_label,
            "gallery_refreshed": succeeded,
            "thumbnail_url": entries[0]["thumbnail_url"],
        }
        if failure:
            payload["warning"] = f"Moved {moved} of {len(prepared)} items. Undo will restore those moved. {failure}"
        elif not succeeded:
            payload["warning"] = f"Moved {moved} items, but the catalog refresh failed. The batch can still be undone."
        self.respond_json(HTTPStatus.OK, payload)

    def undo_move(self, body: dict[str, object]) -> None:
        history = read_history(self.config)
        token = body.get("token")
        latest = next(
            (
                candidate for candidate in reversed(history)
                if candidate.get("status") == "moved" and (token is None or candidate.get("token") == token)
            ),
            None,
        )
        if latest is None:
            raise ValueError("There is no available move to undo")
        selected_token = latest.get("token")
        entries = [
            entry for entry in history
            if entry.get("status") == "moved" and entry.get("token") == selected_token
        ]
        prepared: list[tuple[Path, Path, dict[str, object]]] = []
        for entry in entries:
            source = Path(str(entry["source"])).resolve()
            destination = Path(str(entry["destination"])).resolve()
            media_root = Path(str(entry["media_root"])).resolve()
            action_root = Path(str(entry["action_root"])).resolve()
            if not source.is_relative_to(media_root) or not destination.is_relative_to(action_root):
                raise ValueError("A history entry failed its path safety check")
            if source.suffix.lower() not in MEDIA_EXTENSIONS or destination.suffix.lower() not in MEDIA_EXTENSIONS:
                raise ValueError("A history entry is not a supported media file")
            if not destination.is_file():
                raise ValueError(f"The moved file is no longer present: {destination.name}")
            if source.exists():
                raise ValueError(f"Undo will not overwrite the occupied original path: {source}")
            prepared.append((source, destination, entry))

        now = datetime.now().astimezone().isoformat()
        restored = 0
        failure: str | None = None
        for source, destination, entry in reversed(prepared):
            try:
                source.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(destination), str(source))
                entry["status"] = "undone"
                entry["undone_at"] = now
                restored += 1
                if restored % 25 == 0:
                    write_history(self.config, history)
            except Exception as error:
                failure = str(error)
                break
        write_history(self.config, history)
        succeeded, _ = self.run_rebuild(self.config)
        if succeeded:
            self.reload_runtime()
        first_entry = entries[0]
        payload: dict[str, object] = {
            "name": first_entry.get("name") if len(entries) == 1 else f"{restored} items",
            "count": restored,
            "gallery_refreshed": succeeded,
            "thumbnail_url": first_entry.get("thumbnail_url"),
        }
        if failure:
            payload["warning"] = f"Restored {restored} of {len(entries)} items. {failure}"
        elif not succeeded:
            payload["warning"] = "The file was restored, but the catalog refresh failed."
        self.respond_json(HTTPStatus.OK, payload)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    config_path = args.config.expanduser().resolve()
    config = GalleryConfig.load(config_path)
    backfill_history_thumbnails(config)
    server = ThreadingHTTPServer((args.host, args.port), GalleryHandler)
    server.gallery_config = config  # type: ignore[attr-defined]
    server.config_path = config_path  # type: ignore[attr-defined]
    server.gallery_lock = threading.RLock()  # type: ignore[attr-defined]
    server.thumbnail_lock = threading.RLock()  # type: ignore[attr-defined]
    server.catalog = load_catalog(config)  # type: ignore[attr-defined]
    print(f"Serving {config.title} at http://{args.host}:{args.port}/gallery/", flush=True)
    print(f"Media root: {config.media_root}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nSlideSorter stopped.", flush=True)
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
