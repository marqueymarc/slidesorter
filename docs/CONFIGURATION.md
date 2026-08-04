# Configuration reference

## Environment

### `SLIDESORTER_STATE_DIR`

Set the parent directory for generated state.

```sh
export SLIDESORTER_STATE_DIR="$HOME/.slidesorter-state"
```

The default collection uses a `default` child directory.

## `slidesorter run`

```text
slidesorter run MEDIA_ROOT [options]
```

| Option | Default | Meaning |
|---|---|---|
| `--state-dir` | Platform state path | Catalog, cache, config, and history root |
| `--title` | `Media Library` | Collection heading |
| `--source-label` | Media root name | Short source description |
| `--staged-root` | `MEDIA_ROOT/Staged` | Staging destination |
| `--removed-root` | `MEDIA_ROOT/Removed` | Recoverable removal destination |
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

`--media-root` is required. `--gallery-root` controls the generated state directory.

## `slidesorter serve`

```sh
slidesorter serve --config PATH [--host HOST] [--port PORT]
```

The default config is the platform default state path.

## Root constraints

Stage and Remove must differ. Neither can equal the media root or contain the media root. They may live inside or outside the media root.

SlideSorter creates destination parent directories during moves. It does not require Stage and Remove to exist before the first move.

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
