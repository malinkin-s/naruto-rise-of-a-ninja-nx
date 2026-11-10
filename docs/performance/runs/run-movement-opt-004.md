# Console Measurement — `pilot-village-view-003`

Evidence: FTP game log `naruto_004.log` (SHA-256 `acb41dcb446dbd64092badf3aa8e672d490e781426560d5922c71eed6bc9d333`); CPU log `logs/rex/rex_profile.log` (SHA-256 `7a5bc1d049641e52a04eef99c845bf2d17dfd451648e23d98160513d950cfaee`). Raw logs were held in memory only.

**Status: candidate (scene/config review required).** Segment: 2026-11-09T00:15:55.159000 to 2026-11-09T00:16:25.181000 (game-log clock); monotonic ticks `327846240531`–`328422656963`; guest ordinals 2609–3434.
Full windows inside segment: 2 Renut, 2 CPU. The run still requires save, route, build, config and observed clock validation.

| Event stream | Events | Intervals | FPS | p50 / p95 / p99 / max interval (ms) | 1% low FPS |
|---|---:|---:|---:|---|---:|
| guest | 826 | 825 | 27.548 | 35.690 / 42.670 / 48.133 / 51.766 | 20.406 |
| present | 827 | 826 | 27.552 | 36.227 / 45.157 / 53.954 / 86.564 | 15.855 |

1% low = 1000 divided by the mean duration of the slowest ceil(1%) intervals. Intervals are between host-present callbacks or guest Swaps; panel scanout is not measured. Overflow invalidates the percentiles.

| Renut tick window | Log time at end | Frames | FPS | Render busy mean ms/frame | GPU mean ms/frame | Draws/frame |
|---|---|---:|---:|---:|---:|---:|
| 327990961890–328183187616 | 2026-11-09T00:16:12.708000 | 273 | 27.27 | 27.92 | 27.27 | 1766.8 |
| 328183187616–328375212030 | 2026-11-09T00:16:22.709000 | 276 | 27.60 | 27.49 | 25.91 | 1799.2 |

| CPU tick window | Profile FPS | Total CPU% | Main CPU% | Render CPU% | Clocks CPU/GPU/RAM MHz | Cores / mask | Audio misses |
|---|---:|---:|---:|---:|---|---|---:|
| 327846255876–328038275170 | 28.0 | 551.0 | 172.6 | 139.7 | 1020.0/460.8/1600.0 | 4 / 0xF | 0.0 |
| 328055533275–328247548983 | 30.6 | 313.0 | 97.9 | 77.5 | 1020.0/460.8/1600.0 | 4 / 0xF | 0.0 |

| Modular Culling (Batch5) | Batches tested/fr | Batches culled/fr (%) | Items tested/fr | Items culled/fr (%) |
|---|---:|---:|---:|---:|
| Segment window | 0.0 | 0.0 (0.0%) | 1568.3 | 280.9 (17.9%) |

| Culling Distances | <50m | 50–100m | 100–150m | 150–200m | >200m |
|---|---:|---:|---:|---:|---:|
| Distance histogram | 396.7 | 605.8 | 336.3 | 211.5 | 12.9 |

**Unknown until the run metadata and checkpoints are reviewed:** exact scene, build/ELF identity, console model, mode, shader-cache state, simulation-clock drift, functional correctness and whether counters perturb timing.
