"""Command line entry point: ``mcmaster fetch 91251A540 ...``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import export
from .client import McMasterClient, McMasterError
from .config import ConfigError, load_credentials

DEFAULT_CAD = ["3-D STEP"]


def read_part_numbers(args: argparse.Namespace) -> list[str]:
    parts = list(args.parts)
    if args.file:
        for line in Path(args.file).read_text().splitlines():
            line = line.split("#", 1)[0].strip()
            if line:
                parts.append(line)
    seen, unique = set(), []
    for p in parts:
        p = p.strip().upper()
        if p and p not in seen:
            seen.add(p)
            unique.append(p)
    return unique


def fetch_part(client: McMasterClient, part: str, args: argparse.Namespace) -> dict:
    product = client.subscribe(part)
    record = {"product": product, "files": []}
    if args.price:
        record["price"] = client.get_price(part)

    available = export.links(product)
    wanted = [] if args.no_cad else (args.cad or DEFAULT_CAD)
    if args.images:
        wanted = wanted + ["Image"]
    part_dir = args.out / "cad" / part
    for key in wanted:
        link = available.get(key)
        if not link:
            print(f"  {part}: no '{key}' file available", file=sys.stderr)
            continue
        try:
            path = client.download(link, part_dir)
        except McMasterError as e:
            # Keep the specs even if one file fails (CAD downloads are rate-limited).
            print(f"  {part}: could not download '{key}': {e}", file=sys.stderr)
            record.setdefault("errors", []).append(f"{key}: {e}")
            continue
        record["files"].append(str(path.relative_to(args.out)))
        print(f"  {part}: saved {key} -> {path}")
    return record


def cmd_fetch(args: argparse.Namespace) -> int:
    parts = read_part_numbers(args)
    if not parts:
        print("No part numbers given.", file=sys.stderr)
        return 2
    args.out.mkdir(parents=True, exist_ok=True)

    records, failed = [], []
    with McMasterClient(load_credentials(args.config)) as client:
        for part in parts:
            print(f"Fetching {part}")
            try:
                records.append(fetch_part(client, part, args))
            except McMasterError as e:
                print(f"  {part}: {e}", file=sys.stderr)
                failed.append(part)
                if e.status == 401:
                    break  # credentials or token problem; the rest will fail too

    if records:
        export.write_json(records, args.out / "parts.json")
        export.write_csv(records, args.out / "parts.csv")
        print(f"Wrote {len(records)} part(s) to {args.out / 'parts.csv'} and parts.json")
    if failed:
        print(f"Failed: {', '.join(failed)}", file=sys.stderr)
        return 1
    return 0


def cmd_unsubscribe(args: argparse.Namespace) -> int:
    parts = read_part_numbers(args)
    status = 0
    with McMasterClient(load_credentials(args.config)) as client:
        for part in parts:
            try:
                client.unsubscribe(part)
                print(f"Unsubscribed {part}")
            except McMasterError as e:
                print(f"  {part}: {e}", file=sys.stderr)
                status = 1
    return status


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mcmaster", description=__doc__)
    parser.add_argument("--config", type=Path, help="TOML credentials file (default: ./mcmaster.toml)")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_parts(p):
        p.add_argument("parts", nargs="*", help="McMaster-Carr part numbers, e.g. 91251A540")
        p.add_argument("-f", "--file", help="Text file with one part number per line (# comments ok)")

    fetch = sub.add_parser("fetch", help="Fetch specs and CAD files for parts")
    add_parts(fetch)
    fetch.add_argument("-o", "--out", type=Path, default=Path("mcmaster-output"), help="Output folder")
    fetch.add_argument(
        "--cad",
        action="append",
        metavar="TYPE",
        help="CAD link to download, as named by the API (repeatable). Default: '3-D STEP'. "
        "Others include '2-D DWG', '3-D SolidWorks', '3-D IGES'.",
    )
    fetch.add_argument("--no-cad", action="store_true", help="Only fetch specs")
    fetch.add_argument("--images", action="store_true", help="Also download the product image")
    fetch.add_argument("--price", action="store_true", help="Also fetch pricing")
    fetch.set_defaults(func=cmd_fetch)

    unsub = sub.add_parser("unsubscribe", help="Remove parts from your API subscriptions")
    add_parts(unsub)
    unsub.set_defaults(func=cmd_unsubscribe)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except ConfigError as e:
        print(f"Config error: {e}", file=sys.stderr)
        return 2
    except McMasterError as e:
        print(f"McMaster-Carr API error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
