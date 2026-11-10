# Console Measurement — `pilot-village-view-002`

Evidence: FTP game log `naruto_001.log` (SHA-256 `274895ed6c371135421d13ba4392575ee3cd9e77e3688371590caf77ad39da71`); CPU log `logs/rex/rex_profile.log` (SHA-256 `46437b5a9a925211b41fe21d8230ef87ec70b58fe34a7a24705b0792076d639f`). Raw logs were held in memory only.

**Status: candidate (scene/config review required).** Segment: 2026-11-08T17:22:32.811000 to 2026-11-08T17:23:02.820000 (game-log clock); monotonic ticks `6919666868039`–`6920243031282`; guest ordinals 1811–2659.
Full windows inside segment: 2 Renut, 2 CPU. The run still requires save, route, build, config and observed clock validation.

| Event stream | Events | Intervals | FPS | p50 / p95 / p99 / max interval (ms) | 1% low FPS |
|---|---:|---:|---:|---|---:|
| guest | 849 | 848 | 28.322 | 33.818 / 43.208 / 48.550 / 56.747 | 20.030 |
| present | 850 | 849 | 28.326 | 34.645 / 44.935 / 49.771 / 55.671 | 19.398 |

1% low = 1000 divided by the mean duration of the slowest ceil(1%) intervals. Intervals are between host-present callbacks or guest Swaps; panel scanout is not measured. Overflow invalidates the percentiles.

| Renut tick window | Log time at end | Frames | FPS | Render busy mean ms/frame | GPU mean ms/frame | Draws/frame |
|---|---|---:|---:|---:|---:|---:|
| 6919763208752–6919955496098 | 2026-11-08T17:22:47.843000 | 282 | 28.16 | 23.45 | 26.23 | 1545.2 |
| 6919955496098–6920147816569 | 2026-11-08T17:22:57.860000 | 286 | 28.55 | 23.72 | 25.52 | 1539.0 |

| CPU tick window | Profile FPS | Total CPU% | Main CPU% | Render CPU% | Clocks CPU/GPU/RAM MHz | Cores / mask | Audio misses |
|---|---:|---:|---:|---:|---|---|---:|
| 6919666872109–6919858887474 | 28.4 | 301.0 | 100.8 | 75.2 | 1020.0/460.8/1600.0 | 4 / 0xF | 0.0 |
| 6919870956859–6920062963600 | 30.1 | 287.0 | 97.4 | 69.9 | 1020.0/460.8/1600.0 | 4 / 0xF | 0.0 |

| Modular Culling (Batch5) | Batches tested/fr | Batches culled/fr (%) | Items tested/fr | Items culled/fr (%) |
|---|---:|---:|---:|---:|
| Current window | 0.0 | 0.0 (0.0%) | 2199.2 | 1046.5 (47.6%) |
| Current window | 0.0 | 0.0 (0.0%) | 2173.3 | 1019.6 (46.9%) |
| Current window | 0.0 | 0.0 (0.0%) | 2241.9 | 1075.9 (48.0%) |
| Current window | 0.0 | 0.0 (0.0%) | 2055.7 | 905.5 (44.0%) |
| Current window | 0.0 | 0.0 (0.0%) | 2188.8 | 1022.8 (46.7%) |

| Culling Distances | <50m | 50–100m | 100–150m | 150–200m | >200m |
|---|---:|---:|---:|---:|---:|
| Distance histogram | 310.9 | 468.5 | 614.1 | 589.8 | 210.9 |
| Distance histogram | 307.9 | 462.4 | 616.0 | 577.7 | 204.2 |
| Distance histogram | 306.0 | 453.1 | 639.2 | 615.3 | 223.3 |
| Distance histogram | 307.9 | 467.1 | 596.2 | 515.1 | 164.0 |
| Distance histogram | 304.2 | 464.1 | 627.1 | 585.1 | 203.2 |

## Bottleneck Verdict

- **Primary Limit: MAIN_CPU_BOUND** (Main XThread: ~32.4 ms / 97.4% of Core 0 vs 33.3 ms target budget)
- **Secondary Factor: DRAW_CALL_VOLUME** (1542 draws/frame; scene complexity)
- **GPU Status:** Headroom available (25.9 ms GPU time; 7.5 ms margin to 30 FPS target)
- **Prescribed Action:** Profile guest functions with `tools/switch_profile_report.py`; tighten modular culling `max_dist` in `sub_820FD5F8`.

**Unknown until the run metadata and checkpoints are reviewed:** exact scene, build/ELF identity, console model, mode, shader-cache state, simulation-clock drift, functional correctness and whether counters perturb timing.
