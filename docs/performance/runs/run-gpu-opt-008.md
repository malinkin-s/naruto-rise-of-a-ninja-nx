# Console Measurement — `run-gpu-opt-008`

Evidence: FTP game log `naruto_008.log` (SHA-256 `3fe173f43602e2fa47e010a7c4d838126f0b20067027dccb7d1a2fc12e66307b`); CPU log `logs/rex/rex_profile.log` (SHA-256 `da9fc8e802e4453dff35990a9c3e1d0b08f0510c1c86268fb511db432e75fa40`). Raw logs were held in memory only.

**Status: candidate (scene/config review required).** Segment: 2026-11-09T02:49:27.499000 to 2026-11-09T02:49:57.520000 (game-log clock); monotonic ticks `504720795931`–`505297204162`; guest ordinals 2144–2930.
Full windows inside segment: 2 Renut, 2 CPU. The run still requires save, route, build, config and observed clock validation.

| Event stream | Events | Intervals | FPS | p50 / p95 / p99 / max interval (ms) | 1% low FPS |
|---|---:|---:|---:|---|---:|
| guest | 787 | 786 | 26.244 | 37.793 / 42.812 / 47.199 / 64.685 | 19.338 |
| present | 788 | 787 | 26.278 | 37.262 / 44.611 / 57.128 / 63.433 | 16.561 |

1% low = 1000 divided by the mean duration of the slowest ceil(1%) intervals. Intervals are between host-present callbacks or guest Swaps; panel scanout is not measured. Overflow invalidates the percentiles.

| Renut tick window | Log time at end | Frames | FPS | Render busy mean ms/frame | GPU mean ms/frame | Draws/frame |
|---|---|---:|---:|---:|---:|---:|
| 504790345826–504982958792 | 2026-11-09T02:49:41.153000 | 260 | 25.92 | 35.77 | 33.75 | 2562.8 |
| 504982958792–505175016306 | 2026-11-09T02:49:51.156000 | 267 | 26.69 | 33.34 | 32.13 | 2352.2 |

| CPU tick window | Profile FPS | Total CPU% | Main CPU% | Render CPU% | Clocks CPU/GPU/RAM MHz | Cores / mask | Audio misses |
|---|---:|---:|---:|---:|---|---|---:|
| 504720813102–504912831715 | 26.0 | 434.0 | 116.2 | 129.1 | 1020.0/460.8/1600.0 | 4 / 0xF | 0.0 |
| 504927128264–505119141071 | 28.9 | 334.0 | 95.9 | 94.2 | 1020.0/460.8/1600.0 | 4 / 0xF | 0.0 |

| Modular Culling (Batch5) | Batches tested/fr | Batches culled/fr (%) | Items tested/fr | Items culled/fr (%) |
|---|---:|---:|---:|---:|
| Current window | 0.0 | 0.0 (0.0%) | 0.0 | 0.0 (0.0%) |
| Current window | 0.0 | 0.0 (0.0%) | 0.0 | 0.0 (0.0%) |
| Current window | 0.0 | 0.0 (0.0%) | 0.0 | 0.0 (0.0%) |
| Current window | 0.0 | 0.0 (0.0%) | 0.0 | 0.0 (0.0%) |
| Current window | 0.0 | 0.0 (0.0%) | 0.0 | 0.0 (0.0%) |

| Culling Distances | <50m | 50–100m | 100–150m | 150–200m | >200m |
|---|---:|---:|---:|---:|---:|
| Distance histogram | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| Distance histogram | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| Distance histogram | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| Distance histogram | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| Distance histogram | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |

## Bottleneck Verdict

- **Primary Limit: MAIN_CPU_BOUND** (Main XThread: ~33.2 ms / 95.9% of Core 0 vs 33.3 ms target budget)
- **Secondary Factor: DRAW_CALL_VOLUME** (2457 draws/frame; scene complexity)
- **GPU Status:** Headroom available (32.9 ms GPU time; 0.4 ms margin to 30 FPS target)
- **Prescribed Action:** Profile guest functions with `tools/switch_profile_report.py`; tighten modular culling `max_dist` in `sub_820FD5F8`.

**Unknown until the run metadata and checkpoints are reviewed:** exact scene, build/ELF identity, console model, mode, shader-cache state, simulation-clock drift, functional correctness and whether counters perturb timing.
