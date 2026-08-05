from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from slidesorter import cli


class RunCommandTests(unittest.TestCase):
    def test_run_uses_the_default_collection_profile(self):
        with tempfile.TemporaryDirectory() as temporary:
            media = Path(temporary) / "media"
            media.mkdir()
            with patch("slidesorter.cli.builder.main") as build, patch("slidesorter.cli.server.main") as serve:
                cli.run([str(media)])

            build_args = build.call_args.args[0]
            state = media.resolve() / ".slidesorterstate" / "default"
            self.assertIn(str(state), build_args)
            self.assertIn("--profile", build_args)
            self.assertIn("default", build_args)
            self.assertEqual(
                serve.call_args.args[0][:2],
                ["--config", str(state / "gallery-config.json")],
            )

    def test_run_uses_named_profiles_as_independent_state_directories(self):
        with tempfile.TemporaryDirectory() as temporary:
            media = Path(temporary) / "media"
            media.mkdir()
            with patch("slidesorter.cli.builder.main") as build, patch("slidesorter.cli.server.main"):
                cli.run([str(media), "--profile", "triage"])

            self.assertIn(str(media.resolve() / ".slidesorterstate" / "triage"), build.call_args.args[0])

    def test_state_dir_and_profile_are_not_ambiguous(self):
        with tempfile.TemporaryDirectory() as temporary:
            media = Path(temporary) / "media"
            media.mkdir()
            with self.assertRaises(SystemExit):
                cli.run([str(media), "--state-dir", str(media / "state"), "--profile", "triage"])

    def test_run_without_a_root_reopens_the_last_compatible_collection(self):
        with tempfile.TemporaryDirectory() as temporary:
            media = Path(temporary) / "media"
            state = Path(temporary) / "state"
            media.mkdir()
            state.mkdir()
            (state / "gallery-config.json").write_text("{}")
            config = SimpleNamespace(media_root=media.resolve(), state_profile="triage")
            with (
                patch("slidesorter.cli.read_collection_registry", return_value=[{"root": str(media), "opened_at": "now"}]),
                patch("slidesorter.cli.server.collection_state_dir", return_value=state),
                patch("slidesorter.cli.server.GalleryConfig.load", return_value=config),
                patch("slidesorter.cli.builder.main") as build,
                patch("slidesorter.cli.server.main") as serve,
            ):
                cli.run([])

            self.assertIn(str(state), build.call_args.args[0])
            self.assertIn("triage", build.call_args.args[0])
            self.assertEqual(serve.call_args.args[0][:2], ["--config", str(state / "gallery-config.json")])

    def test_run_without_a_root_requires_an_existing_collection(self):
        with patch("slidesorter.cli.read_collection_registry", return_value=[]):
            with self.assertRaisesRegex(SystemExit, "No existing collection"):
                cli.run([])
