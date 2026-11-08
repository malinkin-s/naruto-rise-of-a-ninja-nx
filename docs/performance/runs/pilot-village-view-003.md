# Console Measurement — `pilot-village-view-003`

Evidence: FTP game log `naruto_001.log` (SHA-256 `6e4032b675be9febcc7f73343fd0ab83a05c0382d544ae97a8fc9b16acb72c65`); CPU log `logs/rex/rex_profile.log` (SHA-256 `320fb9e1b05337a982f95e71a8ae554b075c8552b3dff0e01457728e782c3c8d`). Raw logs were held in memory only.

**Status: candidate (scene/config review required).** Segment: 2026-11-08T18:19:21.748000 to 2026-11-08T18:19:51.781000 (game-log clock); monotonic ticks `6985119989905`–`6985696613873`; guest ordinals 3075–3931.
Full windows inside segment: 2 Renut, 2 CPU. The run still requires save, route, build, config and observed clock validation.

| Event stream | Events | Intervals | FPS | p50 / p95 / p99 / max interval (ms) | 1% low FPS |
|---|---:|---:|---:|---|---:|
| guest | 857 | 856 | 28.565 | 33.390 / 44.118 / 48.036 / 60.198 | 20.025 |
| present | 858 | 857 | 28.566 | 34.163 / 46.551 / 49.575 / 71.565 | 18.557 |

1% low = 1000 divided by the mean duration of the slowest ceil(1%) intervals. Intervals are between host-present callbacks or guest Swaps; panel scanout is not measured. Overflow invalidates the percentiles.

| Renut tick window | Log time at end | Frames | FPS | Render busy mean ms/frame | GPU mean ms/frame | Draws/frame |
|---|---|---:|---:|---:|---:|---:|
| 6985160615744–6985353275453 | 2026-11-08T18:19:33.899000 | 288 | 28.70 | 22.55 | 27.08 | 1515.3 |
| 6985353275453–6985545894550 | 2026-11-08T18:19:43.931000 | 286 | 28.51 | 22.58 | 27.55 | 1520.2 |

| CPU tick window | Profile FPS | Total CPU% | Main CPU% | Render CPU% | Clocks CPU/GPU/RAM MHz | Cores / mask | Audio misses |
|---|---:|---:|---:|---:|---|---|---:|
| 6985120008800–6985312027167 | 28.7 | 311.0 | 102.6 | 74.1 | 1020.0/460.8/1600.0 | 4 / 0xF | 0.0 |
| 6985324617209–6985516628934 | 30.4 | 293.0 | 97.0 | 67.7 | 1020.0/460.8/1600.0 | 4 / 0xF | 0.0 |

| Modular Culling (Batch5) | Batches tested/fr | Batches culled/fr (%) | Items tested/fr | Items culled/fr (%) |
|---|---:|---:|---:|---:|
| Current window | 0.0 | 0.0 (0.0%) | 2086.2 | 945.9 (45.3%) |
| Current window | 0.0 | 0.0 (0.0%) | 2145.0 | 1003.2 (46.8%) |
| Current window | 0.0 | 0.0 (0.0%) | 2172.3 | 1042.1 (48.0%) |
| Current window | 0.0 | 0.0 (0.0%) | 2170.0 | 1040.0 (47.9%) |
| Current window | 0.0 | 0.0 (0.0%) | 2170.0 | 1040.1 (47.9%) |
| Current window | 0.0 | 0.0 (0.0%) | 2170.0 | 1040.0 (47.9%) |

| Culling Distances | <50m | 50–100m | 100–150m | 150–200m | >200m |
|---|---:|---:|---:|---:|---:|
| Distance histogram | 303.6 | 464.1 | 613.8 | 540.0 | 159.7 |
| Distance histogram | 308.3 | 477.0 | 590.8 | 566.3 | 197.6 |
| Distance histogram | 313.2 | 486.2 | 559.9 | 583.0 | 225.0 |
| Distance histogram | 313.0 | 486.0 | 560.0 | 583.0 | 223.0 |
| Distance histogram | 313.0 | 486.0 | 560.0 | 583.0 | 223.0 |
| Distance histogram | 313.0 | 486.0 | 560.0 | 583.0 | 223.0 |

## Bottleneck Verdict

- **Primary Limit: MAIN_CPU_BOUND** (Main XThread: ~31.9 ms / 97.0% of Core 0 vs 33.3 ms target budget)
- **Secondary Factor: DRAW_CALL_VOLUME** (1518 draws/frame; scene complexity)
- **GPU Status:** Headroom available (27.3 ms GPU time; 6.0 ms margin to 30 FPS target)
- **Prescribed Action:** Profile guest functions with `tools/switch_profile_report.py`; tighten modular culling `max_dist` in `sub_820FD5F8`.

**Unknown until the run metadata and checkpoints are reviewed:** exact scene, build/ELF identity, console model, mode, shader-cache state, simulation-clock drift, functional correctness and whether counters perturb timing.
