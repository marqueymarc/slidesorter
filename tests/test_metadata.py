import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

from slidesorter.metadata import capture_metadata


class CaptureMetadataTests(unittest.TestCase):
    def make_jpeg(self, path: Path, capture: str | None = None) -> None:
        image = Image.new("RGB", (8, 8), color=(120, 180, 140))
        if capture:
            exif = Image.Exif()
            exif[36867] = capture
            image.save(path, format="JPEG", exif=exif)
        else:
            image.save(path, format="JPEG")

    def test_embedded_image_capture_time_wins_over_file_time(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "photo.jpg"
            self.make_jpeg(path, "2010:01:02 03:04:05")

            result = capture_metadata(path, "picture", 2_000_000_000)

            self.assertEqual(result["captured_at"], "2010-01-02T03:04:05")
            self.assertEqual(result["capture_source"], "embedded")
            self.assertEqual(result["date_label"], "2010-01-02 03:04")
            self.assertNotEqual(result["date_sort"], 2_000_000_000)

    def test_missing_image_metadata_is_explicit_file_fallback(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "no-date.jpg"
            self.make_jpeg(path)

            result = capture_metadata(path, "picture", 1_234_567_890)

            self.assertIsNone(result["captured_at"])
            self.assertEqual(result["capture_source"], "file")
            self.assertEqual(result["date_sort"], 1_234_567_890)
            self.assertIn("file modification", str(result["date_title"]))

    @patch("slidesorter.metadata._exiftool_capture", return_value=None)
    @patch("slidesorter.metadata.shutil.which", return_value="/usr/bin/ffprobe")
    @patch("slidesorter.metadata.subprocess.run")
    def test_video_creation_time_comes_from_ffprobe(self, run, _which, _exiftool):
        run.return_value = SimpleNamespace(
            returncode=0,
            stdout=json.dumps({"format": {"tags": {"creation_time": "2014-07-21T16:20:30Z"}}}),
        )

        result = capture_metadata(Path("clip.mov"), "video", 2_000_000_000)

        self.assertEqual(result["captured_at"], "2014-07-21T16:20:30+00:00")
        self.assertEqual(result["capture_source"], "embedded")
        self.assertEqual(result["date_label"], "2014-07-21 16:20")

    @patch("slidesorter.metadata._exiftool_capture", return_value=None)
    @patch("slidesorter.metadata._pillow_capture", return_value=None)
    def test_malformed_image_metadata_falls_back_without_failing_build(self, _pillow, _exiftool):
        result = capture_metadata(Path("malformed.jpg"), "picture", 987.5)

        self.assertEqual(result["capture_source"], "file")
        self.assertEqual(result["date_sort"], 987.5)


if __name__ == "__main__":
    unittest.main()
