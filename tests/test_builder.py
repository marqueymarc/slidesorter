import json
from pathlib import Path
import tempfile
import unittest

from slidesorter import builder


class BuilderTests(unittest.TestCase):
    def test_lazy_build_creates_external_state_and_catalog(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            media = root / "media"
            state = root / "state"
            media.mkdir()
            (media / "Trips").mkdir()
            (media / "Trips" / "photo.jpg").write_bytes(b"synthetic-photo")
            (media / "clip.mov").write_bytes(b"synthetic-video")

            builder.main(
                [
                    "--media-root", str(media),
                    "--gallery-root", str(state),
                    "--title", "Fixture Library",
                    "--thumbnail-policy", "lazy",
                    "--media-mode", "both",
                ]
            )

            catalog = json.loads((state / "catalog.json").read_text())
            config = json.loads((state / "gallery-config.json").read_text())
            self.assertEqual(catalog["title"], "Fixture Library")
            self.assertEqual(catalog["source_label"], "media")
            self.assertEqual(len(catalog["items"]), 2)
            self.assertEqual({item["kind"] for item in catalog["items"]}, {"picture", "video"})
            self.assertEqual(config["media_root"], str(media.resolve()))
            self.assertEqual(config["gallery_root"], str(state.resolve()))
            self.assertEqual(config["history_retention_days"], 90)
            self.assertEqual(config["appearance"], "system")
            self.assertTrue((state / "index.html").is_file())
            self.assertTrue((state / "history.js").is_file())
            self.assertTrue((state / "appearance.js").is_file())
            self.assertTrue((state / "favicon.svg").is_file())
            self.assertTrue((state / "pointer-probe.html").is_file())
            index = (state / "index.html").read_text()
            self.assertIn("/gallery/app.js?v=3.9.2", index)
            self.assertIn("/gallery/appearance.js?v=3.9.2", index)
            self.assertIn('rel="icon" href="/gallery/favicon.svg"', index)
            self.assertIn('id="history-link"', index)
            self.assertIn('id="item-action-popover"', index)
            self.assertIn('id="update-instructions"', index)
            self.assertIn('id="update-copy"', index)
            self.assertIn('id="update-instructions-copy"', index)
            self.assertIn('/gallery/pointer-probe.html', index)
            app = (state / "app.js").read_text()
            self.assertIn("toggleItemActionPopover", app)
            self.assertIn("activeTileId", app)
            self.assertIn("function isTypingTarget", app)
            self.assertIn("input[type=checkbox], input[type=radio]", app)
            self.assertNotIn("reconcileHoverIntent", app)
            self.assertNotIn("single-destination-actions", app)
            probe = (state / "pointer-probe.html").read_text()
            self.assertIn('Pointer diagnostics', probe)
            self.assertIn('"pointermove"', probe)
            self.assertIn('"mousemove"', probe)
            self.assertNotIn("fetch(", probe)
            self.assertNotIn("/api/", probe)
            history = (state / "history.html").read_text()
            self.assertIn('id="history-back"', history)
            self.assertIn("Back to SlideSorter", history)
            self.assertFalse((media / "catalog.json").exists())

    def test_stage_and_remove_trees_are_excluded(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            media = root / "media"
            state = root / "state"
            for directory in (media, media / "Staged", media / "Removed"):
                directory.mkdir(parents=True, exist_ok=True)
            (media / "keep.jpg").write_bytes(b"keep")
            (media / "Staged" / "staged.jpg").write_bytes(b"staged")
            (media / "Removed" / "removed.jpg").write_bytes(b"removed")

            builder.main(["--media-root", str(media), "--gallery-root", str(state)])

            catalog = json.loads((state / "catalog.json").read_text())
            self.assertEqual([item["id"] for item in catalog["items"]], ["keep.jpg"])

    def test_default_colocated_state_is_excluded_from_the_catalog(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            media = root / "media"
            state = media / ".slidesorterstate" / "default"
            media.mkdir()
            state.mkdir(parents=True)
            (media / "keep.jpg").write_bytes(b"keep")
            (state / "hidden.jpg").write_bytes(b"generated-state")

            builder.main(["--media-root", str(media)])

            catalog = json.loads((state / "catalog.json").read_text())
            config = json.loads((state / "gallery-config.json").read_text())
            self.assertEqual([item["id"] for item in catalog["items"]], ["keep.jpg"])
            self.assertEqual(config["state_identity"]["profile"], "default")

    def test_mismatched_state_is_rejected_before_writes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = root / "first"
            second = root / "second"
            state = root / "state"
            for directory in (first, second, state):
                directory.mkdir()
            (state / "gallery-config.json").write_text(json.dumps({"media_root": str(first.resolve())}))
            sentinel = state / "action-history.json"
            sentinel.write_text("preserve")

            with self.assertRaises(SystemExit):
                builder.main(["--media-root", str(second), "--gallery-root", str(state)])

            self.assertEqual(sentinel.read_text(), "preserve")

    def test_destinations_and_structure_setting_survive_the_next_build(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            media = root / "media"
            state = root / "state"
            media.mkdir()
            (media / "photo.jpg").write_bytes(b"photo")
            actions = [
                {"id": "keep", "label": "Keep (green check icon)", "root": str(media / "Keep")},
                {"id": "later", "label": "Review later", "root": str(media / "Later")},
                {"id": "remove", "label": "Remove (red trash icon)", "root": str(media / "Removed")},
            ]
            builder.main(
                [
                    "--media-root", str(media),
                    "--gallery-root", str(state),
                    "--actions-json", json.dumps(actions),
                    "--no-keep-structure",
                    "--history-retention-days", "45",
                    "--title", "Remembered Library",
                    "--source-label", "Remembered Source",
                    "--thumbnail-width", "640",
                ]
            )
            builder.main(["--media-root", str(media), "--gallery-root", str(state)])

            config = json.loads((state / "gallery-config.json").read_text())
            self.assertEqual([action["id"] for action in config["actions"]], ["keep", "later", "remove"])
            self.assertFalse(config["keep_structure"])
            self.assertEqual(config["history_retention_days"], 45)
            self.assertEqual(config["title"], "Remembered Library")
            self.assertEqual(config["source_label"], "Remembered Source")
            self.assertEqual(config["thumbnail_width"], 640)
            self.assertEqual(config["appearance"], "system")


if __name__ == "__main__":
    unittest.main()
