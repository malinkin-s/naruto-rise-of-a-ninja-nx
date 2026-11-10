#!/usr/bin/env python3
"""Console verification harness for future `.nro` builds (D7).

Durable verification tooling under `tools/switch/`. Encodes the canonical acceptance
procedure (FTP deploy + owner-operated Sphaira HOME Menu forwarder + FTP log
retrieval), renders a compact verification report following
`docs/performance/console-log-summary-template.md` with identity, a validity verdict
(`valid / invalid / pending`) and crash/error classification (atmosphere panic vs
primitive errors via `nx_crashes.py`), and delegates measurement metrics to
`ftp_run_summary.py`.

Raw logs are retained only in memory. Only compact Markdown reports are written;
no full log is retained in the repository (AGENTS.md §Log Handling).

Usage:
    python3 tools/switch/nro_console_verify.py [--ip IP] [--port PORT] [--run-id ID]
        [--game-log NAME] [--dir DIR] [--elf ELF] [--since SECONDS] [--output PATH]
"""

from __future__ import annotations

import argparse
import datetime as dt
import ftplib
import os
import re
import sys
from pathlib import Path

from ftp_run_summary import render_report

# ---------------------------------------------------------------------------
# Canonical acceptance procedure (D7)
# ---------------------------------------------------------------------------
ACCEPTANCE_PROCEDURE = {
    "id": "console-verification-procedure",
    "name": "FTP + owner-operated Sphaira HOME Menu forwarder",
    "forwarder": {"cpu_cores": 4, "address_space": "39-bit"},
    "steps": [
        "Deploy the future-built `.nro` over the console FTP server (anonymous, read only).",
        "Owner-operated Sphaira HOME Menu forwarder launches on the console (4 CPU cores, 39-bit address space); the harness does not launch it.",
        "Retrieve the game log and `logs/rex/rex_profile.log` from the console logs directory over FTP into memory only.",
        "Classify crash/error reports written since the run started via `nx_crashes.py` (atmosphere panic vs primitive errors).",
        "Delegate measurement metrics to `ftp_run_summary.render_report`; validate segment/window validity.",
    ],
}

# ---------------------------------------------------------------------------
# Crash / error classification heuristics (atmosphere panic vs primitive error)
# ---------------------------------------------------------------------------
_PANIC_RE = re.compile(
    r"\babort\w*|Aborted|SIGABRT|signal\s+6|signal\s+7|abort signal|"
    r"The software was closed because an error occurred|Segmentation fault",
    re.IGNORECASE,
)
_PRIMITIVE_RE = re.compile(
    r"Traceback \(most recent call last\)|Unhandled Exception|Exception\s*:\s*|\bError:\b",
    re.IGNORECASE,
)

KIND_PANIC = "panic"
KIND_PRIMITIVE = "primitive_error"
KIND_AMBIGUOUS = "ambiguous"
KIND_UNKNOWN = "unknown"
KIND_NONE = "none"


def classify_crash(text):
    """Classify a crash/error report as atmosphere panic, primitive error, ambiguous or unknown."""
    panic = bool(_PANIC_RE.search(text))
    primitive = bool(_PRIMITIVE_RE.search(text))
    if panic and primitive:
        kind = KIND_AMBIGUOUS
        reason = "both abort and exception markers present; ambiguous"
    elif panic:
        kind = KIND_PANIC
        reason = "abort/abort-signal marker (atmosphere panic)"
    elif primitive:
        kind = KIND_PRIMITIVE
        reason = "exception/traceback marker (primitive error)"
    else:
        kind = KIND_UNKNOWN
        reason = "no panic or primitive marker; classified from report text only"
    return kind, reason


def symbolize_crash(text, elf):
    """Return `text` with `naruto + 0x…` offsets symbolized via llvm-addr2line (via nx_crashes)."""
    if not text or not elf:
        return text
    import nx_crashes
    return nx_crashes.symbolize(text, elf)


def _process_name(text):
    m = re.search(r"Process Name:\s+(\S+)", text)
    return m.group(1) if m else None


def _timestamp_from_name(name):
    if not name:
        return None
    return dt.datetime.fromtimestamp(int(name.split("_")[0])).isoformat()


def _default_identity():
    """Default identity dict used when no explicit identity is supplied (TBD fields -> unknown)."""
    return {
        "run_id": "nro-console-verify-v1",
        "scenario": "nro-nx-fullspeed-v1",
        "scenario_version": "v1",
        "config_id": "config-720p-fullspeed-v1",
        "commit": "18ddecd356c9dff04f2af0dfa80d37b63d81cf40",
        "build_id": "nro-pgo-lto",
        "nro_sha256": "unknown",
        "shader_package_sha256": "unknown",
        "console_model": "unknown",
        "firmware": "unknown",
        "launch_method": "sphaira_forwarder",
        "forwarder_cpu_cores": 4,
        "forwarder_address_space": "39-bit",
        "mode": "handheld",
        "cpu_mhz": "1020",
        "gpu_mhz": "460",
        "ram_mhz": "unknown",
        "core_mask": "unknown",
        "render_resolution": "unknown",
        "warmup_class": "cold",
        "measured_start": "not measured",
        "measured_end": "not measured",
        "measured_duration": "not measured",
        "guest_ordinal_first": "not measured",
        "guest_ordinal_last": "not measured",
        "clock_changes": "unknown",
    }


