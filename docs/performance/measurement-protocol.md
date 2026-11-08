# Measurement Protocol

Purpose: compare one module-level hypothesis in the **same** game state. Historical numbers from `docs/port-journal.md` §Measurements and `docs/culling-solutions-log.md` are context, not rows in the new baseline. Do not compare different clocks, scenes, saves or shader-cache states as an A/B result.

## Predeclare a run

Record scenario ID/version, initial save/checkpoint digest, replay digest and expected checkpoints; commit, Build ID, NRO/ELF/shader hashes; console model, firmware, handheld/docked, core mask, CPU/GPU/RAM clocks, 720p or other resolution, TOML hash, forwarder/overlays/background services, temperature or proxy and warm-up policy. Record ambient conditions if available; otherwise mark unknown. Define the start/stop events of the measured segment **before** running. Keep loading, shader warm-up, menus and cutscenes as separately labeled segments.

Use a unique Run ID and the accepted FTP + Sphaira forwarder workflow (`console-run-workflow.md`): the owner transfers files by FTP and launches the four-core/39-bit forwarder, then logs are read through `tools/switch/ftp_run_summary.py`. `tools/switch/nxtest.sh` uses netloader and is not the acceptance path. The collector retains one compact Markdown report per run and no full raw log; `tools/switch/ftp_logs.py` now calls this collector. Do not paste full logs into chat or agent context. Keep binary/profile/optional metric-stream artifacts outside Git with hashes; do not overwrite game files or saves. Screenshots/video are not required for routine performance runs; use them only when log/checkpoint data cannot establish scene equivalence or a visual regression is under investigation.

## Metric selection

Use `metric-catalog.md` as the source-backed map of available counters, subsystem ownership, interpretation limits and the diagnostic decision tree. Treat its availability labels as capability of the installed 0.1.4 binary, then verify actual presence in each run log. The minimum low-overhead triage set is: guest Swaps and host presents, mean FPS, Swap-to-Swap work/pacing/late/hitches, per-thread CPU%, game/render waits, render busy and GPU mean, draws/frame, pipeline creations, clocks/core mask, memory and audio errors. These are **10-second aggregates or snapshots** in 0.1.4. New opt-in source computes segment frame-interval percentiles/1% low in memory; it needs a new build and console overhead validation. Neither path proves simulation drift or a definitive CPU/GPU bottleneck. Record missing values as `not measured`.

Do not enable stack sampling, per-shader GPU timestamps or extra tracing in the headline run until their cost is measured. When diagnosing a specific stage, predeclare the diagnostic mode as a separate config ID and compare it with the low-overhead control. Use the same window markers in all logs; otherwise mark cross-log association as unproven.

### Quick subsystem index

| Question | Primary metric | Currently available | Missing / task |
|---|---|---|---|
| Is gameplay smooth? | Host-present intervals and independent game-clock drift | One-second FPS, 180-frame guest-swap history, host-present counter (`frame_stats.cpp`, `switch_perf.cpp`) | Durable timestamp stream and independent game-clock checkpoint; distinguish guest swap from display present |
| CPU bottleneck? | Busy/wait time on the frame critical path, samples by function | `rex_profile.log` gives per-thread CPU% per window, not per-frame busy ms; 1 kHz stacks are optional (`tools/switch_profile_report.py`) | Per-frame alignment with scenario events and critical-path spans |
| GPU bottleneck? | GPU ms and present interval in same scene | GPU timestamp averages, `[renut]` reports, GPU profile (`frame_stats.cpp`, `gpu/backend/gpu_profile.cpp`) | Stable per-frame export and thermal/clock correlation |
| Draw/renderer cost? | Draws by type, queue/render busy ms | `--naruto_debug_census=true`, `[renut]`, culling counters (`docs/archive/HANDOFF.md` §Next steps; `gpu/d3d/hooks/draw.cpp`) | Stage-level attribution if total render time is ambiguous |
| Memory/IO? | Peak heap/cache, file bytes/misses, load latency | Renut memory report, SDK guest faults/mapping and upload proxies (`gpu/backend/memory_report.cpp`, `sdk/src/ui/switch_perf.cpp`) | Long-run peak/time-series and explicit file/load counters and markers |
| Audio? | Underruns/missing requests | `rex_profile.log` audio line (`sdk/src/ui/switch_perf.cpp`) | Sync with active scene and audible check |

For each module experiment, declare one primary metric, expected direction and smallest meaningful change **before** edit. Record FPS, frame-time distribution when available, CPU/GPU, draw count, memory and error counters as guardrails. A faster module with a visual or audio regression fails acceptance. Use the exact binary for A and B where a runtime toggle exists; otherwise separate Build IDs and identical scenario/config IDs. Interleave A/B order when practical.

## Repetition and variance

Start with pilot repeats of one frozen scenario to estimate natural spread and checkpoint drift. Set the number of confirmation repeats and the effect-size rule from that spread; the number is **TBD**, not an arbitrary universal constant. Keep every valid and invalid run, with reasons. Compare within-scenario medians and spread (range/IQR or bootstrap interval when enough independent repeats exist); show every run ID. A run is invalid if its initial state, route checkpoints, clocks, resolution, shader-cache class or measured segment differs from the declared configuration. Investigate outliers; never silently delete them.

**Steady state:** prewarm until shader/pipeline creation and cache activity settle under a documented rule, then start at the declared game event. Run a separate cold-start experiment when startup hitches matter. The threshold for “settled” is TBD after pilot logs. Stock and overclocked data are separate configurations (`docs/port-journal.md` §Measurements; `rex_profile.log` clocks line).
