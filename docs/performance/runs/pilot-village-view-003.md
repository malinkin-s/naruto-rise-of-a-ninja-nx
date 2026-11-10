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
| Segment window | 0.0 | 0.0 (0.0%) | 2170.0 | 1040.0 (47.9%) |

| Culling Distances | <50m | 50–100m | 100–150m | 150–200m | >200m |
|---|---:|---:|---:|---:|---:|
| Distance histogram | 313.0 | 486.0 | 560.0 | 583.0 | 223.0 |

**Unknown until the run metadata and checkpoints are reviewed:** exact scene, build/ELF identity, console model, mode, shader-cache state, simulation-clock drift, functional correctness and whether counters perturb timing.
