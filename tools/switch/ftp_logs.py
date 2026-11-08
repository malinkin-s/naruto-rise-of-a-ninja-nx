#!/usr/bin/env python3
"""Compatibility entry point for compact FTP measurement summaries.

The earlier version wrote full console logs into out/runs/. That is disallowed by
GEMINI.md Log Handling. This entry point now has the same Run ID arguments and
behavior as ftp_run_summary.py and never retains raw logs.
"""

from ftp_run_summary import main


if __name__ == "__main__":
    raise SystemExit(main())
