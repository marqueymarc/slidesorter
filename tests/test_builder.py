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
            self.assertTrue((state / "index.html").is_file())
            self.assertTrue((state / "history.js").is_file())
            index = (state / "index.html").read_text()
            self.assertIn("/gallery/app.js?v=3.5.0", index)
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


if __name__ == "__main__":
    unittest.main()
