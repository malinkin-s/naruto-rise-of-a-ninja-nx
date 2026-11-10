#!/usr/bin/env python3
"""Read a measured forwarder run over FTP and retain only a compact Markdown report.

The raw game and CPU logs exist only in memory. A report is *pending* unless both
logs carry the requested Run ID and have complete windows inside its segment.

When --control <run_id> is passed, the report appends an observation table comparing
primary metrics against that control run's saved Markdown report.
"""

import argparse
import datetime as dt
import ftplib
import hashlib
from io import BytesIO
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[2]
ID_RE = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")
STAMP_RE = re.compile(r"^\[(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d+)\]")
CPU_MARK_RE = re.compile(r"\[measure\] run=([A-Za-z0-9_-]+) cpu_window_tick_start=(\d+) cpu_window_tick_end=(\d+) tick_hz=(\d+)")
RENUT_MARK_RE = re.compile(r"\[measure\] run=([A-Za-z0-9_-]+) renut_window_tick_start=(\d+) renut_window_tick_end=(\d+) tick_hz=(\d+)")
SEGMENT_RE = re.compile(r"\[measure\] run=([A-Za-z0-9_-]+) (START|END)\b")
RENUT_RE = re.compile(r"\[renut\] (\d+(?:\.\d+)?) s: (\d+) game frames \(([\d.]+) fps\), render thread busy ([\d.]+) ms a frame \(\d+ frames\), GPU ([\d.]+) ms a frame \(\d+ frames\); (\d+) draws")
THREAD_RE = re.compile(r'^-- thread \d+ "([^"]+)": CPU ([\d.]+)%')
PROFILE_RE = re.compile(r'^==== ([\d.]+) s \| mode: ([^|]+) \| game ([\d.]+) fps \| CPU total ([\d.]+)%')
CLOCK_RE = re.compile(r'clocks: CPU ([\d.]+) MHz, GPU ([\d.]+) MHz, memory ([\d.]+) MHz \| process cores (\d+) \(mask (0x[\dA-Fa-f]+)\)')
AUDIO_RE = re.compile(r'audio: [\d.]+ client blocks mixed, ([\d.]+) requests without data')
CULL_BATCH_RE = re.compile(r"\[naruto-cull\] Batch5: Batches tested:\s*([\d.]+)/fr,\s*culled:\s*([\d.]+)/fr\s*\(([\d.]+)%\)\s*\|\s*Items tested:\s*([\d.]+)/fr,\s*culled:\s*([\d.]+)/fr\s*\(([\d.]+)%\)")
CULL_DIST_RE = re.compile(r"\[naruto-cull\] Batch5Dist: <50m:\s*([\d.]+),\s*50-100m:\s*([\d.]+),\s*100-150m:\s*([\d.]+),\s*150-200m:\s*([\d.]+),\s*>200m:\s*([\d.]+)")


def read_ftp(ftp, path):
    buffer = BytesIO()
    ftp.retrbinary("RETR " + path, buffer.write)
    return buffer.getvalue()


def latest_game_log(ftp, logs):
    ftp.cwd(logs)
    names = [Path(n).name for n in ftp.nlst()]
    numbered = [(int(m.group(1)), n) for n in names if (m := re.fullmatch(r"naruto_(\d+)\.log", n))]
    if not numbered:
        raise ValueError("no naruto_NNN.log in the console logs directory")
    return max(numbered)[1]


def stamp(line):
    m = STAMP_RE.match(line)
    return dt.datetime.fromisoformat(m.group(1)) if m else None


def segment(game, run_id):
    starts, ends = [], []
    for line in game.splitlines():
        m = SEGMENT_RE.search(line)
        if m and m.group(1) == run_id and stamp(line):
            (starts if m.group(2) == "START" else ends).append((stamp(line), line))
    if not starts or not ends:
        return None
    pairs = []
    for s_time, s_line in starts:
        s_tick_m = re.search(r"\btick=(\d+)", s_line)
        if not s_tick_m:
            continue
        s_tick = s_tick_m.group(1)
        for e_time, e_line in ends:
            if e_time <= s_time:
                continue
            e_ticks = re.search(r"\btick_start=(\d+) tick_end=(\d+)", e_line)
            if e_ticks and e_ticks.group(1) == s_tick:
                pairs.append((s_time, e_time, int(s_tick), int(e_ticks.group(2)), e_line))
    if not pairs:
        return None
    return pairs[-1]


def culling_info(game, start_time, end_time):
    batch_lines = []
    dist_lines = []
    for line in game.splitlines():
        t = stamp(line)
        if not t or t < start_time or t > end_time:
            continue
        if m := CULL_BATCH_RE.search(line):
            batch_lines.append(m.groups())
        elif m := CULL_DIST_RE.search(line):
            dist_lines.append(m.groups())
    return batch_lines, dist_lines


