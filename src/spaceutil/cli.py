"""Command line for the space utilization analyzer."""
from __future__ import annotations

import argparse
import sys

from .analysis import flag, hourly_profile, load_spaces, load_visits, space_stats


def _report(args: argparse.Namespace) -> int:
    spaces = load_spaces(args.spaces)
    visits = load_visits(args.events, spaces)
    rows = space_stats(visits, spaces, args.day_hours)
    days = len({v.entry.date() for v in visits})
    print(f"Space utilization: {len(visits)} visits over {days} day(s), {args.day_hours:g}-hour day")
    print()
    print(f"{'space':<18}{'cap':>4}{'visits':>8}{'peak':>6}{'util %':>8}  flag")
    for r in sorted(rows, key=lambda r: r["utilization"]):
        print(f"{r['space']:<18}{r['capacity']:>4}{r['visits']:>8}{r['peak']:>6}{r['utilization']:>8.1f}  {flag(r, args.low)}")
    under = [r["space"] for r in rows if flag(r, args.low) == "UNDER"]
    print()
    print(f"Under {args.low:g}% used: {', '.join(under) if under else 'none'}")
    return 0


def _hourly(args: argparse.Namespace) -> int:
    spaces = load_spaces(args.spaces)
    if args.space not in spaces:
        raise ValueError(f"unknown space '{args.space}'")
    visits = [v for v in load_visits(args.events, spaces) if v.space == args.space]
    print(f"{args.space}: average people per hour (capacity {spaces[args.space]})")
    for hour, avg in hourly_profile(visits).items():
        print(f"{hour:02d}:00  {avg:>4.1f}  {'#' * round(avg * 2)}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="spaceutil", description="Occupancy analysis from badge visit data.")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("report", help="utilization table for every space")
    r.add_argument("events")
    r.add_argument("spaces")
    r.add_argument("--low", type=float, default=30.0, help="flag spaces under this percent (default 30)")
    r.add_argument("--day-hours", type=float, default=9.0, help="hours a space is available per day (default 9)")
    r.set_defaults(func=_report)
    h = sub.add_parser("hourly", help="average headcount per hour for one space")
    h.add_argument("events")
    h.add_argument("spaces")
    h.add_argument("space")
    h.set_defaults(func=_hourly)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (ValueError, OSError) as err:
        print(f"error: {err}", file=sys.stderr)
        return 2
