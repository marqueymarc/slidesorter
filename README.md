# SlideSorter

Review large picture and video trees without uploading them anywhere.

[![CI](https://github.com/marqueymarc/slidesorter/actions/workflows/ci.yml/badge.svg)](https://github.com/marqueymarc/slidesorter/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/marqueymarc/slidesorter)](https://github.com/marqueymarc/slidesorter/releases/latest)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)

SlideSorter is a local-first media review desk. It scans a directory, builds thumbnails, and presents a fast browser gallery. Route files into named import, review, archive, or removal folders. Undo every move from a persistent journal.

Your media stays on your machine. The GitHub repository and container image contain no catalog, thumbnails, paths, history, or user data.

## Features

- Browse tens of thousands of pictures and videos with server-backed pagination.
- Search filenames and folders without rendering the entire collection.
- Filter pictures, videos, or both.
- Sort by age, name, size, or modification time.
- Play videos inline with seeking and keyboard play/pause.
- Expand pictures without leaving the gallery.
- Select one item, a page, a Shift range, or all filtered results.
- Route individual items and batches to configurable destination folders.
- Keep the first two destinations as direct buttons and place additional labels under More.
- Use lightweight label hints for built-in glyphs and tones without an AI service.
- Preserve relative directory paths during every move.
- Undo single and batch moves from the History journal.
- Preview moved pictures and videos directly in History.
- Reveal original files in Finder, Explorer, or a Linux file manager.
- Keep source code separate from all generated runtime state.
- Use Tailscale Serve for private remote access.

## Safety first

Destination actions **move files**. The default Remove action means “move into a recoverable holding directory,” not permanent deletion.

SlideSorter:

- refuses paths outside the configured media root;
- refuses destination collisions;
- records planned moves before touching files;
- records exact original and destination paths;
- refuses Undo when the original path is occupied;
- excludes every configured destination tree from the active gallery;
- binds to `127.0.0.1` unless you explicitly choose another host.

Back up irreplaceable media before reorganizing it. See [Security](SECURITY.md) and [State and privacy](docs/STATE_AND_PRIVACY.md).

## Requirements

- Python 3.11 or newer
- `ffmpeg` for video thumbnails and broad image support
- macOS or Linux
- A modern browser

Windows should run the core server, but receives less routine testing.

Install `ffmpeg` on macOS:

```sh
brew install ffmpeg
```

Install `ffmpeg` on Debian or Ubuntu:

```sh
sudo apt-get install ffmpeg
```

## Installation

Install the latest GitHub release with `pipx`:

```sh
pipx install "https://github.com/marqueymarc/slidesorter/releases/latest/download/slidesorter-3.3.2-py3-none-any.whl"
```

Install from a checkout:

```sh
git clone https://github.com/marqueymarc/slidesorter.git
cd slidesorter
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

See [Installation](docs/INSTALLATION.md) for platform details and upgrades.

## Quick start

Run one command:

```sh
slidesorter run "/path/to/Media"
```

Open:

```text
http://127.0.0.1:8765/gallery/
```

SlideSorter writes generated state outside the repository:

- macOS: `~/Library/Application Support/SlideSorter/default`
- Linux: `~/.local/state/slidesorter/default`
- Override: set `SLIDESORTER_STATE_DIR`
- Per run: pass `--state-dir PATH`

Stop the server with `Control-C`.

## Choose explicit destinations

The first run creates Stage and Remove defaults. Keep them on the same filesystem for fast renames:

```sh
slidesorter run "/Volumes/Archive/Media" \
  --staged-root "/Volumes/Archive/Media/Staged" \
  --removed-root "/Volumes/Archive/Media/Removed" \
  --title "Family Archive"
```

Place them elsewhere for a different workflow:

```sh
slidesorter run "/Volumes/Archive/Media" \
  --staged-root "/Volumes/Import Queue" \
  --removed-root "/Volumes/Review Holding"
```

After startup, use Settings to rename, reorder, remove, or add up to 16 destinations. The first two stay visible as buttons; the rest appear under More. Destination settings survive rebuilds and later invocations that use the same state directory.

Keep directory structure is enabled by default. Disable it to move files directly into each destination root. Flat moves refuse duplicate filenames and existing destinations.

Labels can include a deterministic presentation hint such as `Remove (use a red trash can glyph)`. SlideSorter maps recognized words to built-in icons and tones locally; it does not call an LLM.

Cross-filesystem moves may copy before removing the source. Keep the computer awake.

## Build and serve separately

Build a catalog without starting the server:

```sh
slidesorter build \
  --media-root "/path/to/Media" \
  --gallery-root "/path/to/slidesorter-state" \
  --media-mode both \
  --thumbnail-policy lazy
```

Serve that catalog later:

```sh
slidesorter serve \
  --config "/path/to/slidesorter-state/gallery-config.json"
```

This split supports launch agents, containers, and repeatable deployments.

## Runtime state

SlideSorter keeps code and state separate.

| File or directory | Purpose | Safe to publish? |
|---|---|---|
| `catalog.json` | Media metadata and relative paths | No |
| `gallery-config.json` | Absolute roots and settings | No |
| `manifest.json` | Build counts and timestamps | Usually no |
| `thumbs/` | Cached media thumbnails | No |
| `action-history.json` | Move and Undo journal | No |
| Source package | Application code and static assets | Yes |

Delete the state directory to discard the catalog and cache. Preserve `action-history.json` while you still need Undo.

Read [State and privacy](docs/STATE_AND_PRIVACY.md) before automating cleanup.

## Stateless distribution and hosting

GitHub can host SlideSorter’s **code**, releases, documentation, and container image without retaining media state.

The interactive application must still run beside the files it manages. A static website cannot access arbitrary local disks, reveal Finder items, or perform recoverable moves. A conventional cloud deployment would require uploading media and adopting an account, database, and storage security model.

Recommended model:

1. Host source and releases on GitHub.
2. Run SlideSorter locally or in a local container.
3. Mount media and state at runtime.
4. Use Tailscale Serve for private remote access.
5. Never expose the write-capable server directly to the public internet.

The published container is stateless. Supply `/media` and `/state` volumes:

```sh
docker run --rm \
  -p 127.0.0.1:8765:8765 \
  -v "/path/to/Media:/media" \
  -v "slidesorter-state:/state" \
  ghcr.io/marqueymarc/slidesorter:3.3.2
```

The image contains code and `ffmpeg`. The mounted volumes contain all user state.

## Private remote access

Keep SlideSorter bound to localhost. Proxy it through Tailscale:

```sh
tailscale serve --bg 8765
```

Tailscale prints a private HTTPS URL available only inside your tailnet.

Disable it when finished:

```sh
tailscale serve --https=443 off
```

See [Remote access](docs/REMOTE_ACCESS.md) for threat-model details.

## Gallery controls

| Control | Behavior |
|---|---|
| Click card | Select only that item |
| Command-click or Control-click | Toggle one item |
| Shift-click | Toggle the ordered range from the anchor |
| Select all on page | Select or clear the visible page |
| Select all results | Select the current filter without downloading every ID |
| First two destination buttons | Move into those configured roots |
| More | Show any additional destination labels |
| Undo | Restore the original path |
| History thumbnail | Expand a picture or play a video in place |
| Space | Play or pause the active inline video |
| `/` | Focus search |
| Escape | Close Settings or a History preview |

## Supported media

Pictures:

```text
jpg jpeg png gif webp heic heif tif tiff bmp
```

Videos:

```text
mov mp4 m4v avi mts m2ts 3gp mkv
```

Browser playback depends on browser codec support. SlideSorter serves HTTP byte ranges, enabling seeking when the browser supports the format.

## Documentation

- [Installation](docs/INSTALLATION.md)
- [User guide](docs/USER_GUIDE.md)
- [Configuration reference](docs/CONFIGURATION.md)
- [Architecture](docs/ARCHITECTURE.md)
- [State and privacy](docs/STATE_AND_PRIVACY.md)
- [Remote access](docs/REMOTE_ACCESS.md)
- [Development](docs/DEVELOPMENT.md)
- [Frequently asked questions](docs/FAQ.md)
- [Security policy](SECURITY.md)
- [Contributing](CONTRIBUTING.md)
- [Changelog](CHANGELOG.md)

## Current limitations

- SlideSorter manages filesystem media, not Apple Photos libraries.
- It does not compare Photos assets or import into Photos.
- It does not transcode unsupported video codecs.
- The server has no built-in accounts or authentication.
- Folder pickers are native on macOS; other systems require typed paths.
- Cross-device moves can be slow and cannot be atomic.
- Runtime state is single-process. Do not run two servers against one state directory.

## Contributing

Run the tests before submitting a change:

```sh
python -m unittest discover -s tests -v
```

Read [Contributing](CONTRIBUTING.md) and [Development](docs/DEVELOPMENT.md).

## License

SlideSorter is available under the [MIT License](LICENSE).
