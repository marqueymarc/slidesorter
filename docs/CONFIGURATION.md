# Configuration reference

## Environment

### `SLIDESORTER_STATE_DIR`

Set the parent directory for automatic fallback state when a media root cannot
host its own hidden state directory.

```sh
export SLIDESORTER_STATE_DIR="$HOME/.slidesorter-state"
```

Fallback state uses `collections/<collection-id>/<profile>`. It never uses one
shared `default` directory for every collection.

## `slidesorter run`

```text
slidesorter run MEDIA_ROOT [options]
```

| Option | Default | Meaning |
|---|---|---|
| `--state-dir` | `MEDIA_ROOT/.slidesorterstate/default` when writable | Exact catalog, cache, config, and history root |
| `--profile` | `default` | Named automatic state profile; uses `MEDIA_ROOT/.slidesorterstate/PROFILE` |
| `--title` | `Media Library` | Collection heading |
| `--source-label` | Media root name | Short source description |
| `--staged-root` | `MEDIA_ROOT/Staged` | Staging destination |
| `--removed-root` | `MEDIA_ROOT/Removed` | Recoverable removal destination |
| `--keep-structure` | enabled | Preserve source-relative paths at destinations |
| `--no-keep-structure` | — | Move files directly into destination folders |
| `--history-retention-days` | `90` | Days to retain records after they become Purged (`0` removes them immediately) |
| `--media-mode` | `both` | `pictures`, `videos`, or `both` |
| `--thumbnail-width` | `720` | Thumbnail pixel width |
| `--thumbnail-policy` | `lazy` | Generate on demand or eagerly |
| `--workers` | `4` | Eager thumbnail worker count |
| `--host` | `127.0.0.1` | Listening address |
| `--port` | `8765` | Listening port |

## `slidesorter build`

Use Build for scheduled scans or separated service management.

```sh
slidesorter build --media-root PATH [options]
```

`--media-root` is required. If `--gallery-root` is omitted, Build uses the same
per-collection default as Run. `--profile` selects its named profile.

## `slidesorter serve`

```sh
slidesorter serve --config PATH [--host HOST] [--port PORT]
```

`--config` is required because multiple collection profiles may coexist.

## Destination settings

The browser Settings panel stores an ordered `actions` list in `gallery-config.json`. Each entry has a stable id, a raw label, and an absolute destination root. The first two actions are direct buttons; later actions appear under More.

The builder preserves actions and the directory-structure setting when the same state profile is rebuilt or started again. Existing Stage and Remove configuration migrates automatically.

Each state profile records its canonical media root and profile name. Reusing it
for a different root, or a different profile, fails before it rewrites the
catalog, configuration, assets, or History. Older compatible state is adopted
on its next successful build without clearing History. To use existing state at
an old location, pass that location with `--state-dir`; SlideSorter never moves
it automatically.

The History retention setting is also preserved. Changing it through Settings → Rebuild History updates `gallery-config.json` without rescanning the media catalog.

## History reconciliation

Rebuild History checks the source and destination paths recorded for each active move:

- destination present and source absent: still available for Undo;
- destination absent and source present: restored outside SlideSorter;
- both paths absent: Purged and no longer undoable;
- both paths present: conflict, so SlideSorter will not offer Undo;
- unsafe or malformed journal paths: skipped without filesystem access.

Purged entries are retained for `history_retention_days`, shown after active and completed entries, and automatically pruned on later journal writes or History rebuilds. Active `planned` and `moved` records are always retained.

Labels may end with a recognized presentation hint, for example `Remove (use a red trash can glyph)`. This is deterministic local parsing, not an LLM call. Unknown parentheticals remain part of the visible label.

## Root constraints

Destination folders must differ and cannot contain one another. A destination cannot equal the media root or contain the media root. Destinations may live inside or outside the media root.

SlideSorter creates destination parent directories during moves. Destinations do not need to exist before the first move.

With Keep directory structure enabled, `/Root/A/B/photo.jpg` moves to `/Destination/A/B/photo.jpg`. With it disabled, the same file moves to `/Destination/photo.jpg`. Flat single and batch moves refuse collisions.

## Thumbnail policy

Use `lazy` for large collections. The first visit to a page creates missing thumbnails and caches them.

Use `eager` for kiosks or offline demonstrations. Build time increases with corpus size.

Thumbnail cache keys include:

- absolute media path;
- file size;
- nanosecond modification time;
- thumbnail width.

Changing any value creates a new cache entry.

## Binding addresses

Keep `127.0.0.1` for normal use. Binding `0.0.0.0` exposes write actions to reachable networks. SlideSorter has no built-in authentication.

Prefer Tailscale Serve over a public bind.
