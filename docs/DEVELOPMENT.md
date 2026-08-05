# Development

## Set up

```sh
git clone https://github.com/marqueymarc/slidesorter.git
cd slidesorter
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

Install `ffmpeg` for visual testing.

## Run tests

```sh
python -m unittest discover -s tests -v
```

Compile Python sources:

```sh
python -m compileall -q src tests
```

Check browser JavaScript:

```sh
node --check src/slidesorter/assets/app.js
node --check src/slidesorter/assets/history.js
```

## Run a fixture gallery

Create a disposable media directory outside the repository:

```sh
mkdir -p /tmp/slidesorter-media
slidesorter run /tmp/slidesorter-media --state-dir /tmp/slidesorter-state
```

Never add private media or generated state to test fixtures.

## Build distributions

```sh
python -m pip install build
python -m build
```

Inspect wheel contents:

```sh
python -m zipfile -l dist/slidesorter-3.8.0-py3-none-any.whl
```

Confirm all six browser assets are packaged.

## Release

1. Update `CHANGELOG.md`.
2. Update `slidesorter.__version__` and `pyproject.toml` together.
3. Run tests and package checks.
4. Tag `vX.Y.Z`.
5. Publish a GitHub release.
6. Verify wheel and container artifacts.

The release workflow attaches Python distributions. The container workflow publishes to GHCR.
