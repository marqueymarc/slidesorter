# State and privacy

## Data boundary

SlideSorter reads only the configured media root and its generated state directory. It does not upload media, analytics, filenames, thumbnails, or history.

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

## Stateless code distribution

Git, wheels, source archives, and container images contain only application code and static interface assets. `.gitignore` excludes known runtime state names.

The default state path lives outside the source checkout. This reduces accidental commits but does not replace review before publishing.

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
