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
            self.assertTrue((state / "index.html").is_file())
            self.assertTrue((state / "history.js").is_file())
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


if __name__ == "__main__":
    unittest.main()
