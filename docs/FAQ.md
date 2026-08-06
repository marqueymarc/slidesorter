# Frequently asked questions

## Does SlideSorter delete files?

No. Remove moves files to a configured holding directory. Deleting that directory is a separate action outside SlideSorter.

## Can I add destinations besides Stage and Remove?

Yes. Settings supports up to 16 ordered labels, shortcut keys, and folders. Select media to reveal every destination label that fits; any overflow is available under More.

## Do parenthetical icon instructions use AI?

No. SlideSorter recognizes a small local vocabulary for built-in icons and tones. Arbitrary prompt interpretation or generated artwork would require an optional model-backed service and is intentionally outside the local core.

## What happens when Keep directory structure is off?

Files move directly into the selected destination folder. SlideSorter refuses existing filenames and duplicate names within a batch rather than overwriting anything.

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

## Why did the tile actions stop appearing when I move the pointer?

Tile actions no longer depend on hover. Hover only highlights the current tile and targets its configured shortcut. Use the stable `…` on any unselected tile to open the one shared destination popover, or select items to use the global action bar. SlideSorter clears the shortcut target after focus, resize, or scrolling if pointer delivery is uncertain, so it cannot act on a stale tile. Settings → About & help → Pointer diagnostics provides a local, media-free event report if the browser itself still behaves unexpectedly.

## Can a destination live on another disk?

Yes. Cross-disk moves may copy the entire file before removing the source.

## Can two users operate simultaneously?

Avoid it. One server serializes actions, but two people can still make surprising workflow decisions. One state profile must have only one server process.

## Can I run more than one SlideSorter collection or workflow?

Yes. Each root has its own hidden default state profile. For independent
workflows on one root, use `slidesorter run MEDIA_ROOT --profile NAME`. Do not
run two servers on the same profile.

## What happens after I empty Remove outside SlideSorter?

The History page initially keeps the journal record, but Undo becomes unavailable as soon as the destination is gone. Use Settings → Rebuild History to mark it Purged. Purged entries appear at the bottom and expire under the remembered retention setting, which defaults to 90 days.

Rebuild History deletes no media. It only updates and eventually prunes journal records whose files are already missing from both recorded paths.
