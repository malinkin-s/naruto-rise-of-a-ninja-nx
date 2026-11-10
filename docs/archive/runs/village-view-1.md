# Console Measurement — `village-view-1`

Evidence: FTP game log `naruto_003.log` (SHA-256 `0fc3acaa298e5ea4607375c231e2e1f0590edc7e455f2df42eabfeef34fd5878`); CPU log `logs/rex/rex_profile.log` (SHA-256 `4bf8b520c35c96e6c07d0b4baaddcbd3ed26dbc7bf3eb0a17de0269a37f3fd6a`). Raw logs were held in memory only.

**Status: pending.** Segment: 2026-11-08T16:57:51.629000 to 2026-11-08T16:58:21.633000 (game-log clock); monotonic ticks `6891236485316`–`6891812561639`; guest ordinals 1398–2185.
Full windows inside segment: 0 Renut, 0 CPU. The run still requires save, route, build, config and observed clock validation.

| Event stream | Events | Intervals | FPS | p50 / p95 / p99 / max interval (ms) | 1% low FPS |
|---|---:|---:|---:|---|---:|
| guest | 788 | 787 | 26.290 | 37.836 / 42.996 / 46.175 / 64.235 | 20.179 |
| present | 789 | 788 | 26.319 | 37.683 / 45.438 / 49.069 / 57.458 | 19.373 |

1% low = 1000 divided by the mean duration of the slowest ceil(1%) intervals. Intervals are between host-present callbacks or guest Swaps; panel scanout is not measured. Overflow invalidates the percentiles.

| Renut tick window | Log time at end | Frames | FPS | Render busy mean ms/frame | GPU mean ms/frame | Draws/frame |
|---|---|---:|---:|---:|---:|---:|
| not measured: no full tick-aligned Renut window | | | | | | |

| CPU tick window | Profile FPS | Total CPU% | Main CPU% | Render CPU% | Clocks CPU/GPU/RAM MHz | Cores / mask | Audio misses |
|---|---:|---:|---:|---:|---|---|---:|
| not measured: no full CPU window | | | | | | | |

| Modular Culling (Batch5) | Batches tested/fr | Batches culled/fr (%) | Items tested/fr | Items culled/fr (%) |
|---|---:|---:|---:|---:|
| Current window | 0.0 | 0.0 (0.0%) | 2473.0 | 931.0 (37.6%) |
| Current window | 0.0 | 0.0 (0.0%) | 2468.9 | 943.0 (38.2%) |
| Current window | 0.0 | 0.0 (0.0%) | 2454.1 | 933.0 (38.0%) |
| Current window | 0.0 | 0.0 (0.0%) | 2454.0 | 933.0 (38.0%) |
| Current window | 0.0 | 0.0 (0.0%) | 2454.0 | 933.0 (38.0%) |

| Culling Distances | <50m | 50–100m | 100–150m | 150–200m | >200m |
|---|---:|---:|---:|---:|---:|
| Distance histogram | 309.0 | 454.5 | 624.9 | 803.9 | 275.7 |
| Distance histogram | 319.6 | 484.1 | 574.4 | 768.8 | 316.9 |
| Distance histogram | 318.1 | 494.0 | 565.0 | 767.0 | 305.0 |
| Distance histogram | 318.0 | 494.0 | 565.0 | 767.0 | 305.0 |
| Distance histogram | 318.0 | 494.0 | 565.0 | 767.0 | 305.0 |

## Bottleneck Verdict

- **Primary Limit: GPU_BOUND** (GPU execution: 30.4 ms at 460 MHz vs 33.3 ms target)
- **Prescribed Action:** Profile GPU passes with `renut_gpu_profile = 10.0`.

**Unknown until the run metadata and checkpoints are reviewed:** exact scene, build/ELF identity, console model, mode, shader-cache state, simulation-clock drift, functional correctness and whether counters perturb timing.
