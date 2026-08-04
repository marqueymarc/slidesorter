# Changelog

All notable changes appear here. SlideSorter follows semantic versioning.

## [3.2.0] - 2026-08-04

### Added

- First public SlideSorter release.
- Local-first picture and video catalog builder.
- Server-backed search, filters, sorting, and pagination.
- Configurable page capacity and direct page navigation.
- Finder-style single, toggle, range, page, and filtered selection.
- Recoverable Stage and Remove operations.
- Batch moves with one-token Undo.
- Persistent History journal with thumbnails.
- In-place picture expansion and video playback in History.
- HTTP byte ranges for video seeking.
- Settings for media, Stage, Remove, and collection roots.
- External state directory defaults.
- Unified `slidesorter run`, `build`, and `serve` commands.
- Docker image with mounted media and state volumes.
- Tailscale Serve documentation for private remote access.

### Changed

- Branded the interface and server as SlideSorter.
- Made the SlideSorter wordmark open a fresh gallery tab.
- Removed return navigation from full-screen media tabs.
- Generalized hard-coded Kepler paths into required runtime configuration.

### Security

- Kept localhost as the default bind address.
- Validated decoded relative paths before access.
- Restricted History media to journaled source and destination files.
- Refused collisions and unsafe Undo restores.

[3.2.0]: https://github.com/marqueymarc/slidesorter/releases/tag/v3.2.0
