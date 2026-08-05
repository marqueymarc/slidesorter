# State and privacy

## Data boundary

SlideSorter reads only the configured media root and its generated state profile. It does not upload media, analytics, filenames, thumbnails, or history.

The application contains no telemetry SDK and makes no application-level outbound requests.

Package installation and container pulls may contact their normal registries.

## Generated state

### Catalog

`catalog.json` contains relative paths, sizes, modification times, media types, and display labels.

### Configuration

`gallery-config.json` contains absolute filesystem paths. Treat it as private machine metadata.

### Thumbnails

`thumbs/` contains derived JPEG previews. A thumbnail may reveal sensitive visual content.

### History

`action-history.json` contains source paths, destination paths, timestamps, statuses, and recovery tokens. Preserve it while Undo matters.

Settings → Rebuild History reads only the source and destination paths already recorded in this file. It marks entries Purged when neither path still contains the media. Purged records are deleted after the configured retention interval; active Undo records are not deleted by retention. The normal History Refresh view does not modify the journal.

## Stateless code distribution

Git, wheels, source archives, and container images contain only application code and static interface assets. `.gitignore` excludes known runtime state names.

The default state path is `MEDIA_ROOT/.slidesorterstate/default`, excluded from
the catalog. When the root is not writable, SlideSorter uses a stable,
collection-specific platform-state fallback. This reduces accidental sharing
between collections but does not replace review before publishing.

Each profile records its canonical media root and profile name. A state
directory assigned to another collection is rejected before SlideSorter writes
generated files or touches History. Existing compatible state is adopted; no
state is moved or deleted automatically.

## Ephemeral operation

You may place state in a temporary directory for browsing-only sessions:

```sh
slidesorter run "/path/to/Media" --state-dir "$(mktemp -d)"
```

Do not use ephemeral state when you need durable Undo history. Destination actions alter media even if the journal later disappears.

## Deleting state

Stopping SlideSorter does not delete state. Removing the state directory discards:

- cached thumbnails;
- catalog metadata;
- configuration;
- move history.

It does not restore or delete media files.

## Backups

Back up original media independently. Do not place a backup on the same physical device as its original.

For durable recovery, back up `action-history.json` with the media tree while moves remain under review.
