# User guide

## Start a collection

```sh
slidesorter run "/path/to/Media" --title "My Media"
```

Open `http://127.0.0.1:8765/gallery/`.

SlideSorter scans recursively. It excludes every configured destination tree when that tree lives under the media root.

## Browse

Use the picture, video, and combined filters to narrow the collection. Search matches filenames and relative folder names. Sorting runs on the server and remains consistent across pages.

Change page capacity between 25 and 500. Start with 100 on most machines. Type an arbitrary page number and press Enter to jump there.

## Preview media

Click a card’s central play control to play a video in place. Use native controls to seek. Press Space to play or pause the active video.

Open a media item in a new tab for a larger viewer. The full-screen tab intentionally has no back control because the gallery remains open in its original tab. Click the SlideSorter wordmark to open a fresh gallery tab.

When inline playback ends, SlideSorter restores the card poster and selector.

## Select media

- Click a card to select only that item.
- Command-click on macOS to toggle an item.
- Control-click on other platforms to toggle an item.
- Shift-click to apply the target state across an ordered range.
- Select all on page to affect only visible results.
- Select all results to capture the current search and type filter.

Range selection works across pagination because the server resolves the ordered range.

## Route media

The first run creates Stage and Remove destinations. Settings can rename, reorder, remove, or add destinations. The first two appear as direct card and bulk buttons. Additional destinations appear under More.

By default, SlideSorter preserves each relative path:

Example:

```text
Source: /Media/2024/Trip/IMG_1001.mov
Stage:  /Media/Staged/2024/Trip/IMG_1001.mov
```

Turn off Keep directory structure to flatten moves:

```text
Source: /Media/2024/Trip/IMG_1001.mov
Remove: /Media/Removed/IMG_1001.mov
```

Flat moves refuse duplicate filenames and never overwrite an existing destination.

Use destinations for import queues, review groups, favorites, archives, or recoverable removal. Remove still does not delete media.

### Presentation hints

SlideSorter recognizes a small local vocabulary in a final parenthetical:

```text
Remove (use a red trash can glyph)
Review later (blue clock icon)
Favorites (amber star)
Approved (green check)
```

The parenthetical is hidden from the button and History label after its built-in icon and tone are selected. Ordinary labels such as `Vacation (2018)` remain unchanged. No prompt is sent to an LLM or network service.

Review the holding directory before deleting anything with Finder or another tool.

## Undo moves

Use the global Undo button immediately after a move. Use History to inspect older moves.

Undo:

- restores the exact original path;
- refuses to overwrite an occupied path;
- restores one History item or every remaining item under one batch token;
- requires the moved destination file to remain present.

## Use History

History loads up to 500 current journal entries. Each entry retains the destination label and presentation used when the move occurred. Click an available thumbnail to expand a picture or play a video in place. Use the native video controls for seeking.

Every undoable row has an Undo button that restores only that file. A multi-item move has one batch bar before its first remaining item; Undo all restores every remaining file in that batch. Undo latest batch at the top finds the newest fully restorable batch.

Click the thumbnail again, click ×, or press Escape to close a preview. Use Open full size to create a separate media tab.

Refresh view only rereads the journal. If you later empty Remove, relocate files with Finder, or otherwise change moved media outside SlideSorter, open Settings and choose Rebuild History. SlideSorter then checks every active journal record, removes Undo from unavailable moves, and marks files missing at both recorded paths as Purged. Purged records are grouped at the bottom.

The adjacent retention setting controls how long Purged records remain. It defaults to 90 days and is remembered across restarts. A value of 0 removes Purged records immediately. Rebuild History never age-prunes a move that is still available for Undo.

## Refresh after external changes

Click Refresh after adding, renaming, moving, or deleting files outside SlideSorter. Refresh rescans the root and rebuilds metadata.

## Change settings

Settings can change:

- media root;
- ordered destination labels and folders;
- Keep directory structure behavior;
- picture/video inclusion;
- collection title;
- source label;
- page capacity.
- Purged-history retention.

Saving filesystem settings rebuilds the catalog.

## Stop safely

Wait for any active move to finish. Stop the terminal process with Control-C. Stopping the server does not alter media or remove state.
