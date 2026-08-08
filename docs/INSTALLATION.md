# Installation

## Choose an installation method

Use `pipx` for a normal desktop installation. Use Docker for an isolated runtime. Use an editable checkout when contributing.

## Install with Homebrew

```sh
brew install marqueymarc/homebrew-tap/slidesorter
```

The formula installs Python and ffmpeg dependencies. Upgrade when a newer
SlideSorter release is published:

```sh
brew update
brew upgrade slidesorter
```

The tap refreshes its formula from the latest GitHub release daily and can also
be manually run from its Actions page.

## Install with pipx

Install `pipx`:

```sh
brew install pipx
pipx ensurepath
```

Install the release wheel:

```sh
pipx install "https://github.com/marqueymarc/slidesorter/releases/latest/download/slidesorter-3.9.3-py3-none-any.whl"
```

Verify the command:

```sh
slidesorter --version
```

Upgrade later:

```sh
pipx upgrade slidesorter
```

## Install from source

```sh
git clone https://github.com/marqueymarc/slidesorter.git
cd slidesorter
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

## Install ffmpeg

SlideSorter uses `ffmpeg` for video posters and broad image decoding.

macOS:

```sh
brew install ffmpeg
```

Debian or Ubuntu:

```sh
sudo apt-get update
sudo apt-get install ffmpeg
```

Fedora:

```sh
sudo dnf install ffmpeg
```

Without `ffmpeg`, the gallery still runs. Some thumbnails remain unavailable.

## Run with Docker

```sh
docker run --rm \
  -p 127.0.0.1:8765:8765 \
  -v "/path/to/Media:/media" \
  -v "slidesorter-state:/state" \
  ghcr.io/marqueymarc/slidesorter:3.9.3
```

Mount `/media` read-write to use destination actions and Undo. Mount it read-only only for browsing.

## Uninstall

Remove a pipx installation:

```sh
pipx uninstall slidesorter
```

SlideSorter does not remove runtime state automatically. Delete the chosen state directory only after deciding whether to preserve Undo history.
