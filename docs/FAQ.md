# Frequently asked questions

## Does SlideSorter delete files?

No. Remove moves files to a configured holding directory. Deleting that directory is a separate action outside SlideSorter.

## Does it modify Apple Photos?

No. SlideSorter does not open, inspect, deduplicate, or import into a Photos library.

## Can GitHub Pages host the whole application?

No. A static page cannot access arbitrary local drives or perform recoverable filesystem moves.

## Can GitHub host it without my data?

Yes. GitHub hosts source, documentation, releases, and a stateless container. Runtime volumes hold all personal state.

## Can I browse remotely?

Yes. Keep the server on localhost and use Tailscale Serve. Do not expose it anonymously.

## Why do some videos download instead of play?

The browser may not support that file’s codec or container. SlideSorter does not transcode media.

## Why is seeking unavailable?

Seeking requires a browser-supported format and HTTP byte ranges. SlideSorter supplies byte ranges, but the browser controls codec support.

## Can Stage live on another disk?

Yes. Cross-disk moves may copy the entire file before removing the source.

## Can two users operate simultaneously?

Avoid it. One server serializes actions, but two people can still make surprising workflow decisions. One state directory must have only one server process.
