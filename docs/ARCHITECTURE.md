# Architecture

## Overview

SlideSorter uses a local-first two-phase design:

```mermaid
flowchart LR
  A["Media tree"] --> B["Catalog builder"]
  B --> C["External state directory"]
  C --> D["Local HTTP server"]
  A --> D
  D --> E["Browser UI"]
  E -->|"Destination move / Undo"| D
  D -->|"Validated file moves"| A
```

The package contains no database and no user media. The builder derives a JSON catalog. The server loads it into memory and serves static assets, thumbnails, byte-range media, and controlled action APIs.

## Package layout

```text
src/slidesorter/
├── actions.py
├── cli.py
├── builder.py
├── server.py
└── assets/
    ├── index.html
    ├── app.css
    ├── app.js
    ├── viewer.html
    ├── history.html
    └── history.js
```

## Runtime state layout

```text
state-directory/
├── gallery-config.json
├── catalog.json
├── manifest.json
├── action-history.json
├── index.html
├── app.css
├── app.js
├── viewer.html
├── history.html
├── history.js
└── thumbs/
```

Static assets are copied into state during each build. This ensures one state directory is internally consistent and independently servable.

## Request flow

1. The browser requests `/gallery/`.
2. The app requests one `/api/catalog` page.
3. The server filters and sorts its in-memory catalog.
4. The browser lazily requests `/thumbnail/...` URLs.
5. The server creates missing cached posters.
6. Media plays through `/media/...` with HTTP byte ranges.

## File action transaction

Every configured destination uses this sequence:

1. Decode and validate a media-root-relative ID.
2. Reject configured destination descendants as source files.
3. Resolve the destination beneath its configured root, preserving the relative path or flattening to the filename according to Settings.
4. Reject an existing destination.
5. Append a `planned` journal record.
6. Move the file.
7. Mark the journal record `moved`.
8. Rebuild and reload the catalog.

Batch actions preflight every destination and detect flat-name collisions before moving the first file.

## Undo transaction

Undo accepts an individual journal entry, a requested batch token, or the newest active token. It verifies every selected source and destination against recorded roots. It refuses missing destinations and occupied source paths. Batch restores run in reverse order; item Undo leaves the remaining token members available for a later Undo all.

## Selection model

SlideSorter avoids sending tens of thousands of IDs to the browser. Select all stores a filter snapshot plus explicit inclusions and exclusions. Bulk actions resolve the snapshot against the current server catalog.

Shift ranges use a read-only endpoint that resolves anchor and target positions in the active search, type, and sort order.

## History previews

History media uses journal entry IDs, not arbitrary paths. The server resolves only an existing recorded source or destination beneath the roots snapshotted in that journal entry. This remains safe and usable if a destination is later renamed or removed from Settings. Videos use the same byte-range implementation as gallery playback.

## History reconciliation and retention

`POST /api/rebuild-history` performs an explicit reconciliation under the gallery lock. It resolves journaled paths only beneath their snapshotted media and destination roots, then classifies each active record as moved, restored, purged, conflict, failed, or skipped. It never moves or deletes media.

Purged records carry a `purged_at` timestamp. The configured retention period is persisted in `gallery-config.json`; expired Purged records are removed during reconciliation and later atomic journal writes. Stable sorting keeps Purged records below every other status in the History response. Batch Undo remains available only when every moved member of the token is present and every original path is free.

## Concurrency model

Python’s `ThreadingHTTPServer` handles static and media requests concurrently. One reentrant lock serializes settings, moves, Undo, and rebuild operations. A separate thumbnail lock prevents duplicate poster generation.

Run one server per state directory. Multiple processes do not share locks.

## Why not static hosting?

Static hosting can render the interface but cannot inspect or modify arbitrary client files. Browser sandbox rules prohibit the core workflow. A hosted service would need uploads, authentication, object storage, a database, and a new privacy model.

SlideSorter therefore distributes stateless code and runs stateful operations locally.
