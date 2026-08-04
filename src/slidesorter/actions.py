"""Configurable destination actions and lightweight presentation hints."""

from __future__ import annotations

from dataclasses import dataclass
import re
from pathlib import Path
from typing import Iterable


MAX_ACTIONS = 16
ACTION_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
FINAL_HINT = re.compile(r"^(?P<label>.+?)\s*\((?P<hint>[^()]*)\)\s*$")

ICON_RULES = (
    ("trash", ("trash", "trashcan", "bin", "delete", "discard", "remove")),
    ("tray", ("tray", "stage", "upload", "import", "inbox")),
    ("archive", ("archive", "box", "store", "file away")),
    ("star", ("star", "favorite", "favourite", "best")),
    ("check", ("check", "keep", "approve", "accepted")),
    ("clock", ("clock", "later", "review", "hold", "pending")),
)
TONE_RULES = (
    ("danger", ("red", "danger", "destructive", "trash", "delete", "discard", "remove")),
    ("amber", ("amber", "orange", "yellow", "star", "favorite", "archive")),
    ("blue", ("blue", "review", "later", "hold", "clock")),
    ("mint", ("green", "mint", "stage", "upload", "import", "keep", "approve", "check")),
    ("neutral", ("gray", "grey", "neutral", "plain")),
)
PRESENTATION_WORDS = {
    "glyph", "icon", "color", "colour",
    *(word for _, words in ICON_RULES for word in words),
    *(word for _, words in TONE_RULES for word in words),
}


def _contains(text: str, words: Iterable[str]) -> bool:
    return any(word in text for word in words)


def action_presentation(raw_label: str) -> tuple[str, str, str]:
    """Return display label, built-in icon key, and tone.

    A final parenthetical is treated as a presentation hint only when it contains
    recognized vocabulary. Ordinary labels such as ``Vacation (2018)`` remain
    untouched.
    """

    value = " ".join(raw_label.strip().split())
    match = FINAL_HINT.match(value)
    hint = ""
    display = value
    if match:
        candidate = match.group("hint").casefold()
        if _contains(candidate, PRESENTATION_WORDS):
            display = match.group("label").strip()
            hint = candidate
    semantics = f"{display.casefold()} {hint}"
    icon = next((key for key, words in ICON_RULES if _contains(semantics, words)), "arrow")
    tone = next((key for key, words in TONE_RULES if _contains(semantics, words)), "neutral")
    return display, icon, tone


def resolve_root(media_root: Path, value: object, fallback: str) -> Path:
    path = Path(str(value or fallback)).expanduser()
    if not path.is_absolute():
        path = media_root / path
    return path.resolve()


@dataclass(frozen=True)
class DestinationAction:
    id: str
    label: str
    root: Path

    @classmethod
    def from_raw(cls, media_root: Path, raw: object, index: int) -> "DestinationAction":
        if not isinstance(raw, dict):
            raise ValueError(f"Destination {index + 1} must be an object")
        action_id = str(raw.get("id", "")).strip().casefold()
        label = " ".join(str(raw.get("label", "")).strip().split())
        if not ACTION_ID.fullmatch(action_id):
            raise ValueError(f"Destination {index + 1} has an invalid id")
        if not label or len(label) > 120:
            raise ValueError(f"Destination {index + 1} needs a label of 120 characters or fewer")
        display, _, _ = action_presentation(label)
        if not display:
            raise ValueError(f"Destination {index + 1} needs a visible label")
        return cls(action_id, label, resolve_root(media_root, raw.get("root"), display))

    def config_dict(self) -> dict[str, str]:
        return {"id": self.id, "label": self.label, "root": str(self.root)}

    def public_dict(self) -> dict[str, str]:
        display, icon, tone = action_presentation(self.label)
        return {
            **self.config_dict(),
            "display_label": display,
            "icon": icon,
            "tone": tone,
        }


def validate_actions(media_root: Path, actions: tuple[DestinationAction, ...]) -> None:
    if not media_root.is_dir():
        raise ValueError(f"Root tree is not an existing directory: {media_root}")
    if not actions:
        raise ValueError("Configure at least one destination")
    if len(actions) > MAX_ACTIONS:
        raise ValueError(f"Configure no more than {MAX_ACTIONS} destinations")
    ids = [action.id for action in actions]
    if len(ids) != len(set(ids)):
        raise ValueError("Destination ids must be unique")
    roots = [action.root for action in actions]
    if len(roots) != len(set(roots)):
        raise ValueError("Every destination must use a different folder")
    for action in actions:
        if action.root == media_root or media_root.is_relative_to(action.root):
            raise ValueError(
                f"{action_presentation(action.label)[0]} cannot be the root tree or one of its parents"
            )
    for index, root in enumerate(roots):
        for other in roots[index + 1:]:
            if root.is_relative_to(other) or other.is_relative_to(root):
                raise ValueError("Destination folders cannot contain one another")


def actions_from_raw(media_root: Path, raw_actions: object) -> tuple[DestinationAction, ...]:
    if not isinstance(raw_actions, list):
        raise ValueError("Destinations must be a list")
    actions = tuple(
        DestinationAction.from_raw(media_root, raw, index)
        for index, raw in enumerate(raw_actions)
    )
    validate_actions(media_root, actions)
    return actions


def legacy_actions(
    media_root: Path,
    staged_root: object = None,
    removed_root: object = None,
    staged_name: str = "Staged",
    removed_name: str = "Removed",
) -> tuple[DestinationAction, ...]:
    actions = (
        DestinationAction("stage", "Stage", resolve_root(media_root, staged_root, staged_name)),
        DestinationAction(
            "remove",
            "Remove (use a red trash can glyph)",
            resolve_root(media_root, removed_root, removed_name),
        ),
    )
    validate_actions(media_root, actions)
    return actions
