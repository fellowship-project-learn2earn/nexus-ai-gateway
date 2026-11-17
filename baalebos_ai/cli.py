"""`ai` command-line interface."""
from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional

from . import __version__
from .client import BaalebosAI, check_status
from .exceptions import (
    BaalebosAuthError,
    BaalebosConnectionError,
    BaalebosError,
    BaalebosRateLimitError,
    BaalebosRequestError,
    BaalebosUnavailableError,
)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ai",
        description="Ask the Baalebos AI gateway (9 free-tier LLM providers, automatic failover).",
        epilog=(
            'Examples:  ai "explain recursion"  |  cat error.log | ai "what went wrong?"  |  ai --status'
        ),
    )
    p.add_argument("prompt", nargs="*", help="the prompt; text piped on stdin is appended to it")
    p.add_argument("--mode", default="auto",
                   help="auto (default) tries providers in order; also manual, fanout, fallback. "
                        "Unknown values behave like auto")
    p.add_argument("--model", help='provider id, for --mode manual (e.g. "groq-llama-3.3-70b")')
    p.add_argument("--raw", action="store_true", help="print the gateway's full JSON response")
    p.add_argument("--no-stdin", action="store_true", help="never read piped input")
    p.add_argument("--status", action="store_true", help="check that the gateway is up, then exit")
    p.add_argument("--version", action="version", version=f"baalebos-ai {__version__}")
    return p


def _read_stdin() -> str:
    try:
        if sys.stdin is None or sys.stdin.isatty():
            return ""
        return sys.stdin.read().strip()
    except (OSError, ValueError):
        return ""


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.status:
        try:
            print(json.dumps(check_status()))
            return 0
        except (BaalebosConnectionError, BaalebosUnavailableError) as exc:
            print(f"Gateway unreachable: {exc}", file=sys.stderr)
            return 1

    parts = [" ".join(args.prompt).strip()] if args.prompt else []
    if not args.no_stdin:
        piped = _read_stdin()
        if piped:
            parts.append(piped)
    prompt = "\n\n".join(p for p in parts if p)
    if not prompt:
        parser.print_usage(sys.stderr)
        print('Give a prompt, e.g.  ai "explain recursion"', file=sys.stderr)
        return 2

    try:
        client = BaalebosAI()
        if args.raw:
            print(json.dumps(client.chat_raw(prompt, mode=args.mode, model=args.model), indent=2))
        else:
            print("\n" + client.chat(prompt, mode=args.mode, model=args.model) + "\n")
        return 0
    except BaalebosRateLimitError as exc:
        print(f"Limit reached: {exc}", file=sys.stderr)
    except BaalebosAuthError as exc:
        print(f"Authentication problem: {exc}", file=sys.stderr)
    except BaalebosRequestError as exc:
        print(f"Bad request: {exc}", file=sys.stderr)
    except (BaalebosConnectionError, BaalebosUnavailableError) as exc:
        print(f"Gateway unavailable: {exc}", file=sys.stderr)
        print("Run `ai --status` to check it, and try again shortly.", file=sys.stderr)
    except BaalebosError as exc:
        print(f"Error: {exc}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
