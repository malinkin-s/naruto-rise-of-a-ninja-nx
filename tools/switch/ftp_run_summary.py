#!/usr/bin/env python3
"""Read a measured forwarder run over FTP and retain only a compact Markdown report.

The raw game and CPU logs exist only in memory. A report is *pending* unless both
logs carry the requested Run ID and have complete windows inside its segment.
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


def classify_bottleneck(gw, cw, end_line):
    main_cpu = None
    render_cpu = None
    draw_thread_cpu = None
    fps = None
    for w in cw:
        if "fps" in w:
            fps = w["fps"]
        for name, val in w["threads"].items():
            if name.startswith("Main XThread"):
                main_cpu = val
            elif name.lower().startswith("renut render"):
                render_cpu = val
            elif "820F02C0" in name:
                draw_thread_cpu = val

    mean_draws = sum(w[8] for w in gw) / len(gw) if gw else (float(metric(end_line, "draws_per_frame")) if metric(end_line, "draws_per_frame") != "unknown" else 0.0)
    gpu_ms = sum(w[7] for w in gw) / len(gw) if gw else (float(metric(end_line, "gpu_ms")) if metric(end_line, "gpu_ms") != "unknown" else 0.0)
    render_busy_ms = sum(w[6] for w in gw) / len(gw) if gw else (float(metric(end_line, "render_busy_ms")) if metric(end_line, "render_busy_ms") != "unknown" else 0.0)

    main_ms = (main_cpu * 10.0 / fps) if (main_cpu and fps and fps > 0) else 0.0

    verdict = ["## Bottleneck Verdict", ""]
    if mean_draws and mean_draws < 200:
        verdict.append("> [!WARNING]\n> Low draw count detected (<200 draws/frame). Scene is likely a 2D menu or loading screen, not the Leaf Village gameplay.\n")

    if main_ms >= 32.0 or (main_cpu and main_cpu >= 88.0):
        verdict.append(f"- **Primary Limit: MAIN_CPU_BOUND** (Main XThread: ~{main_ms:.1f} ms / {main_cpu:.1f}% of Core 0 vs 33.3 ms target budget)")
        if mean_draws and mean_draws > 1400:
            verdict.append(f"- **Secondary Factor: DRAW_CALL_VOLUME** ({mean_draws:.0f} draws/frame; scene complexity)")
        if gpu_ms:
            margin = 33.33 - gpu_ms
            verdict.append(f"- **GPU Status:** Headroom available ({gpu_ms:.1f} ms GPU time; {margin:.1f} ms margin to 30 FPS target)")
        verdict.append("- **Prescribed Action:** Profile guest functions with `tools/switch_profile_report.py`; tighten modular culling `max_dist` in `sub_820FD5F8`.")
    elif gpu_ms >= 30.0:
        verdict.append(f"- **Primary Limit: GPU_BOUND** (GPU execution: {gpu_ms:.1f} ms at 460 MHz vs 33.3 ms target)")
        verdict.append("- **Prescribed Action:** Profile GPU passes with `renut_gpu_profile = 10.0`.")
    elif render_busy_ms >= 26.0:
        verdict.append(f"- **Primary Limit: RENDER_DRIVER_BOUND** (Render thread busy: {render_busy_ms:.1f} ms)")
        verdict.append("- **Prescribed Action:** Check pipeline cache and command submission in Renut.")
    elif fps and fps >= 29.0:
        verdict.append("- **Status: PASS_30FPS** (Engine is meeting the 30 FPS target within tolerance).")
    else:
        verdict.append("- **Status: PACING_OR_MIXED** (Frame time variation or pacing slip without a dominant single-stage limit).")
    return "\n".join(verdict)


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


def render_report(run_id, game_name, game_data, profile_data):
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
    if batches or dists:
        lines += ["", "| Modular Culling (Batch5) | Batches tested/fr | Batches culled/fr (%) | Items tested/fr | Items culled/fr (%) |",
                  "|---|---:|---:|---:|---:|"]
        for b in batches:
            lines.append(f"| Current window | {b[0]} | {b[1]} ({b[2]}%) | {b[3]} | {b[4]} ({b[5]}%) |")
        if dists:
            lines += ["", "| Culling Distances | <50m | 50–100m | 100–150m | 150–200m | >200m |",
                      "|---|---:|---:|---:|---:|---:|"]
            for d in dists:
                lines.append(f"| Distance histogram | {d[0]} | {d[1]} | {d[2]} | {d[3]} | {d[4]} |")

    lines += ["", classify_bottleneck(gw, cw, end_line), ""]
    lines += ["**Unknown until the run metadata and checkpoints are reviewed:** exact scene, build/ELF identity, console model, mode, shader-cache state, simulation-clock drift, functional correctness and whether counters perturb timing.", ""]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("run_id", help="unique Run ID configured in naruto_measure_run_id")
    ap.add_argument("--ip", default="192.168.0.165")
    ap.add_argument("--port", type=int, default=5000)
    ap.add_argument("--dir", default="/switch/naruto-nx")
    ap.add_argument("--game-log", help="specific naruto_NNN.log; default is highest numbered")
    ap.add_argument("--output", type=Path, help="compact Markdown destination")
    args = ap.parse_args()
    if not ID_RE.fullmatch(args.run_id):
        ap.error("Run ID must be 1–64 ASCII letters, digits, hyphens or underscores")
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
    report = render_report(args.run_id, name, game, profile)
    output = args.output or ROOT / "docs/performance/runs" / (args.run_id + ".md")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report, encoding="utf-8")
    print(f"compact report: {output} ({len(game)} game-log bytes and {len(profile)} profile bytes parsed in memory)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
