"""CLI entrypoint — `prevue review` drives the walking skeleton loop."""

from __future__ import annotations

import argparse
import sys

from prevue.engines.errors import AuthError, EngineFailure
from prevue.review import ForkPrUnsupported, run_review


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="prevue", description="Token-efficient AI PR review")
    subparsers = parser.add_subparsers(dest="command", required=True)

    review_parser = subparsers.add_parser(
        "review",
        help="Run AI review on the current pull request",
    )
    review_parser.set_defaults(func=_cmd_review)

    args = parser.parse_args(argv)
    return args.func()


def _cmd_review() -> int:
    try:
        run_review()
    except ForkPrUnsupported as exc:
        print(str(exc), file=sys.stderr)
        return 0
    except (EngineFailure, AuthError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
