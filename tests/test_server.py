import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
import tempfile
import threading
import unittest
from unittest.mock import patch

from slidesorter.actions import DestinationAction
from slidesorter.server import (
    DIRECTORY_PROMPTS,
    PUBLIC_GALLERY_FILES,
    GalleryConfig,
    GalleryHandler,
    collection_state_dir,
    copied_actions,
    provision_destination_roots,
    history_entry_undo_available,
    inside,
    latest_release_payload,
    release_version_parts,
    reconcile_history,
    safe_relative,
    validate_roots,
)


class PublicAssetTests(unittest.TestCase):
    def test_pointer_probe_is_an_explicit_public_gallery_asset(self):
        self.assertIn("pointer-probe.html", PUBLIC_GALLERY_FILES)


class UpdateCheckTests(unittest.TestCase):
    def test_release_version_parts_accepts_tags_and_rejects_other_values(self):
        self.assertEqual(release_version_parts("v3.8.0"), (3, 8, 0))
        self.assertEqual(release_version_parts("3.8.0-rc1"), (3, 8, 0))
        with self.assertRaises(ValueError):
            release_version_parts("latest")

    @patch("slidesorter.server.urlopen")
    def test_latest_release_payload_compares_public_release_without_collection_data(self, mocked_open):
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            @staticmethod
            def read():
                return b'{"tag_name":"v3.10.0","html_url":"https://github.com/marqueymarc/slidesorter/releases/tag/v3.10.0"}'

        mocked_open.return_value = Response()
        payload = latest_release_payload()
        self.assertEqual(payload["current_version"], "3.9.0")
        self.assertEqual(payload["latest_version"], "3.10.0")
        self.assertTrue(payload["update_available"])
        self.assertEqual(payload["release_url"], "https://github.com/marqueymarc/slidesorter/releases/tag/v3.10.0")
        self.assertNotIn("media_root", payload)


