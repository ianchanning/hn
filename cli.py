#!/usr/bin/env python3
"""Story-agnostic CLI forwarder for the Hacker News Epistemic Observatory.

Delegates execution to hn-comments/cli.py.
"""

from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
HN_COMMENTS_DIR = HERE / "hn-comments"
if str(HN_COMMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(HN_COMMENTS_DIR))

from cli import main, run_cli  # noqa: E402

if __name__ == "__main__":
    run_cli()
