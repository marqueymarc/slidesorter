# User guide

## Start a collection

```sh
slidesorter run "/path/to/Media" --title "My Media"
```

Open `http://127.0.0.1:8765/gallery/`.

SlideSorter scans recursively. It excludes configured Stage and Remove trees when those trees live under the media root.

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

## Stage media

Stage moves selected files beneath the configured Stage root. SlideSorter preserves each relative path.

Example:

```text
Source: /Media/2024/Trip/IMG_1001.mov
Stage:  /Media/Staged/2024/Trip/IMG_1001.mov
```

Use Stage for an import queue, review queue, or later processing step.

## Remove media

Remove moves selected files beneath the configured Remove root. It does not delete them.

Review the holding directory before deleting anything with Finder or another tool.

## Undo moves

Use the global Undo button immediately after a move. Use History to inspect older moves.

Undo:

- restores the exact original path;
- refuses to overwrite an occupied path;
- restores a batch under one journal token;
- requires the moved destination file to remain present.

## Use History

History loads the most recent 500 journal entries. Click a thumbnail to expand a picture or play a video in place. Use the native video controls for seeking.

Click the thumbnail again, click ×, or press Escape to close a preview. Use Open full size to create a separate media tab.

## Refresh after external changes

Click Refresh after adding, renaming, moving, or deleting files outside SlideSorter. Refresh rescans the root and rebuilds metadata.

## Change settings

Settings can change:

- media root;
- Stage root;
- Remove root;
- picture/video inclusion;
- collection title;
- source label;
- page capacity.

Saving filesystem settings rebuilds the catalog.

## Stop safely

Wait for any active move to finish. Stop the terminal process with Control-C. Stopping the server does not alter media or remove state.
