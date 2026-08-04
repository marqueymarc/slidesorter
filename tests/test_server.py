import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import threading
import unittest

from slidesorter.actions import DestinationAction
from slidesorter.server import (
    GalleryConfig,
    GalleryHandler,
    inside,
    safe_relative,
    validate_roots,
)


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
        state = root / "state"
        destination = media / "Removed"
        media.mkdir()
        state.mkdir()
        action = DestinationAction("remove", "Remove", destination.resolve())
        config = GalleryConfig(
            media_root=media.resolve(), gallery_root=state.resolve(), title="Fixture",
            source_label="Fixture", actions=(action,), keep_structure=keep_structure,
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
                media_mode="both", thumbnail_width=720, thumbnail_policy="lazy", workers=1,
            )
            handler = object.__new__(GalleryHandler)
            handler.server = SimpleNamespace(gallery_config=config, gallery_lock=threading.RLock())

            with self.assertRaises(ValueError):
                handler.history_media_path("missing")


if __name__ == "__main__":
    unittest.main()
