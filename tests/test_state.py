import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from slidesorter.state import (
    DEFAULT_PROFILE,
    StateCompatibilityError,
    automatic_state_dir,
    collection_id,
    collection_registry_path,
    ensure_compatible_state,
    fallback_state_dir,
    read_collection_registry,
    record_collection,
    state_identity,
    validate_profile,
)


class StatePathTests(unittest.TestCase):
    def test_writable_collection_uses_hidden_profile_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            media = Path(temporary) / "media"
            media.mkdir()

            self.assertEqual(
                automatic_state_dir(media, "triage"),
                media.resolve() / ".slidesorterstate" / "triage",
            )

    def test_fallback_is_stable_and_collection_specific(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = root / "first"
            second = root / "second"
            first.mkdir()
            second.mkdir()
            with patch("slidesorter.state.Path.mkdir", side_effect=PermissionError):
                self.assertEqual(
                    automatic_state_dir(first, DEFAULT_PROFILE),
                    fallback_state_dir(first, DEFAULT_PROFILE),
                )
            self.assertEqual(collection_id(first), collection_id(first))
            self.assertNotEqual(collection_id(first), collection_id(second))

    def test_profile_requires_a_safe_child_name(self):
        for invalid in ("", "../other", "review/again", ".", " space", "name with spaces"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                validate_profile(invalid)
        self.assertEqual(validate_profile("Review_2026-08"), "Review_2026-08")

    def test_recent_collection_registry_tracks_paths_not_collection_contents(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = root / "first"
            second = root / "second"
            first.mkdir()
            second.mkdir()
            with patch.dict(os.environ, {"SLIDESORTER_STATE_DIR": str(root / "app-state")}, clear=False):
                record_collection(first, "2026-08-05T10:00:00+00:00")
                record_collection(second, "2026-08-05T11:00:00+00:00")
                entries = read_collection_registry()
                raw = json.loads(collection_registry_path().read_text())

            self.assertEqual([entry["root"] for entry in entries], [str(second.resolve()), str(first.resolve())])
            self.assertEqual(raw[0], {"root": str(second.resolve()), "opened_at": "2026-08-05T11:00:00+00:00"})


class StateCompatibilityTests(unittest.TestCase):
    def test_other_collection_is_rejected_without_mutating_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = root / "first"
            second = root / "second"
            state = root / "state"
            for directory in (first, second, state):
                directory.mkdir()
            config = {
                "media_root": str(first.resolve()),
                "state_identity": state_identity(first, DEFAULT_PROFILE),
            }
            config_path = state / "gallery-config.json"
            config_path.write_text(json.dumps(config))
            sentinel = state / "action-history.json"
            sentinel.write_text("[\"preserve\"]")

            with self.assertRaises(StateCompatibilityError):
                ensure_compatible_state(state, second, DEFAULT_PROFILE)

            self.assertEqual(config_path.read_text(), json.dumps(config))
            self.assertEqual(sentinel.read_text(), "[\"preserve\"]")

    def test_matching_legacy_config_is_adoptable(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            media = root / "media"
            state = root / "state"
            media.mkdir()
            state.mkdir()
            (state / "gallery-config.json").write_text(json.dumps({"media_root": str(media.resolve())}))

            ensure_compatible_state(state, media, DEFAULT_PROFILE)
