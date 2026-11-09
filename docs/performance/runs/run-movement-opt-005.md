# Console Measurement — `pilot-village-view-003`

Evidence: FTP game log `naruto_005.log` (SHA-256 `dfff81202f3b62fb7e403a3814b3d46b0fd1c0e839e26d9b1341c69008f109ad`); CPU log `logs/rex/rex_profile.log` (SHA-256 `1770f3306dc3e4a5045c0f4b9b707f5d384f489d8359853c936f51ccac4c5a43`). Raw logs were held in memory only.

**Status: candidate (scene/config review required).** Segment: 2026-11-09T00:44:25.111000 to 2026-11-09T00:44:55.120000 (game-log clock); monotonic ticks `360674722505`–`361250885293`; guest ordinals 2268–3074.
Full windows inside segment: 2 Renut, 2 CPU. The run still requires save, route, build, config and observed clock validation.

| Event stream | Events | Intervals | FPS | p50 / p95 / p99 / max interval (ms) | 1% low FPS |
|---|---:|---:|---:|---|---:|
| guest | 807 | 806 | 26.922 | 36.792 / 41.676 / 47.358 / 55.933 | 20.214 |
| present | 808 | 807 | 26.926 | 36.713 / 44.590 / 50.806 / 63.904 | 17.727 |

1% low = 1000 divided by the mean duration of the slowest ceil(1%) intervals. Intervals are between host-present callbacks or guest Swaps; panel scanout is not measured. Overflow invalidates the percentiles.

| Renut tick window | Log time at end | Frames | FPS | Render busy mean ms/frame | GPU mean ms/frame | Draws/frame |
|---|---|---:|---:|---:|---:|---:|
| 360693989385–360886633315 | 2026-11-09T00:44:36.148000 | 267 | 26.61 | 28.12 | 27.70 | 1984.2 |
| 360886633315–361078995699 | 2026-11-09T00:44:46.167000 | 272 | 27.15 | 27.22 | 28.01 | 1911.6 |

| CPU tick window | Profile FPS | Total CPU% | Main CPU% | Render CPU% | Clocks CPU/GPU/RAM MHz | Cores / mask | Audio misses |
|---|---:|---:|---:|---:|---|---|---:|
| 360674737587–360866757016 | 26.9 | 503.0 | 158.8 | 126.9 | 1020.0/460.8/1600.0 | 4 / 0xF | 0.0 |
| 360884775130–361076778153 | 29.6 | 321.0 | 100.4 | 80.1 | 1020.0/460.8/1600.0 | 4 / 0xF | 0.0 |

| Modular Culling (Batch5) | Batches tested/fr | Batches culled/fr (%) | Items tested/fr | Items culled/fr (%) |
|---|---:|---:|---:|---:|
| Current window | 0.0 | 0.0 (0.0%) | 1855.9 | 493.2 (26.6%) |
| Current window | 0.0 | 0.0 (0.0%) | 1891.1 | 423.1 (22.4%) |
| Current window | 0.0 | 0.0 (0.0%) | 1768.5 | 381.7 (21.6%) |
| Current window | 0.0 | 0.0 (0.0%) | 1768.4 | 364.6 (20.6%) |
| Current window | 0.0 | 0.0 (0.0%) | 1710.4 | 336.7 (19.7%) |

| Culling Distances | <50m | 50–100m | 100–150m | 150–200m | >200m |
|---|---:|---:|---:|---:|---:|
| Distance histogram | 285.4 | 640.5 | 618.7 | 267.6 | 37.8 |
| Distance histogram | 345.8 | 639.3 | 577.3 | 297.1 | 25.7 |
| Distance histogram | 335.3 | 599.5 | 526.0 | 284.5 | 17.2 |
| Distance histogram | 354.5 | 613.1 | 497.1 | 288.3 | 9.4 |
| Distance histogram | 373.6 | 616.5 | 431.7 | 270.8 | 11.8 |

## Bottleneck Verdict

- **Primary Limit: MAIN_CPU_BOUND** (Main XThread: ~33.9 ms / 100.4% of Core 0 vs 33.3 ms target budget)
- **Secondary Factor: DRAW_CALL_VOLUME** (1948 draws/frame; scene complexity)
- **GPU Status:** Headroom available (27.9 ms GPU time; 5.5 ms margin to 30 FPS target)
- **Prescribed Action:** Profile guest functions with `tools/switch_profile_report.py`; tighten modular culling `max_dist` in `sub_820FD5F8`.

**Unknown until the run metadata and checkpoints are reviewed:** exact scene, build/ELF identity, console model, mode, shader-cache state, simulation-clock drift, functional correctness and whether counters perturb timing.
