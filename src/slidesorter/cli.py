"""Command-line interface for SlideSorter."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from . import __version__
from . import builder, server


def run_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="slidesorter run",
        description="Build a SlideSorter catalog and serve it locally.",
    )
    parser.add_argument("media_root", type=Path, help="Picture and video directory to review")
    parser.add_argument("--state-dir", type=Path, default=builder.DEFAULT_GALLERY_ROOT)
    parser.add_argument("--title", default="Media Library")
    parser.add_argument("--source-label")
    parser.add_argument("--staged-root", type=Path)
    parser.add_argument("--removed-root", type=Path)
    parser.add_argument(
        "--keep-structure",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Preserve source-relative paths beneath destination folders",
    )
    parser.add_argument("--media-mode", choices=("videos", "pictures", "both"), default="both")
    parser.add_argument("--thumbnail-width", type=int, default=720)
    parser.add_argument("--thumbnail-policy", choices=("lazy", "eager"), default="lazy")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    return parser


def print_help() -> None:
    print(
        "SlideSorter\n\n"
        "Usage:\n"
        "  slidesorter run MEDIA_ROOT [options]\n"
        "  slidesorter build --media-root PATH [options]\n"
        "  slidesorter serve [--config PATH] [options]\n\n"
        "Run 'slidesorter COMMAND --help' for command-specific options."
    )


def run(argv: list[str]) -> None:
    args = run_parser().parse_args(argv)
    build_args = [
        "--media-root", str(args.media_root),
        "--gallery-root", str(args.state_dir),
        "--title", args.title,
        "--media-mode", args.media_mode,
        "--thumbnail-width", str(args.thumbnail_width),
        "--thumbnail-policy", args.thumbnail_policy,
        "--workers", str(args.workers),
    ]
    if args.source_label:
        build_args.extend(("--source-label", args.source_label))
    if args.staged_root:
        build_args.extend(("--staged-root", str(args.staged_root)))
    if args.removed_root:
        build_args.extend(("--removed-root", str(args.removed_root)))
    if args.keep_structure is not None:
        build_args.append("--keep-structure" if args.keep_structure else "--no-keep-structure")
    builder.main(build_args)
    server.main(
        [
            "--config", str(args.state_dir / "gallery-config.json"),
            "--host", args.host,
            "--port", str(args.port),
        ]
    )


def main(argv: list[str] | None = None) -> None:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments or arguments[0] in {"-h", "--help"}:
        print_help()
        return
    if arguments[0] in {"-V", "--version"}:
        print(f"SlideSorter {__version__}")
        return
    command, rest = arguments[0], arguments[1:]
    if command == "run":
        run(rest)
    elif command == "build":
        builder.main(rest)
    elif command == "serve":
        server.main(rest)
    else:
        raise SystemExit(f"Unknown command: {command}. Use 'slidesorter --help'.")