def is_nonzero_cull(groups):
    return any(float(x) > 0.0 for x in groups)


def game_windows(game, run_id, start_tick, end_tick):
    result = []
    pending = None
    for line in game.splitlines():
        marker = RENUT_MARK_RE.search(line)
        if marker:
            pending = (int(marker.group(2)), int(marker.group(3)), int(marker.group(4))) if marker.group(1) == run_id else None
            continue
        m, when = RENUT_RE.search(line), stamp(line)
        if not m or not when or not pending:
            continue
        window_start, window_end, hz = pending
        pending = None
        if start_tick <= window_start < window_end <= end_tick and hz > 0:
            frames = int(m.group(2))
            if frames:
                result.append((window_start, window_end, hz, when, frames, float(m.group(3)),
                               float(m.group(4)), float(m.group(5)), int(m.group(6)) / frames))
    return result


def cpu_windows(profile, run_id, start_tick, end_tick):
    result, current = [], None
    for line in profile.splitlines():
        marker = CPU_MARK_RE.search(line)
        if marker:
            if current:
                result.append(current)
            current = None
            if marker.group(1) == run_id and int(marker.group(2)) >= start_tick and int(marker.group(3)) <= end_tick:
                current = {"start": int(marker.group(2)), "end": int(marker.group(3)), "hz": int(marker.group(4)), "threads": {}}
            continue
        if current is None:
            continue
        if m := PROFILE_RE.search(line):
            current.update(seconds=float(m.group(1)), mode=m.group(2).strip(), fps=float(m.group(3)), cpu=float(m.group(4)))
        elif m := CLOCK_RE.search(line):
            current.update(cpu_mhz=float(m.group(1)), gpu_mhz=float(m.group(2)), ram_mhz=float(m.group(3)), cores=int(m.group(4)), mask=m.group(5))
        elif m := THREAD_RE.search(line):
            current["threads"][m.group(1)] = float(m.group(2))
        elif m := AUDIO_RE.search(line):
            current["audio_misses"] = float(m.group(1))
    if current:
        result.append(current)
    return [r for r in result if "fps" in r and "cpu_mhz" in r]


def metric(end_line, name):
    m = re.search(r"\b" + re.escape(name) + r"=([A-Za-z0-9.]+)", end_line)
    return m.group(1) if m else "unknown"


def parse_run_report_metrics(report_text):
    """Extract primary scalar metrics from an existing run report."""
    res = {}
    m = re.search(r"^\|\s*guest\s*\|\s*\d+\s*\|\s*\d+\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*/\s*([\d.]+)\s*/\s*([\d.]+)", report_text, re.MULTILINE)
    if m:
        res["guest_fps"] = float(m.group(1))
        res["guest_p50"] = float(m.group(2))
        res["guest_p95"] = float(m.group(3))
        res["guest_p99"] = float(m.group(4))
    m = re.search(r"^\|\s*present\s*\|\s*\d+\s*\|\s*\d+\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*/\s*([\d.]+)\s*/\s*([\d.]+)", report_text, re.MULTILINE)
    if m:
        res["present_fps"] = float(m.group(1))
        res["present_p50"] = float(m.group(2))
        res["present_p95"] = float(m.group(3))
        res["present_p99"] = float(m.group(4))

    renut_rows = re.findall(r"^\|\s*\d+–\d+\s*\|\s*[^|]+\|\s*\d+\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|", report_text, re.MULTILINE)
    if renut_rows:
        res["renut_fps"] = sum(float(r[0]) for r in renut_rows) / len(renut_rows)
        res["render_busy_ms"] = sum(float(r[1]) for r in renut_rows) / len(renut_rows)
        res["gpu_ms"] = sum(float(r[2]) for r in renut_rows) / len(renut_rows)
        res["draws_per_frame"] = sum(float(r[3]) for r in renut_rows) / len(renut_rows)

    cpu_rows = re.findall(r"^\|\s*\d+–\d+\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+|unknown)\s*\|\s*([\d.]+|unknown)\s*\|", report_text, re.MULTILINE)
    if cpu_rows:
        res["profile_fps"] = sum(float(r[0]) for r in cpu_rows) / len(cpu_rows)
        res["total_cpu"] = sum(float(r[1]) for r in cpu_rows) / len(cpu_rows)
        main_vals = [float(r[2]) for r in cpu_rows if r[2] != "unknown"]
        if main_vals:
            res["main_cpu"] = sum(main_vals) / len(main_vals)
        render_vals = [float(r[3]) for r in cpu_rows if r[3] != "unknown"]
        if render_vals:
            res["render_cpu"] = sum(render_vals) / len(render_vals)
    return res


