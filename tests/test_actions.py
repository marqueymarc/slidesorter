from pathlib import Path
import tempfile
import unittest

from slidesorter.actions import (
    DestinationAction,
    action_presentation,
    actions_from_raw,
    validate_actions,
)


class PresentationTests(unittest.TestCase):
    def test_parenthetical_hint_creates_red_trash_presentation(self):
        self.assertEqual(
            action_presentation("Remove (use a red trash can glyph)"),
            ("Remove", "trash", "danger"),
        )

    def test_ordinary_parenthetical_remains_in_label(self):
        self.assertEqual(
            action_presentation("Vacation (2018)"),
            ("Vacation (2018)", "arrow", "neutral"),
        )


class DestinationValidationTests(unittest.TestCase):
    def test_more_than_two_destinations_are_supported_in_order(self):
        with tempfile.TemporaryDirectory() as temporary:
            media = Path(temporary) / "media"
            media.mkdir()
            actions = actions_from_raw(
                media,
                [
                    {"id": "stage", "label": "Stage", "root": "Staged"},
                    {"id": "remove", "label": "Remove", "root": "Removed"},
                    {"id": "review", "label": "Review later (blue clock icon)", "root": "Review"},
                ],
            )
            self.assertEqual([action.id for action in actions], ["stage", "remove", "review"])
            self.assertEqual(actions[2].public_dict()["display_label"], "Review later")

    def test_nested_destinations_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            media = Path(temporary) / "media"
            media.mkdir()
            actions = (
                DestinationAction("one", "One", media / "Destinations"),
                DestinationAction("two", "Two", media / "Destinations" / "Two"),
            )
            with self.assertRaises(ValueError):
                validate_actions(media, actions)

    def test_shortcuts_are_preserved_and_must_be_unique(self):
        with tempfile.TemporaryDirectory() as temporary:
            media = Path(temporary) / "media"
            media.mkdir()
            actions = actions_from_raw(
                media,
                [
                    {"id": "stage", "label": "Stage", "root": "Staged", "shortcut": "S"},
                    {"id": "review", "label": "Review", "root": "Review", "shortcut": "r"},
                ],
            )
            self.assertEqual(actions[0].public_dict()["shortcut"], "s")
            with self.assertRaisesRegex(ValueError, "shortcut keys must be unique"):
                actions_from_raw(
                    media,
                    [
                        {"id": "stage", "label": "Stage", "root": "Staged", "shortcut": "s"},
                        {"id": "save", "label": "Save", "root": "Save", "shortcut": "S"},
                    ],
                )

    def test_undo_shortcut_is_reserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            media = Path(temporary) / "media"
            media.mkdir()
            with self.assertRaisesRegex(ValueError, "U is reserved for Undo"):
                actions_from_raw(
                    media,
                    [{"id": "undoable", "label": "Undoable", "root": "Undoable", "shortcut": "U"}],
                )


if __name__ == "__main__":
    unittest.main()