class DirectoryPickerCompatibilityTests(unittest.TestCase):
    def test_current_and_legacy_destination_fields_are_supported(self):
        self.assertEqual(
            set(DIRECTORY_PROMPTS),
            {"media_root", "action_root", "staged_root", "removed_root"},
        )

    def test_collection_switcher_finds_a_single_named_profile(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "media"
            state = root / ".slidesorterstate" / "triage"
            state.mkdir(parents=True)
            state.joinpath("gallery-config.json").write_text("{}")

            self.assertEqual(collection_state_dir(root), state.resolve())


class PathSafetyTests(unittest.TestCase):
    def test_safe_relative_accepts_nested_media(self):
        self.assertEqual(safe_relative("2024/Trip/photo.jpg").as_posix(), "2024/Trip/photo.jpg")

    def test_safe_relative_rejects_traversal_and_absolute_paths(self):
        for value in ("../photo.jpg", "/tmp/photo.jpg", "folder/../photo.jpg", ""):
            with self.subTest(value=value), self.assertRaises(ValueError):
                safe_relative(value)

    def test_inside_stays_under_root(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            self.assertEqual(inside(root, safe_relative("a/b.jpg")), root / "a" / "b.jpg")

    def test_action_roots_cannot_contain_media_root(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            media = root / "media"
            media.mkdir()
            with self.assertRaises(ValueError):
                validate_roots(media, root, root / "removed")


class RangeTests(unittest.TestCase):
    def test_standard_range(self):
        self.assertEqual(GalleryHandler.parse_range("bytes=10-19", 100), (10, 19))

    def test_open_ended_range(self):
        self.assertEqual(GalleryHandler.parse_range("bytes=90-", 100), (90, 99))

    def test_suffix_range(self):
        self.assertEqual(GalleryHandler.parse_range("bytes=-10", 100), (90, 99))

    def test_invalid_range(self):
        with self.assertRaises(ValueError):
            GalleryHandler.parse_range("bytes=100-101", 100)


class DestinationPathTests(unittest.TestCase):
    def make_handler(self, root: Path, keep_structure: bool) -> tuple[GalleryHandler, DestinationAction]:
        media = root / "media"
        state = media / ".slidesorterstate" / "default"
        destination = media / "Removed"
        media.mkdir()
        state.mkdir(parents=True)
        action = DestinationAction("remove", "Remove", destination.resolve())
        config = GalleryConfig(
            media_root=media.resolve(), gallery_root=state.resolve(), title="Fixture",
            source_label="Fixture", actions=(action,), keep_structure=keep_structure,
            history_retention_days=90,
            media_mode="both", thumbnail_width=720, thumbnail_policy="lazy", workers=1,
        )
        handler = object.__new__(GalleryHandler)
        handler.server = SimpleNamespace(gallery_config=config)
        return handler, action

    def test_structure_on_preserves_source_relative_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            handler, action = self.make_handler(Path(temporary), True)
            source = handler.config.media_root / "Trips" / "photo.jpg"
            self.assertEqual(
                handler.destination_for(action, source, safe_relative("Trips/photo.jpg")),
                action.root / "Trips" / "photo.jpg",
            )

    def test_structure_off_flattens_to_filename(self):
        with tempfile.TemporaryDirectory() as temporary:
            handler, action = self.make_handler(Path(temporary), False)
            source = handler.config.media_root / "Trips" / "photo.jpg"
            self.assertEqual(
                handler.destination_for(action, source, safe_relative("Trips/photo.jpg")),
                action.root / "photo.jpg",
            )

    def test_colocated_state_is_not_an_actionable_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            handler, _ = self.make_handler(Path(temporary), True)
            hidden = handler.config.gallery_root / "hidden.jpg"
            hidden.write_bytes(b"state")

            with self.assertRaises(ValueError):
                handler.source_from_id(".slidesorterstate/default/hidden.jpg")


class SettingsCompatibilityTests(unittest.TestCase):
    def test_public_settings_always_include_stage_and_remove_compatibility_roots(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            media = (root / "media").resolve()
            state = (root / "state").resolve()
            media.mkdir()
            state.mkdir()
            actions = (
                DestinationAction("stage", "Stage", media / "Staged"),
                DestinationAction("remove", "Remove", media / "Removed"),
            )
            config = GalleryConfig(
                media_root=media, gallery_root=state, title="Fixture",
                source_label="Fixture", actions=actions, keep_structure=True,
                history_retention_days=90,
                media_mode="both", thumbnail_width=720, thumbnail_policy="lazy", workers=1,
            )

            settings = config.public_settings()

            self.assertEqual(settings["staged_root"], str(media / "Staged"))
            self.assertEqual(settings["removed_root"], str(media / "Removed"))
            self.assertEqual([action["display_label"] for action in settings["actions"]], ["Stage", "Remove"])
            self.assertEqual(settings["history_retention_days"], 90)
            self.assertEqual(settings["appearance"], "system")

    def test_settings_accept_a_valid_appearance_and_reject_an_unknown_one(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            media = (root / "media").resolve()
            state = (root / "state").resolve()
            media.mkdir()
            state.mkdir()
            config = GalleryConfig(
                media_root=media, gallery_root=state, title="Fixture", source_label="Fixture",
                actions=(DestinationAction("stage", "Stage", media / "Staged"),), keep_structure=True,
                history_retention_days=90, media_mode="both", thumbnail_width=720,
                thumbnail_policy="lazy", workers=1,
            )
            settings = {
                "media_root": str(media),
                "actions": [{"id": "stage", "label": "Stage", "root": str(media / "Staged")}],
                "keep_structure": True,
                "media_mode": "both",
                "title": "Fixture",
                "source_label": "Fixture",
                "appearance": "light",
            }
            self.assertEqual(GalleryConfig.from_settings(config, settings).appearance, "light")
            settings["appearance"] = "sepia"
            with self.assertRaises(ValueError):
                GalleryConfig.from_settings(config, settings)

    def test_settings_cannot_reassign_an_existing_state_profile_to_another_root(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            media = (root / "media").resolve()
            other = (root / "other").resolve()
            state = (root / "state").resolve()
            for directory in (media, other, state):
                directory.mkdir()
            config = GalleryConfig(
                media_root=media,
                gallery_root=state,
                title="Fixture",
                source_label="Fixture",
                actions=(DestinationAction("stage", "Stage", media / "Staged"),),
                keep_structure=True,
                history_retention_days=90,
                media_mode="both",
                thumbnail_width=720,
                thumbnail_policy="lazy",
                workers=1,
            )

            with self.assertRaises(ValueError):
                GalleryConfig.from_settings(
                    config,
                    {
                        "media_root": str(other),
                        "actions": [{"id": "stage", "label": "Stage", "root": str(other / "Staged")}],
                        "media_mode": "both",
                        "title": "Fixture",
                        "source_label": "Fixture",
                    },
                )

    def test_new_destination_cannot_adopt_an_existing_media_subtree(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            media = (root / "media").resolve()
            state = (root / "state").resolve()
            archive = media / "Archive"
            archive.mkdir(parents=True)
            state.mkdir()
            (archive / "already-there.jpg").write_bytes(b"image")
            config = GalleryConfig(
                media_root=media, gallery_root=state, title="Fixture", source_label="Fixture",
                actions=(DestinationAction("stage", "Stage", media / "Staged"),), keep_structure=True,
                history_retention_days=90, media_mode="both", thumbnail_width=720,
                thumbnail_policy="lazy", workers=1,
            )

            with self.assertRaisesRegex(ValueError, "already contains media"):
                GalleryConfig.from_settings(
                    config,
                    {
                        "media_root": str(media),
                        "actions": [
                            {"id": "stage", "label": "Stage", "root": str(media / "Staged")},
                            {"id": "archive", "label": "Archive", "root": str(archive)},
                        ],
                        "keep_structure": True,
                        "media_mode": "both",
                        "title": "Fixture",
                        "source_label": "Fixture",
                    },
                )

    def test_copied_labels_receive_fresh_destination_folders_under_new_root(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            destination = (root / "new").resolve()
            destination.mkdir()
            actions = (
                DestinationAction("stage", "Stage", root / "old" / "Staged"),
                DestinationAction("for-mom", "For Mom (green check icon)", root / "old" / "For Mom"),
            )

            copied = copied_actions(destination, actions)

            self.assertEqual([action.label for action in copied], [action.label for action in actions])
            self.assertEqual([action.root for action in copied], [destination / "Stage", destination / "For Mom"])

    def test_new_destination_folder_is_created_and_verified(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            destination = root / "For Mom"
            actions = (DestinationAction("for-mom", "For Mom", destination),)

            created = provision_destination_roots((), actions)

            self.assertEqual(created, [destination])
            self.assertTrue(destination.is_dir())

    def test_new_destination_rejects_a_file_conflict(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            destination = root / "For Mom"
            destination.write_text("not a folder")
            actions = (DestinationAction("for-mom", "For Mom", destination),)

            with self.assertRaisesRegex(ValueError, "conflicts with an existing file"):
                provision_destination_roots((), actions)


class HistoryMediaTests(unittest.TestCase):
    def test_history_media_resolves_journaled_destination(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            media = root / "media"
            staged = media / "Staged"
            removed = media / "Removed"
            state = root / "state"
            for directory in (media, staged, removed, state):
                directory.mkdir(parents=True, exist_ok=True)
            destination = staged / "2024" / "clip.mov"
            destination.parent.mkdir()
            destination.write_bytes(b"synthetic-video")
            source = media / "2024" / "clip.mov"
            entry = {
                "entry_id": "abc123",
                "source": str(source),
                "destination": str(destination),
                "name": "clip.mov",
                "status": "moved",
                "media_root": str(media.resolve()),
                "action_root": str(staged.resolve()),
            }
            (state / "action-history.json").write_text(json.dumps([entry]))
            config = GalleryConfig(
                media_root=media.resolve(),
                gallery_root=state.resolve(),
                title="Fixture",
                source_label="Fixture",
                actions=(
                    DestinationAction("stage", "Stage", staged.resolve()),
                    DestinationAction("remove", "Remove", removed.resolve()),
                ),
                keep_structure=True,
                history_retention_days=90,
                media_mode="both",
                thumbnail_width=720,
                thumbnail_policy="lazy",
                workers=1,
            )
            handler = object.__new__(GalleryHandler)
            handler.server = SimpleNamespace(gallery_config=config, gallery_lock=threading.RLock())

            self.assertEqual(handler.history_media_path("abc123"), destination.resolve())

    def test_history_media_rejects_unknown_id(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            media = root / "media"
            state = root / "state"
            staged = media / "Staged"
            removed = media / "Removed"
            for directory in (media, state, staged, removed):
                directory.mkdir(parents=True, exist_ok=True)
            (state / "action-history.json").write_text("[]")
            config = GalleryConfig(
                media_root=media.resolve(), gallery_root=state.resolve(), title="Fixture",
                source_label="Fixture",
                actions=(
                    DestinationAction("stage", "Stage", staged.resolve()),
                    DestinationAction("remove", "Remove", removed.resolve()),
                ),
                keep_structure=True,
                history_retention_days=90,
                media_mode="both", thumbnail_width=720, thumbnail_policy="lazy", workers=1,
            )
            handler = object.__new__(GalleryHandler)
            handler.server = SimpleNamespace(gallery_config=config, gallery_lock=threading.RLock())

            with self.assertRaises(ValueError):
                handler.history_media_path("missing")


class HistoryReconciliationTests(unittest.TestCase):
    def entry(self, root: Path, name: str = "clip.mov", status: str = "moved") -> dict[str, object]:
        media = (root / "media").resolve()
        destination_root = (root / "Removed").resolve()
        media.mkdir(exist_ok=True)
        destination_root.mkdir(exist_ok=True)
        return {
            "entry_id": name,
            "token": name,
            "status": status,
            "name": name,
            "source": str(media / name),
            "destination": str(destination_root / name),
            "media_root": str(media),
            "action_root": str(destination_root),
            "created_at": "2026-01-01T00:00:00+00:00",
        }

    def test_available_move_stays_undoable(self):
        with tempfile.TemporaryDirectory() as temporary:
            entry = self.entry(Path(temporary))
            Path(str(entry["destination"])).write_bytes(b"video")

            summary = reconcile_history([entry], 90)

            self.assertEqual(entry["status"], "moved")
            self.assertTrue(history_entry_undo_available(entry))
            self.assertEqual(summary["available"], 1)

    def test_missing_move_becomes_purged(self):
        with tempfile.TemporaryDirectory() as temporary:
            entry = self.entry(Path(temporary))

            summary = reconcile_history([entry], 90)

            self.assertEqual(entry["status"], "purged")
            self.assertIn("purged_at", entry)
            self.assertEqual(summary["purged"], 1)
            self.assertFalse(history_entry_undo_available(entry))

    def test_external_restore_is_recorded(self):
        with tempfile.TemporaryDirectory() as temporary:
            entry = self.entry(Path(temporary))
            Path(str(entry["source"])).write_bytes(b"photo")

            summary = reconcile_history([entry], 90)

            self.assertEqual(entry["status"], "restored")
            self.assertEqual(summary["restored"], 1)

    def test_planned_move_that_never_started_is_failed(self):
        with tempfile.TemporaryDirectory() as temporary:
            entry = self.entry(Path(temporary), status="planned")
            Path(str(entry["source"])).write_bytes(b"photo")

            summary = reconcile_history([entry], 90)

            self.assertEqual(entry["status"], "failed")
            self.assertEqual(summary["failed"], 1)

    def test_expired_purged_record_is_pruned(self):
        with tempfile.TemporaryDirectory() as temporary:
            now = datetime(2026, 8, 4, tzinfo=timezone.utc)
            entry = self.entry(Path(temporary), status="purged")
            entry["purged_at"] = (now - timedelta(days=91)).isoformat()
            entries = [entry]

            summary = reconcile_history(entries, 90, now)

            self.assertEqual(entries, [])
            self.assertEqual(summary["expired"], 1)

    def test_unmounted_recorded_root_is_skipped_not_purged(self):
        with tempfile.TemporaryDirectory() as temporary:
            entry = self.entry(Path(temporary))
            Path(str(entry["action_root"])).rmdir()

            summary = reconcile_history([entry], 90)

            self.assertEqual(entry["status"], "moved")
            self.assertEqual(summary["skipped"], 1)
            self.assertEqual(summary["purged"], 0)

    def test_purged_record_recovers_if_destination_reappears(self):
        with tempfile.TemporaryDirectory() as temporary:
            entry = self.entry(Path(temporary), status="purged")
            entry["purged_at"] = "2026-08-01T00:00:00+00:00"
            Path(str(entry["destination"])).write_bytes(b"video")

            summary = reconcile_history([entry], 90)

            self.assertEqual(entry["status"], "moved")
            self.assertNotIn("purged_at", entry)
            self.assertEqual(summary["available"], 1)


class HistoryUndoTests(unittest.TestCase):
    def make_handler(self, root: Path) -> GalleryHandler:
        media = (root / "media").resolve()
        removed = (root / "Removed").resolve()
        state = (root / "state").resolve()
        for directory in (media, removed, state):
            directory.mkdir(parents=True, exist_ok=True)
        entries: list[dict[str, object]] = []
        for index, name in enumerate(("one.jpg", "two.jpg"), start=1):
            destination = removed / name
            destination.write_bytes(name.encode())
            entries.append({
                "entry_id": f"entry{index}",
                "token": "batch1",
                "batch_size": 2,
                "status": "moved",
                "name": name,
                "source": str(media / name),
                "destination": str(destination),
                "media_root": str(media),
                "action_root": str(removed),
                "created_at": "2026-08-04T09:00:00+00:00",
            })
        (state / "action-history.json").write_text(json.dumps(entries))
        config = GalleryConfig(
            media_root=media,
            gallery_root=state,
            title="Fixture",
            source_label="Fixture",
            actions=(DestinationAction("remove", "Remove", removed),),
            keep_structure=True,
            history_retention_days=90,
            media_mode="both",
            thumbnail_width=720,
            thumbnail_policy="lazy",
            workers=1,
        )
        handler = object.__new__(GalleryHandler)
        handler.server = SimpleNamespace(
            gallery_config=config,
            gallery_lock=threading.RLock(),
            catalog={"items": []},
        )
        handler.run_rebuild = lambda _config: (True, "")
        handler.reload_runtime = lambda: None
        handler.respond_json = lambda _status, payload: setattr(handler, "response_payload", payload)
        return handler

    def test_history_payload_offers_item_and_single_batch_undo(self):
        with tempfile.TemporaryDirectory() as temporary:
            handler = self.make_handler(Path(temporary))

            payload = handler.history_payload()

            self.assertTrue(payload["can_undo"])
            self.assertEqual(len(payload["entries"]), 2)
            self.assertTrue(all(entry["undo_available"] for entry in payload["entries"]))
            self.assertTrue(all(entry["batch_undo_available"] for entry in payload["entries"]))
            self.assertTrue(all(entry["batch_remaining"] == 2 for entry in payload["entries"]))

    def test_item_undo_restores_only_selected_entry(self):
        with tempfile.TemporaryDirectory() as temporary:
            handler = self.make_handler(Path(temporary))

            handler.undo_move({"entry_id": "entry1"})

            history = json.loads(handler.config.history_path.read_text())
            self.assertEqual([entry["status"] for entry in history], ["undone", "moved"])
            self.assertTrue((handler.config.media_root / "one.jpg").is_file())
            self.assertTrue((handler.config.actions[0].root / "two.jpg").is_file())
            self.assertEqual(handler.response_payload["count"], 1)

    def test_batch_undo_restores_every_remaining_entry(self):
        with tempfile.TemporaryDirectory() as temporary:
            handler = self.make_handler(Path(temporary))
            handler.undo_move({"entry_id": "entry1"})

            handler.undo_move({"token": "batch1"})

            history = json.loads(handler.config.history_path.read_text())
            self.assertEqual([entry["status"] for entry in history], ["undone", "undone"])
            self.assertTrue((handler.config.media_root / "two.jpg").is_file())
            self.assertEqual(handler.response_payload["count"], 1)


if __name__ == "__main__":
    unittest.main()