def render_comparison_table(candidate_metrics, control_metrics, control_id):
    """Render an observation comparison against a control run report."""
    rows = [
        ("Guest FPS (Swap)", "guest_fps", "↑", True),
        ("Guest p50 interval (ms)", "guest_p50", "↓", False),
        ("Guest p99 interval (ms)", "guest_p99", "↓", False),
        ("Present FPS", "present_fps", "↑", True),
        ("Present p50 interval (ms)", "present_p50", "↓", False),
        ("Present p99 interval (ms)", "present_p99", "↓", False),
        ("Render busy mean (ms)", "render_busy_ms", "↓", False),
        ("GPU mean (ms)", "gpu_ms", "↓", False),
        ("Draws / frame", "draws_per_frame", "—", None),
        ("Main CPU %", "main_cpu", "↓", False),
        ("Render CPU %", "render_cpu", "↓", False),
    ]
    out = [
        f"## Comparison against Control (`{control_id}`)",
        "",
        "> [!NOTE]",
        "> Observation only. Scene, save, route and TOML identity must match before attributing any delta to code changes.",
        "",
        f"| Metric | Control (`{control_id}`) | Candidate | Δ | Desired |",
        "|---|---:|---:|---:|:---:|",
    ]
    for label, key, desired, higher_better in rows:
        c_val = control_metrics.get(key)
        k_val = candidate_metrics.get(key)
        if c_val is None or k_val is None:
            continue
        delta = k_val - c_val
        sign = "+" if delta > 0 else ""
        out.append(f"| {label} | {c_val:.2f} | {k_val:.2f} | {sign}{delta:.2f} | {desired} |")
    return "\n".join(out)


