# Console Measurement — `pilot-village-view-001`

Evidence: FTP game log `naruto_001.log` (SHA-256 `d83ca4eb1c2c39c15e96f78ebb509c907bf57c802d87bf107d7ae3aa7edaedb6`); CPU log `logs/rex/rex_profile.log` (SHA-256 `2ab15d925b214347695509306e578429af759c085ba9cbf580882ab82bb13f0b`). Raw logs were held in memory only.

**Status: candidate (scene/config review required).** Segment: 2026-11-08T16:50:59.918000 to 2026-11-08T16:51:29.934000 (game-log clock); monotonic ticks `6883313273103`–`6883889572832`; guest ordinals 1743–2523.
Full windows inside segment: 2 Renut, 2 CPU. The run still requires save, route, build, config and observed clock validation.

| Event stream | Events | Intervals | FPS | p50 / p95 / p99 / max interval (ms) | 1% low FPS |
|---|---:|---:|---:|---|---:|
| guest | 781 | 780 | 26.043 | 35.659 / 44.790 / 105.879 / 344.738 | 4.805 |
| present | 782 | 781 | 26.051 | 36.311 / 46.930 / 87.618 / 425.914 | 4.505 |

1% low = 1000 divided by the mean duration of the slowest ceil(1%) intervals. Intervals are between host-present callbacks or guest Swaps; panel scanout is not measured. Overflow invalidates the percentiles.

| Renut tick window | Log time at end | Frames | FPS | Render busy mean ms/frame | GPU mean ms/frame | Draws/frame |
|---|---|---:|---:|---:|---:|---:|
| 6883444454787–6883636920665 | 2026-11-08T16:51:16.775000 | 272 | 27.13 | 27.58 | 29.88 | 1951.0 |
| 6883636920665–6883829563033 | 2026-11-08T16:51:26.808000 | 272 | 27.11 | 27.01 | 29.93 | 1960.5 |

| CPU tick window | Profile FPS | Total CPU% | Main CPU% | Render CPU% | Clocks CPU/GPU/RAM MHz | Cores / mask | Audio misses |
|---|---:|---:|---:|---:|---|---|---:|
| 6883315107031–6883507127859 | 24.1 | 266.0 | 77.4 | 71.9 | 1020.0/460.8/1600.0 | 4 / 0xF | 0.0 |
| 6883507791736–6883699815993 | 27.2 | 284.0 | 91.6 | 72.3 | 1020.0/460.8/1600.0 | 4 / 0xF | 0.0 |

| Modular Culling (Batch5) | Batches tested/fr | Batches culled/fr (%) | Items tested/fr | Items culled/fr (%) |
|---|---:|---:|---:|---:|
| Current window | 0.0 | 0.0 (0.0%) | 2504.4 | 960.0 (38.3%) |
| Current window | 0.0 | 0.0 (0.0%) | 2506.6 | 961.3 (38.4%) |
| Current window | 0.0 | 0.0 (0.0%) | 2491.0 | 950.8 (38.2%) |
| Current window | 0.0 | 0.0 (0.0%) | 2492.0 | 949.0 (38.1%) |
| Current window | 0.0 | 0.0 (0.0%) | 2492.0 | 949.0 (38.1%) |

| Culling Distances | <50m | 50–100m | 100–150m | 150–200m | >200m |
|---|---:|---:|---:|---:|---:|
| Distance histogram | 301.0 | 463.0 | 620.5 | 824.6 | 290.3 |
| Distance histogram | 301.4 | 462.2 | 620.9 | 828.1 | 289.0 |
| Distance histogram | 295.2 | 463.0 | 621.0 | 817.8 | 289.0 |
| Distance histogram | 298.0 | 463.0 | 621.0 | 816.0 | 289.0 |
| Distance histogram | 298.0 | 463.0 | 621.0 | 816.0 | 289.0 |

## Bottleneck Verdict

- **Primary Limit: MAIN_CPU_BOUND** (Main XThread: ~33.7 ms / 91.6% of Core 0 vs 33.3 ms target budget)
- **Secondary Factor: DRAW_CALL_VOLUME** (1956 draws/frame; scene complexity)
- **GPU Status:** Headroom available (29.9 ms GPU time; 3.4 ms margin to 30 FPS target)
- **Prescribed Action:** Profile guest functions with `tools/switch_profile_report.py`; tighten modular culling `max_dist` in `sub_820FD5F8`.

**Unknown until the run metadata and checkpoints are reviewed:** exact scene, build/ELF identity, console model, mode, shader-cache state, simulation-clock drift, functional correctness and whether counters perturb timing.