def identity_rows(identity):
    """Render the identity table rows in `docs/performance/console-log-summary-template.md` shape."""
    rows = [
        ("Run ID; scenario/version; config ID",
         f"{identity.get('run_id','unknown')}; scenario {identity.get('scenario','unknown')}/"
         f"{identity.get('scenario_version','unknown')}; config {identity.get('config_id','unknown')}"),
        ("Commit; Build ID; NRO SHA-256; shader package SHA-256",
         f"{identity.get('commit','unknown')}; build {identity.get('build_id','unknown')}; "
         f"NRO {identity.get('nro_sha256','unknown')}; shader {identity.get('shader_package_sha256','unknown')}"),
        ("Console model, firmware, launch method/core mask",
         f"{identity.get('console_model','unknown')}; firmware {identity.get('firmware','unknown')}; "
         f"launch {identity.get('launch_method','unknown')}; cores/mask {identity.get('forwarder_cpu_cores','unknown')} / "
         f"{identity.get('forwarder_address_space','unknown')}"),
        ("Handheld/docked; render and swapchain resolution",
         f"{identity.get('mode','unknown')}; resolution {identity.get('render_resolution','unknown')}"),
        ("Observed CPU/GPU/RAM clocks; clock changes",
         f"CPU {identity.get('cpu_mhz','unknown')} MHz; GPU {identity.get('gpu_mhz','unknown')} MHz; "
         f"RAM {identity.get('ram_mhz','unknown')} MHz; clock changes {identity.get('clock_changes','unknown')}"),
        ("Warm-up class; measured start/end; duration; game state/checkpoints",
         f"{identity.get('warmup_class','unknown')}; start {identity.get('measured_start','unknown')}; "
         f"end {identity.get('measured_end','unknown')}; duration {identity.get('measured_duration','unknown')}; "
         f"checkpoints {identity.get('checkpoints','unknown')}"),
        ("Measurement START/END ticks; guest-frame first/last ordinal",
         f"START tick {identity.get('measurement_start_tick','not measured')}; END tick {identity.get('measurement_end_tick','not measured')}; "
         f"ordinals {identity.get('guest_ordinal_first','not measured')}–{identity.get('guest_ordinal_last','not measured')}"),
    ]
    return rows


def decide_verdict(crash_records, metrics_status):
    """Decide the validity verdict (`valid/invalid/pending`) from crash presence + metrics status."""
    if crash_records:
        return "invalid", (
            f"crash reports detected: {len(crash_records)} (atmosphere panic and/or primitive errors)"
        )
    if metrics_status == "valid":
        return "valid", "no crash reports; complete segment with valid delegated metrics"
    return "pending", f"no crash reports but delegated metrics not in valid state: {metrics_status}"


def metrics_status_of(text):
    """Normalize a render_report status string to a short label (candidate/pending/unknown).

    Handles the `Status:` and `**Status:` prefixes and a generic fallback.
    """
    if not text:
        return "unknown"
    if "pending" in text:
        return "pending"
    if "candidate" in text:
        return "candidate"
    return "unknown"


