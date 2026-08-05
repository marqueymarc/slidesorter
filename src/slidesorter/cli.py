"""Command-line interface for SlideSorter."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from . import __version__
from . import builder, server
from .state import DEFAULT_PROFILE, automatic_state_dir, read_collection_registry, validate_profile


def run_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="slidesorter run",
        description="Build a SlideSorter catalog and serve it locally.",
    )
    parser.add_argument(
        "media_root",
        type=Path,
        nargs="?",
        help="Picture and video directory to review; omit to reopen the last collection",
    )
    parser.add_argument(
        "--state-dir",
        type=Path,
        help="Exact state-profile directory; bypasses automatic collection state selection",
    )
    parser.add_argument(
        "--profile",
        help=f"Named automatic state profile (default: {DEFAULT_PROFILE})",
    )
    parser.add_argument("--title")
    parser.add_argument("--source-label")
    parser.add_argument("--staged-root", type=Path)
    parser.add_argument("--removed-root", type=Path)
    parser.add_argument(
        "--keep-structure",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Preserve source-relative paths beneath destination folders",
    )
    parser.add_argument("--media-mode", choices=("videos", "pictures", "both"))
    parser.add_argument("--appearance", choices=("system", "light", "dark"))
    parser.add_argument("--thumbnail-width", type=int)
    parser.add_argument("--thumbnail-policy", choices=("lazy", "eager"))
    parser.add_argument("--workers", type=int)
    parser.add_argument("--history-retention-days", type=int)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    return parser


def print_help() -> None:
    print(
        "SlideSorter\n\n"
        "Usage:\n"
        "  slidesorter run [MEDIA_ROOT] [options]\n"
        "  slidesorter build --media-root PATH [options]\n"
        "  slidesorter serve --config PATH [options]\n\n"
        "Run 'slidesorter COMMAND --help' for command-specific options."
    )


def run(argv: list[str]) -> None:
    args = run_parser().parse_args(argv)
    if args.state_dir is not None and args.profile is not None:
        raise SystemExit("Use either --state-dir or --profile, not both")
    if args.media_root is None and (args.state_dir is not None or args.profile is not None):
        raise SystemExit("MEDIA_ROOT is required with --state-dir or --profile")
    try:
        profile = validate_profile(args.profile or DEFAULT_PROFILE)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    if args.media_root is None:
        for entry in read_collection_registry():
            candidate_root = Path(entry["root"])
            candidate_state = server.collection_state_dir(candidate_root, DEFAULT_PROFILE)
            if (candidate_state / "gallery-config.json").is_file():
                existing = server.GalleryConfig.load(candidate_state / "gallery-config.json")
                media_root = existing.media_root
                state_dir = candidate_state
                profile = existing.state_profile
                break
        else:
            raise SystemExit("No existing collection to reopen. Run 'slidesorter run MEDIA_ROOT' first.")
    else:
        media_root = args.media_root.expanduser().resolve()
        state_dir = (
            args.state_dir.expanduser().resolve()
            if args.state_dir is not None
            else automatic_state_dir(media_root, profile).resolve()
        )
    build_args = [
        "--media-root", str(media_root),
        "--gallery-root", str(state_dir),
        "--profile", profile,
    ]
    for option, value in (
        ("--title", args.title),
        ("--media-mode", args.media_mode),
        ("--appearance", args.appearance),
        ("--thumbnail-width", args.thumbnail_width),
        ("--thumbnail-policy", args.thumbnail_policy),
        ("--workers", args.workers),
    ):
        if value is not None:
            build_args.extend((option, str(value)))
    if args.source_label:
        build_args.extend(("--source-label", args.source_label))
    if args.staged_root:
        build_args.extend(("--staged-root", str(args.staged_root)))
    if args.removed_root:
        build_args.extend(("--removed-root", str(args.removed_root)))
    if args.keep_structure is not None:
        build_args.append("--keep-structure" if args.keep_structure else "--no-keep-structure")
    if args.history_retention_days is not None:
        build_args.extend(("--history-retention-days", str(args.history_retention_days)))
    builder.main(build_args)
    server.main(
        [
            "--config", str(state_dir / "gallery-config.json"),
            "--host", args.host,
            "--port", str(args.port),
        ]
    )


def main(argv: list[str] | None = None) -> None:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments:
        run([])
        return
    if arguments[0] in {"-h", "--help"}:
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
