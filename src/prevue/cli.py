"""CLI entrypoint — `prevue review` drives the walking skeleton loop."""

from __future__ import annotations

import argparse
import sys

from prevue.commands import run_command
from prevue.engines.errors import AuthError, EngineFailure
from prevue.gate_validate import run_gate_revalidate, run_materialize_comment_event
from prevue.preflight import run_preflight_noop_check
from prevue.review import ForkPrUnsupported, run_review


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="prevue", description="Token-efficient AI PR review")
    subparsers = parser.add_subparsers(dest="command", required=True)

    review_parser = subparsers.add_parser(
        "review",
        help="Run AI review on the current pull request",
    )
    review_parser.set_defaults(func=_cmd_review)

    command_parser = subparsers.add_parser(
        "command",
        help="Handle a /prevue issue comment command",
    )
    command_parser.set_defaults(func=_cmd_command)

    preflight_parser = subparsers.add_parser(
        "preflight",
        help="Print true/false for workflow engine-install skip (same-SHA noop)",
    )
    preflight_parser.set_defaults(func=_cmd_preflight)

    gate_revalidate_parser = subparsers.add_parser(
        "gate-revalidate",
        help="Revalidate repository_dispatch payload before privileged checkout",
    )
    gate_revalidate_parser.set_defaults(func=run_gate_revalidate)

    materialize_parser = subparsers.add_parser(
        "materialize-comment-event",
        help="Write synthetic issue_comment event JSON for command dispatch",
    )
    materialize_parser.set_defaults(func=run_materialize_comment_event)

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


def _cmd_command() -> int:
    try:
        return run_command()
    except ForkPrUnsupported as exc:
        print(str(exc), file=sys.stderr)
        return 0
    except (EngineFailure, AuthError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1


def _cmd_preflight() -> int:
    try:
        print("true" if run_preflight_noop_check() else "false")
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