def render_report(run_id, game_name, game_data, profile_data, control_id=None, control_report_text=None):
    game = game_data.decode("utf-8", "replace")
    profile = profile_data.decode("utf-8", "replace")
    seg = segment(game, run_id)
    lines = [f"# Console Measurement — `{run_id}`", "",
             "Evidence: FTP game log `" + game_name + "` (SHA-256 `" + hashlib.sha256(game_data).hexdigest() +
             "`); CPU log `logs/rex/rex_profile.log` (SHA-256 `" + hashlib.sha256(profile_data).hexdigest() + "`). Raw logs were held in memory only.", ""]
    if seg is None:
        lines += ["**Status: pending.** A unique matching START/END segment with consistent ticks was not found in the game log.",
                  "No baseline or cross-log conclusion is claimed.", ""]
        return "\n".join(lines)
    start, end, tick_start, tick_end, end_line = seg
    gw = game_windows(game, run_id, tick_start, tick_end)
    cw = cpu_windows(profile, run_id, tick_start, tick_end)
    needed = ("guest_events", "guest_intervals", "guest_fps", "present_events", "present_intervals", "present_fps")
    same_tick_hz = len({w[2] for w in gw} | {w["hz"] for w in cw}) == 1
    valid = (bool(gw and cw) and same_tick_hz and tick_end > tick_start and metric(end_line, "overflow") == "false"
             and all(metric(end_line, name) != "unknown" for name in needed))
    lines += [f"**Status: {'candidate (scene/config review required)' if valid else 'pending'}.** Segment: {start.isoformat()} to {end.isoformat()} (game-log clock); monotonic ticks `{tick_start}`–`{tick_end}`; guest ordinals {metric(end_line, 'guest_ordinal_first')}–{metric(end_line, 'guest_ordinal_last')}.",
              f"Full windows inside segment: {len(gw)} Renut, {len(cw)} CPU. The run still requires save, route, build, config and observed clock validation.", "",
              "| Event stream | Events | Intervals | FPS | p50 / p95 / p99 / max interval (ms) | 1% low FPS |",
              "|---|---:|---:|---:|---|---:|"]
    for kind in ("guest", "present"):
        lines.append(f"| {kind} | {metric(end_line, kind+'_events')} | {metric(end_line, kind+'_intervals')} | {metric(end_line, kind+'_fps')} | "
                     f"{metric(end_line, kind+'_p50')} / {metric(end_line, kind+'_p95')} / {metric(end_line, kind+'_p99')} / {metric(end_line, kind+'_max')} | {metric(end_line, kind+'_1pct_low')} |")
    lines += ["", "1% low = 1000 divided by the mean duration of the slowest ceil(1%) intervals. Intervals are between host-present callbacks or guest Swaps; panel scanout is not measured. Overflow invalidates the percentiles.", "",
              "| Renut tick window | Log time at end | Frames | FPS | Render busy mean ms/frame | GPU mean ms/frame | Draws/frame |",
              "|---|---|---:|---:|---:|---:|---:|"]
    for window_start, window_end, hz, when, frames, fps, render, gpu, draws in gw:
        lines.append(f"| {window_start}–{window_end} | {when.isoformat()} | {frames} | {fps:.2f} | {render:.2f} | {gpu:.2f} | {draws:.1f} |")
    if not gw:
        lines.append("| not measured: no full tick-aligned Renut window | | | | | | |")
    lines += ["", "| CPU tick window | Profile FPS | Total CPU% | Main CPU% | Render CPU% | Clocks CPU/GPU/RAM MHz | Cores / mask | Audio misses |",
              "|---|---:|---:|---:|---:|---|---|---:|"]
    for w in cw:
        main = next((v for n, v in w["threads"].items() if n.startswith("Main XThread")), None)
        render = next((v for n, v in w["threads"].items() if n.lower().startswith("renut render")), None)
        value = lambda v: str(v) if v is not None else "unknown"
        lines.append(f"| {w['start']}–{w['end']} | {w['fps']:.1f} | {w['cpu']:.1f} | {value(main)} | {value(render)} | "
                     f"{w['cpu_mhz']}/{w['gpu_mhz']}/{w['ram_mhz']} | {w['cores']} / {w['mask']} | {value(w.get('audio_misses'))} |")
    if not cw:
        lines.append("| not measured: no full CPU window | | | | | | | |")

    batches, dists = culling_info(game, start, end)
    nonzero_batches = [b for b in batches if is_nonzero_cull(b)]
    nonzero_dists = [d for d in dists if is_nonzero_cull(d)]
    if nonzero_batches or nonzero_dists:
        if nonzero_batches:
            b = nonzero_batches[-1]
            lines += ["", "| Modular Culling (Batch5) | Batches tested/fr | Batches culled/fr (%) | Items tested/fr | Items culled/fr (%) |",
                      "|---|---:|---:|---:|---:|",
                      f"| Segment window | {b[0]} | {b[1]} ({b[2]}%) | {b[3]} | {b[4]} ({b[5]}%) |"]
        if nonzero_dists:
            d = nonzero_dists[-1]
            lines += ["", "| Culling Distances | <50m | 50–100m | 100–150m | 150–200m | >200m |",
                      "|---|---:|---:|---:|---:|---:|",
                      f"| Distance histogram | {d[0]} | {d[1]} | {d[2]} | {d[3]} | {d[4]} |"]

    lines += ["", "**Unknown until the run metadata and checkpoints are reviewed:** exact scene, build/ELF identity, console model, mode, shader-cache state, simulation-clock drift, functional correctness and whether counters perturb timing.", ""]

    if control_id and control_report_text:
        candidate_text = "\n".join(lines)
        candidate_m = parse_run_report_metrics(candidate_text)
        control_m = parse_run_report_metrics(control_report_text)
        lines += [render_comparison_table(candidate_m, control_m, control_id), ""]

    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("run_id", help="unique Run ID configured in naruto_measure_run_id")
    ap.add_argument("--control", help="control Run ID; reads docs/performance/runs/<control>.md for delta table")
    ap.add_argument("--ip", default="192.168.0.165")
    ap.add_argument("--port", type=int, default=5000)
    ap.add_argument("--dir", default="/switch/naruto-nx")
    ap.add_argument("--game-log", help="specific naruto_NNN.log; default is highest numbered")
    ap.add_argument("--output", type=Path, help="compact Markdown destination")
    args = ap.parse_args()
    if not ID_RE.fullmatch(args.run_id):
        ap.error("Run ID must be 1–64 ASCII letters, digits, hyphens or underscores")
    if args.control and not ID_RE.fullmatch(args.control):
        ap.error("--control Run ID must be 1–64 ASCII letters, digits, hyphens or underscores")

    control_text = None
    if args.control:
        control_path = ROOT / "docs/performance/runs" / (args.control + ".md")
        if not control_path.is_file():
            ap.error(f"control report does not exist: {control_path}")
        control_text = control_path.read_text(encoding="utf-8")

    logs = args.dir.rstrip("/") + "/logs"
    try:
        with ftplib.FTP() as ftp:
            ftp.connect(args.ip, args.port, timeout=15)
            ftp.login()
            name = args.game_log or latest_game_log(ftp, logs)
            if not re.fullmatch(r"naruto_\d+\.log", name):
                ap.error("--game-log must be a naruto_NNN.log basename")
            game = read_ftp(ftp, logs + "/" + name)
            profile = read_ftp(ftp, logs + "/rex/rex_profile.log")
    except (OSError, ftplib.Error, ValueError) as exc:
        print(f"FTP collection failed: {exc}", file=sys.stderr)
        return 1
    report = render_report(args.run_id, name, game, profile, control_id=args.control, control_report_text=control_text)
    output = args.output or ROOT / "docs/performance/runs" / (args.run_id + ".md")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report, encoding="utf-8")
    print(f"compact report: {output} ({len(game)} game-log bytes and {len(profile)} profile bytes parsed in memory)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