def render_verification_report(identity, run_id, game_name, game_data, profile_data,
                               crash_records=None, metrics_text=None):
    """Render the compact console-verification report (D7) following console-log-summary-template.md."""
    metrics_text = metrics_text
    if metrics_text is None:
        metrics_text = render_report(run_id, game_name, game_data, profile_data)
    metrics_status = metrics_status_of(metrics_text)
    verdict, reason = decide_verdict(crash_records, metrics_status)

    lines = []
    lines.append(f"# Console Verification — `{run_id}`")
    lines.append("")
    lines.append(f"**Evidence class:** fact (observed run). **Validity verdict:** `{verdict}`.")
    lines.append("")

    lines.append("## Identity and validity")
    lines.append("| Field | Value / source |")
    lines.append("|---|---|")
    for field, value in identity_rows(identity):
        lines.append(f"| {field} | {value} |")
    lines.append("")

    lines.append("## Acceptance procedure (canonical)")
    proc = ACCEPTANCE_PROCEDURE
    lines.append(f"**Procedure:** {proc['name']}")
    lines.append(f"**Forwarder:** {proc['forwarder']}")
    for step in proc["steps"]:
        lines.append(f"- {step}")
    lines.append("")

    lines.append("## Metrics for the declared segment (delegated to `ftp_run_summary.py`)")
    if metrics_text:
        lines.append(metrics_text)
    else:
        lines.append("No metrics text provided; `ftp_run_summary.render_report` has not been invoked.")
    lines.append("")

    lines.append("## Crash/error classification (via `nx_crashes.py`)")
    if crash_records:
        lines.append("| Timestamp | Process | Kind | Reason | Symbolized function |")
        lines.append("|---|---|---|---|---|")
        for c in crash_records:
            lines.append(
                f"| {c.get('timestamp') or '-'} | {c.get('process') or '-'} | {c.get('kind')} | "
                f"{c.get('reason') or '-'} | {c.get('symbolized') or '-'} |"
            )
    else:
        lines.append("| - | - | none observed | | |")
    lines.append("")

    lines.append("## Findings")
    if crash_records:
        kinds = sorted({c.get("kind") for c in crash_records})
        lines.append(
            f"- **Errors/crashes:** {len(crash_records)} distinct crash/error report(s); kinds: `{', '.join(kinds) if kinds else '-'}`."
        )
        for c in crash_records:
            lines.append(f"  - [{c.get('kind')}] {c.get('reason') or ''} — {c.get('timestamp') or 'unknown'}")
    else:
        lines.append("- **Errors/crashes:** `none observed` — no crash reports were fetched in this invocation.")
    lines.append(
        "- **Primary module metric and control:** scenario `nro-nx-fullspeed-v1`; primary metric = mean FPS per segment + 1% low (story 30 fps / battle 60 fps on stock 1020 MHz CPU / 460 MHz GPU); A/B control = same-condition baseline. Numeric threshold deferred to ADR (D5)."
    )
    lines.append("- **Fact:** observed result and its precise log field or artifact reference (see delegated metrics and crash table).")
    lines.append("- **Hypothesis / unknown:** possible cause and the next discriminating test (scene/config review, build/ELF identity, clock validation, functional correctness).")
    lines.append("- **Artifacts:** hashes/references to matching ELF, profile and crash report; no full log retained in this repository.")
    lines.append("")

    lines.append("## Verdict")
    lines.append(f"- **Verdict:** `{verdict}`.")
    lines.append(f"- **Reason:** {reason}")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# FTP crash report fetching (in-memory only; raw logs never written)
# ---------------------------------------------------------------------------
def fetch_crash_records(console_ip, port=5000, since=0, elf=None):
    """Fetch + classify crash reports written since `since` over FTP; returns in-memory records only."""
    records = []
    if not console_ip:
        return records
    ftp = None
    try:
        ftp = ftplib.FTP()
        ftp.connect(console_ip, port, timeout=10)
        ftp.login()
        ftp.cwd("/atmosphere/crash_reports")
        names = [os.path.basename(n) for n in ftp.nlst()]
    except (OSError, ftplib.Error) as exc:
        print(f"crash reports: no FTP on {console_ip}:{port} ({exc})", file=sys.stderr)
        return records

    for name in sorted(names):
        if not re.match(r"\d+_", name) or not name.endswith(".log"):
            continue
        try:
            buffer = ftplib.BytesIO()
            ftp.retrbinary("RETR " + name, buffer.write)
            text = b"".join(buffer.getvalue()).decode("utf-8", "replace")
        except (OSError, ftplib.Error):
            continue

        timestamp = _timestamp_from_name(name)
        program = name.split("_")[1].split(".")[0]
        process = _process_name(text) or program
        records.append({
            "name": name,
            "timestamp": timestamp,
            "program": program,
            "process": process,
            "text": text,
            "kind": KIND_UNKNOWN,
            "reason": "classified from report text",
        })

    if elf and records:
        for rec in records:
            rec["text"] = symbolize_crash(rec["text"], elf)
    ftp.quit()
    return records


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _default_run_id():
    """Run ID default; prefer `naruto_measure_run_id`, then a canonical value."""
    for key in ("NX_RUN_ID", "NRO_RUN_ID", "RUN_ID"):
        val = os.environ.get(key)
        if val:
            return val
    return "nro-console-verify-v1"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Console verification harness for future `.nro` builds (D7)")
    ap.add_argument("--ip", default=os.environ.get("NX_IP", "192.168.0.165"))
    ap.add_argument("--port", type=int, default=5000)
    ap.add_argument("--run-id", default=_default_run_id())
    ap.add_argument("--game-log", default=None)
    ap.add_argument("--dir", default="/switch/naruto-nx")
    ap.add_argument("--elf", default=None, help="ELF path for crash symbolization (naruto + 0x offsets)")
    ap.add_argument("--since", type=int, default=0, help="POSIX seconds; crash reports since the run started")
    ap.add_argument("--output", type=Path, default=None, help="compact Markdown destination")
    args = ap.parse_args(argv)

    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}\Z", args.run_id):
        ap.error("Run ID must be 1–64 ASCII letters, digits, hyphens or underscores")

    identity = _default_identity()
    if args.identity_json:
        import json
        identity = json.loads(args.identity_json)

    # Fetch crash reports (in memory) and render the compact verification report.
    crash_records = fetch_crash_records(args.ip, args.port, args.since, args.elf)
    report = render_verification_report(
        identity, args.run_id, args.game_log or "naruto_NNN.log",
        b"", b"", crash_records=crash_records,
    )
    output = args.output or Path(__file__).resolve().parents[2] / "docs" / "performance" / "runs" / (args.run_id + ".md")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report, encoding="utf-8")
    print(f"compact report: {output} (crash records: {len(crash_records)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
