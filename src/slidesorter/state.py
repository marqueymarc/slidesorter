"""Collection-scoped state paths and compatibility checks for SlideSorter."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import sys


STATE_DIRECTORY_NAME = ".slidesorterstate"
COLLECTION_REGISTRY_NAME = "recent-collections.json"
STATE_IDENTITY_VERSION = 1
DEFAULT_PROFILE = "default"
APPEARANCE_MODES = frozenset({"system", "light", "dark"})
_PROFILE_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")


class StateCompatibilityError(ValueError):
    """A state directory is unsafe to use for the requested collection."""


def platform_state_root() -> Path:
    """Return the parent used only when colocated collection state is unavailable."""

    override = os.environ.get("SLIDESORTER_STATE_DIR")
    if override:
        return Path(override).expanduser()
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "SlideSorter"
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "SlideSorter"
    return Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "slidesorter"


def validate_profile(value: str) -> str:
    profile = value.strip()
    if value != profile or not _PROFILE_PATTERN.fullmatch(profile) or profile in {".", ".."}:
        raise ValueError(
            "Profile must be 1–64 letters, numbers, dots, underscores, or hyphens, and start with a letter or number"
        )
    return profile


def validate_appearance(value: object) -> str:
    """Return a supported persisted appearance choice."""

    appearance = str(value).strip().lower()
    if appearance not in APPEARANCE_MODES:
        raise ValueError("Appearance must be System default, Light, or Dark")
    return appearance


def collection_id(media_root: Path) -> str:
    resolved = media_root.expanduser().resolve()
    digest = hashlib.sha256(str(resolved).encode("utf-8")).hexdigest()[:16]
    return f"collection-{digest}"


def fallback_state_dir(media_root: Path, profile: str) -> Path:
    return platform_state_root() / "collections" / collection_id(media_root) / validate_profile(profile)


def automatic_state_dir(media_root: Path, profile: str) -> Path:
    """Return a colocated state directory or a stable platform-state fallback."""

    resolved_media_root = media_root.expanduser().resolve()
    profile = validate_profile(profile)
    colocated_parent = resolved_media_root / STATE_DIRECTORY_NAME
    try:
        colocated_parent.mkdir(exist_ok=True)
    except OSError:
        return fallback_state_dir(resolved_media_root, profile)
    return colocated_parent / profile


def collection_registry_path() -> Path:
    """Return the small machine-local index used to reopen collections.

    Collection data stays next to its media root.  This registry records only
    canonical root paths and last-opened timestamps so the running gallery can
    offer a collection switcher without making a shared catalog or history.
    """

    return platform_state_root() / COLLECTION_REGISTRY_NAME


def read_collection_registry() -> list[dict[str, str]]:
    """Return valid recently opened collections, newest first."""

    try:
        raw = json.loads(collection_registry_path().read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return []
    if not isinstance(raw, list):
        return []
    collections: list[dict[str, str]] = []
    seen: set[str] = set()
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        root = entry.get("root")
        opened_at = entry.get("opened_at")
        if not isinstance(root, str) or not isinstance(opened_at, str):
            continue
        try:
            resolved = Path(root).expanduser().resolve()
        except (OSError, RuntimeError):
            continue
        if not resolved.is_dir() or str(resolved) in seen:
            continue
        seen.add(str(resolved))
        collections.append({"root": str(resolved), "opened_at": opened_at})
    return sorted(collections, key=lambda entry: entry["opened_at"], reverse=True)


def record_collection(media_root: Path, opened_at: str) -> list[dict[str, str]]:
    """Record an opened collection without storing any collection data globally."""

    resolved = media_root.expanduser().resolve()
    entries = [entry for entry in read_collection_registry() if entry["root"] != str(resolved)]
    entries.insert(0, {"root": str(resolved), "opened_at": opened_at})
    entries = entries[:30]
    path = collection_registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
    return entries


def state_identity(media_root: Path, profile: str) -> dict[str, object]:
    resolved_media_root = media_root.expanduser().resolve()
    return {
        "version": STATE_IDENTITY_VERSION,
        "collection_id": collection_id(resolved_media_root),
        "media_root": str(resolved_media_root),
        "profile": validate_profile(profile),
    }


def ensure_compatible_state(gallery_root: Path, media_root: Path, profile: str) -> None:
    """Reject a state directory that is assigned to a different collection/profile.

    Older configurations have no identity block. They are adopted only when their
    recorded media root matches, preserving their existing settings and history.
    """

    config_path = gallery_root / "gallery-config.json"
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return
    except (OSError, json.JSONDecodeError) as error:
        raise StateCompatibilityError(
            f"State config is unreadable: {config_path}. Choose a new state directory rather than overwriting it."
        ) from error
    if not isinstance(raw, dict):
        raise StateCompatibilityError(
            f"State config is invalid: {config_path}. Choose a new state directory rather than overwriting it."
        )
    try:
        recorded_root = Path(str(raw["media_root"])).expanduser().resolve()
    except (KeyError, OSError, RuntimeError) as error:
        raise StateCompatibilityError(
            f"State config has no usable media root: {config_path}. Choose a new state directory rather than overwriting it."
        ) from error
    requested_root = media_root.expanduser().resolve()
    if recorded_root != requested_root:
        raise StateCompatibilityError(
            f"State directory {gallery_root} belongs to {recorded_root}, not {requested_root}. "
            "Use a different --state-dir or profile."
        )

    identity = raw.get("state_identity")
    if identity is None:
        return
    if not isinstance(identity, dict):
        raise StateCompatibilityError(f"State identity is invalid in {config_path}")
    if identity.get("version") != STATE_IDENTITY_VERSION:
        raise StateCompatibilityError(f"State identity version is unsupported in {config_path}")
    if identity.get("media_root") != str(requested_root):
        raise StateCompatibilityError(f"State identity root does not match {requested_root}")
    if identity.get("collection_id") != collection_id(requested_root):
        raise StateCompatibilityError(f"State identity collection does not match {requested_root}")
    if identity.get("profile") != validate_profile(profile):
        raise StateCompatibilityError(
            f"State directory {gallery_root} is profile {identity.get('profile')!r}, not {profile!r}. "
            "Use the matching profile or a different --state-dir."
        )
