# Changelog

All notable changes appear here. SlideSorter follows semantic versioning.

## [3.7.0] - 2026-08-05

### Added

- Added persistent System default, Light, and Dark appearance choices. Appearance
  changes immediately across the gallery, History, and standalone media viewer
  without rebuilding the catalog.
- Added a static, local-first product site for GitHub Pages. It contains no
  catalog, state, history, or private media.

### Changed

- Removed redundant picture/video card badges. Video cards retain their play
  control, while the configured media filter remains visible in the toolbar.

## [3.6.0] - 2026-08-04

### Added

- Added Back to SlideSorter navigation on History and preserved the gallery page,
  search, media filter, sort, page capacity, and scroll position on return.
- Added collection-scoped default state at `.slidesorterstate/default` and named
  profiles through `slidesorter run MEDIA_ROOT --profile NAME`.
- Added collection/profile identity checks that reject accidental state reuse
  before any catalog, asset, configuration, or History write.

### Changed

- Kept the SlideSorter wordmark as a separate fresh-tab action so Back and New Gallery remain unambiguous.
- Excluded colocated generated state from scanning and direct media access.
- Made `slidesorter serve --config PATH` explicit because multiple profiles may
  exist on one machine.
- Added Homebrew installation through `marqueymarc/homebrew-tap`.

### Fixed

- Made a card's checkbox show its checkmark immediately on the first selection click.

## [3.5.0] - 2026-08-04

### Added

- Added per-item History Undo for files originally moved as part of a batch.
- Added one batch bar with Undo all remaining instead of repeating a batch Undo button on every row.

### Changed

- Renamed the page action to Undo latest batch to make its scope explicit.
- Opened card destination More menus below their buttons while retaining upward opening in the fixed bulk bar.

## [3.4.0] - 2026-08-04

### Added

- Added Settings → Rebuild History to reconcile journal records with current filesystem availability.
- Added a remembered Purged-record retention setting, defaulting to 90 days.
- Added explicit Purged, restored-outside-SlideSorter, conflict, and unavailable states.

### Changed

- Kept Purged records in a subdued group below all other History entries.
- Made ordinary History Refresh a read-only view refresh.
- Removed Undo and live preview affordances when their recorded media is unavailable.
- Required every member of a batch to remain safely restorable before offering batch Undo.

### Safety

- Reconciliation validates every journaled path against its snapshotted root and never moves or deletes media.
- Active Undo records are exempt from age-based retention pruning.

## [3.3.2] - 2026-08-04

### Fixed

- Accepted legacy Stage and Remove field names in the macOS directory picker so cached Settings tabs no longer report `Unknown directory setting`.

## [3.3.1] - 2026-08-04

### Fixed

- Cache-busted browser assets so Chrome cannot pair an older script with a newly rebuilt gallery.
- Added explicit no-cache headers for versioned gallery code and markup.
- Restored Stage and Remove compatibility roots in Settings responses and supplied safe UI defaults instead of `undefined`.

## [3.3.0] - 2026-08-04

### Added

- Ordered, user-defined destination labels and folders in Settings.
- Direct card and bulk buttons for the first two destinations, with additional destinations under More.
- Persistent destination configuration across rebuilds and later invocations.
- Built-in icon and tone hints such as `Remove (use a red trash can glyph)` without an LLM or network service.
- A remembered Keep directory structure toggle, enabled by default.
- Flat destination moves with collision detection when directory preservation is disabled.

### Changed

- Generalized move and batch APIs beyond hard-coded Stage and Remove actions.
- Snapshotted destination labels, icons, and tones in History so old entries retain their meaning after settings change.
- Migrated existing Stage and Remove configurations automatically.

### Security

- Refused nested or duplicate destination roots.
- Preflighted duplicate filenames before flat batch moves.
- Continued refusing destination overwrites and unsafe Undo restores.

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
[3.3.0]: https://github.com/marqueymarc/slidesorter/releases/tag/v3.3.0
[3.3.1]: https://github.com/marqueymarc/slidesorter/releases/tag/v3.3.1
[3.3.2]: https://github.com/marqueymarc/slidesorter/releases/tag/v3.3.2
[3.4.0]: https://github.com/marqueymarc/slidesorter/releases/tag/v3.4.0
[3.5.0]: https://github.com/marqueymarc/slidesorter/releases/tag/v3.5.0
[3.6.0]: https://github.com/marqueymarc/slidesorter/releases/tag/v3.6.0
[3.7.0]: https://github.com/marqueymarc/slidesorter/releases/tag/v3.7.0
