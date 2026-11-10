#!/usr/bin/env python3
"""Validation script for repository documentation and agent state integrity.

Enforces:
1. STATE.md line budget (<=150 lines) and freshness relative to latest app/sdk commits.
2. Fact lines cite an existing Run ID, commit hash or existing file path.
3. Relative links across active documentation (root *.md and docs/**/*.md) are valid.
4. Tasks in docs/tasks/T*.md have required fields and at most one in 'measuring' status.

Exit code 0 on success; non-zero with diagnostic violations on failure.
"""

import argparse
import datetime as dt
from pathlib import Path
import re
import subprocess
import sys


REQUIRED_TASK_FIELDS = [
    "status",
    "module",
    "hypothesis",
    "primary metric",
    "scenario",
    "control run id",
    "candidate run id",
    "scope",
    "regression checks",
    "acceptance rule",
]

ALLOWED_STATUSES = {"draft", "ready", "measuring", "accepted", "rejected", "abandoned"}


def find_repo_root(start=None):
    cur = Path(start or Path.cwd()).resolve()
    for parent in [cur] + list(cur.parents):
        if (parent / ".git").exists() or (parent / "STATE.md").exists():
            return parent
    return cur


def get_latest_commit_date(repo_root, paths=("app", "sdk")):
    try:
        cmd = ["git", "log", "-1", "--format=%cd", "--date=short", "--"] + list(paths)
        res = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True, check=True)
        out = res.stdout.strip()
        if out:
            return dt.date.fromisoformat(out)
    except Exception:
        pass
    return None


def verify_git_commit(repo_root, sha):
    try:
        cmd = ["git", "cat-file", "-e", f"{sha}^{{commit}}"]
        res = subprocess.run(cmd, cwd=repo_root, capture_output=True)
        return res.returncode == 0
    except Exception:
        return False


def check_state_md(repo_root, state_path=None):
    violations = []
    path = state_path or (repo_root / "STATE.md")
    if not path.is_file():
        return [f"STATE.md missing at {path}"]

    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    # 1. Budget check (<= 150 lines)
    if len(lines) > 150:
        violations.append(f"STATE.md line budget exceeded: {len(lines)} lines (max 150)")

    # Date check
    date_m = re.search(r"Updated:\s*(\d{4}-\d\d-\d\d)", text)
    if not date_m:
        violations.append("STATE.md lacks 'Updated: YYYY-MM-DD' header")
    else:
        doc_date = dt.date.fromisoformat(date_m.group(1))
        latest_commit_date = get_latest_commit_date(repo_root)
        if latest_commit_date and doc_date < latest_commit_date:
            violations.append(
                f"STATE.md Updated date ({doc_date}) is older than latest app/sdk commit date ({latest_commit_date})"
            )

    # 2. Fact lines citation check
    run_dir = repo_root / "docs/performance/runs"
    archive_run_dir = repo_root / "docs/archive/runs"

    for i, line in enumerate(lines, 1):
        if not re.search(r"\*\*Fact:\*\*", line, re.IGNORECASE):
            continue

        cited = False

        # Look for explicit Run IDs
        for run_match in re.finditer(r"\b([A-Za-z0-9_-]{4,64})\b", line):
            cand_id = run_match.group(1)
            if (run_dir / f"{cand_id}.md").is_file() or (archive_run_dir / f"{cand_id}.md").is_file():
                cited = True
                break
        if cited:
            continue

        # Look for commit hashes (7 to 40 hex chars)
        for hex_m in re.finditer(r"\b([0-9a-f]{7,40})\b", line, re.IGNORECASE):
            sha = hex_m.group(1)
            if verify_git_commit(repo_root, sha):
                cited = True
                break
        if cited:
            continue

        # Look for file paths mentioned in backticks, parens or brackets
        for path_m in re.finditer(r"[`(]([A-Za-z0-9_./-]+\.[A-Za-z0-9_-]+)[`)]", line):
            cand_path = repo_root / path_m.group(1)
            if cand_path.exists():
                cited = True
                break
        if cited:
            continue

        for dir_m in re.finditer(r"[`(]([A-Za-z0-9_./-]+/)[`)]", line):
            cand_dir = repo_root / dir_m.group(1)
            if cand_dir.exists():
                cited = True
                break
        if cited:
            continue

        violations.append(f"STATE.md:{i} Fact line does not cite a valid Run ID, commit or file: {line.strip()[:80]}")

    return violations


def check_markdown_links(repo_root, include_archive=False):
    violations = []
    md_files = list(repo_root.glob("*.md")) + list((repo_root / "docs").rglob("*.md"))

    for p in md_files:
        if not include_archive and "docs/archive" in p.as_posix():
            continue

        content = p.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(content.splitlines(), 1):
            for m in re.finditer(r"\[([^\]]+)\]\(([^)]+)\)", line):
                link = m.group(2).strip()
                if link.startswith(("http://", "https://", "mailto:", "#")):
                    continue

                if link.startswith("file://"):
                    target_path = link[7:].split("#")[0]
                    resolved = Path(target_path)
                else:
                    target_path = link.split("#")[0]
                    if not target_path:
                        continue
                    resolved = (p.parent / target_path).resolve()
                    if not resolved.exists() and "docs/archive" in p.parts:
                        resolved = (repo_root / target_path).resolve()

                if not resolved.exists():
                    rel_p = p.relative_to(repo_root) if p.is_relative_to(repo_root) else p
                    violations.append(f"{rel_p}:{lineno} broken link -> {link}")

    return violations


def check_tasks(repo_root):
    violations = []
    tasks_dir = repo_root / "docs/tasks"
    if not tasks_dir.is_dir():
        return violations

    measuring_count = 0
    task_files = sorted(tasks_dir.glob("T*.md"))

    for p in task_files:
        text = p.read_text(encoding="utf-8")
        fields_found = {}

        for line in text.splitlines():
            m = re.match(r"^\s*-\s*\*\*([^:]+):\*\*\s*(.*)$", line)
            if m:
                k = m.group(1).strip().lower()
                v = m.group(2).strip()
                # Clean trailing comments like <!-- ... -->
                v = re.sub(r"<!--.*?-->", "", v).strip()
                fields_found[k] = v

        missing = [f for f in REQUIRED_TASK_FIELDS if f not in fields_found]
        if missing:
            violations.append(f"{p.relative_to(repo_root)} missing required fields: {', '.join(missing)}")

        status = fields_found.get("status", "").lower()
        if status and status not in ALLOWED_STATUSES:
            violations.append(f"{p.relative_to(repo_root)} has invalid status '{status}' (allowed: {', '.join(sorted(ALLOWED_STATUSES))})")

        if status == "measuring":
            measuring_count += 1

    if measuring_count > 1:
        violations.append(f"Multiple tasks currently in 'measuring' status ({measuring_count}); at most one allowed")

    return violations


def run_checks(repo_root=None, include_archive=False):
    root = find_repo_root(repo_root)
    all_violations = []

    all_violations.extend(check_state_md(root))
    all_violations.extend(check_markdown_links(root, include_archive=include_archive))
    all_violations.extend(check_tasks(root))

    return all_violations


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo-root", type=Path, default=None, help="repository root path")
    ap.add_argument("--include-archive", action="store_true", help="also check links inside docs/archive/")
    args = ap.parse_args()

    root = find_repo_root(args.repo_root)
    violations = run_checks(root, include_archive=args.include_archive)

    if violations:
        print(f"FAILED: {len(violations)} documentation / workflow violation(s) found:\n", file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        return 1

    print("OK: all documentation, state integrity, links, and task constraints passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
