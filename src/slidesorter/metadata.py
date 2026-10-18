"""Extract capture dates without confusing them with filesystem timestamps."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any


_EXIF_IMAGE_KEYS = ("DateTimeOriginal", "CreateDate", "DateTimeDigitized")
_VIDEO_KEYS = (
    "QuickTime:CreateDate",
    "MediaCreateDate",
    "TrackCreateDate",
    "CreateDate",
    "creation_time",
    "com.apple.quicktime.creationdate",
)
_EXIF_OFFSET_KEYS = ("OffsetTimeOriginal", "OffsetTimeDigitized", "OffsetTime")
_DATE_PREFIX = re.compile(r"^(\d{4}):(\d{2}):(\d{2})(.*)$")


def _text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    value = str(value).strip().strip("\x00")
    return value or None


def _parse_datetime(value: Any, offset: Any = None) -> tuple[datetime, str] | None:
    text = _text(value)
    if not text:
        return None
    prefix = _DATE_PREFIX.match(text)
    if prefix:
        text = f"{prefix.group(1)}-{prefix.group(2)}-{prefix.group(3)}{prefix.group(4)}"
    text = text.replace(" UTC", "+00:00").replace("Z", "+00:00")
    if " " in text and "T" not in text:
        text = text.replace(" ", "T", 1)
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        try:
            parsed = datetime.strptime(text[:19], "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            return None
    if parsed.tzinfo is None:
        offset_text = _text(offset)
        if offset_text:
            offset_text = offset_text.replace("Z", "+00:00")
            try:
                offset_value = datetime.fromisoformat(f"2000-01-01T00:00:00{offset_text}").utcoffset()
            except ValueError:
                offset_value = None
            if offset_value is not None:
                parsed = parsed.replace(tzinfo=timezone(offset_value))
    precision = "second" if any(separator in text for separator in ("T", ":")) else "day"
    return parsed, precision


def _candidate(record: dict[str, Any], keys: tuple[str, ...], offsets: tuple[str, ...] = ()) -> tuple[datetime, str] | None:
    offset = next((_text(record.get(key)) for key in offsets if _text(record.get(key))), None)
    for key in keys:
        parsed = _parse_datetime(record.get(key), offset)
        if parsed:
            return parsed
    return None


def _run_json(command: list[str]) -> dict[str, Any] | None:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    try:
        payload = json.loads(completed.stdout)
    except (TypeError, json.JSONDecodeError):
        return None
    if isinstance(payload, list):
        return payload[0] if payload and isinstance(payload[0], dict) else None
    return payload if isinstance(payload, dict) else None


def _exiftool_capture(path: Path, kind: str) -> tuple[datetime, str] | None:
    executable = shutil.which("exiftool")
    if not executable:
        return None
    keys = _EXIF_IMAGE_KEYS if kind == "picture" else _VIDEO_KEYS
    command = [executable, "-j", "-n"]
    command.extend(f"-{key}" for key in (*keys, *_EXIF_OFFSET_KEYS))
    command.append(str(path))
    record = _run_json(command)
    if not record:
        return None
    return _candidate(record, keys, _EXIF_OFFSET_KEYS)


def _pillow_capture(path: Path) -> tuple[datetime, str] | None:
    try:
        from PIL import ExifTags, Image
    except ImportError:
        return None
    try:
        with Image.open(path) as image:
            exif = image.getexif()
            if not exif:
                return None
            names = {ExifTags.TAGS.get(tag, tag): value for tag, value in exif.items()}
    except (OSError, ValueError, SyntaxError, Image.DecompressionBombError):
        return None
    return _candidate(names, _EXIF_IMAGE_KEYS, _EXIF_OFFSET_KEYS)


def _ffprobe_capture(path: Path) -> tuple[datetime, str] | None:
    executable = shutil.which("ffprobe")
    if not executable:
        return None
    payload = _run_json([
        executable,
        "-v", "error",
        "-show_entries", "format_tags:stream_tags",
        "-of", "json",
        str(path),
    ])
    if not payload:
        return None
    records: list[dict[str, Any]] = []
    format_tags = payload.get("format", {}).get("tags") if isinstance(payload.get("format"), dict) else None
    if isinstance(format_tags, dict):
        records.append(format_tags)
    for stream in payload.get("streams", []):
        if isinstance(stream, dict) and isinstance(stream.get("tags"), dict):
            records.append(stream["tags"])
    for record in records:
        normalized = {str(key).casefold(): value for key, value in record.items()}
        for key in ("creation_time", "com.apple.quicktime.creationdate", "date"):
            parsed = _parse_datetime(normalized.get(key))
            if parsed:
                return parsed
    return None


def _timestamp(value: datetime) -> float:
    # A timezone-less camera timestamp is a local wall-clock value. Treating it
    # as UTC keeps catalog ordering stable across machines without changing the
    # displayed camera time.
    return value.replace(tzinfo=value.tzinfo or timezone.utc).timestamp()


def _label(value: datetime, precision: str) -> str:
    return value.strftime("%Y-%m-%d %H:%M" if precision == "second" else "%Y-%m-%d")


def capture_metadata(path: Path, kind: str, modified: float) -> dict[str, object]:
    """Return display and ordering metadata, preferring embedded capture time."""

    candidate = _pillow_capture(path) if kind == "picture" else _ffprobe_capture(path)
    if candidate is None:
        # ExifTool is the broad-format fallback for HEIC, RAW, and unusual
        # camera/video metadata that the lightweight readers cannot decode.
        candidate = _exiftool_capture(path, kind)
    if candidate is not None:
        value, precision = candidate
        return {
            "captured_at": value.isoformat(timespec="seconds"),
            "captured_timestamp": _timestamp(value),
            "capture_source": "embedded",
            "capture_precision": precision,
            "date_label": _label(value, precision),
            "date_title": "Capture date from embedded media metadata",
            "date_sort": _timestamp(value),
        }
    fallback = datetime.fromtimestamp(modified).astimezone()
    return {
        "captured_at": None,
        "captured_timestamp": None,
        "capture_source": "file",
        "capture_precision": None,
        "date_label": fallback.strftime("%Y-%m-%d %H:%M"),
        "date_title": "Capture date unavailable; showing file modification time",
        "date_sort": modified,
    }
