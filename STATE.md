# Naruto NX — Current State

Updated: 2026-11-10. This is the single source of truth for agents. Limit: 150 lines. Labels: **Fact** (cites a Run ID, commit or file), **Hypothesis**, **Unknown**, **Decision**. Checked by `python3 tools/agent/check_docs.py`.

## Build identity

- **Fact:** `main` HEAD is `7509546`, one commit ahead of `origin/main` (`0a4610d`). Release `v0.1.5` is commit `25159ed`; `v0.1.4` is tag `18ddecd` (`git log`).
- **Fact:** the console candidate for the next run is `out/nx-pgo-lto/naruto.nro`, SHA-256 `e9f15f71868eb9d939c81fcf6300df3f4bce59bb62205b887c7907e1c21f76bd`. It was built from `7509546` with PGO=use and LTO (`docs/archive/removed-build-trees-2026-11-09.md`).
- **Fact:** the toolchain and dependency pins are listed in `docs/project/toolchain.md`. The PGO profile (`pgo/`, 2026-10-29) predates the app and SDK changes in `25159ed` and `7509546`, so changed functions lose their counts.
- **Unknown:** published 0.1.5 NRO hash versus local builds, and the console firmware.

## Latest measurements (all stock handheld 1020/460.8/1600 MHz, 4 cores, mask 0xF)

All reports have status **candidate**: scene, save and route equivalence is not verified. Deltas between them are observations, not A/B results.

| Run ID | Build | Guest FPS | p50 / p99 ms | Render busy ms | GPU ms | Draws/fr |
|---|---|---:|---|---:|---:|---:|
| `pilot-village-view-003` | pre-`25159ed` dev | 28.57 | 33.39 / 48.04 | 22.6 | 27.1–27.6 | ~1,518 |
| `run-movement-opt-004` | uncommitted tree after `25159ed` | 27.55 | 35.69 / 48.13 | 27.5–27.9 | 25.9–27.3 | ~1,780 |
| `run-movement-opt-005` | uncommitted tree after `25159ed` | 26.92 | 36.79 / 47.36 | 27.2–28.1 | 27.7–28.0 | ~1,950 |
| `run-gpu-opt-008` | uncommitted tree after `25159ed` | 26.24 | 37.79 / 47.20 | 33.3–35.8 | 32.1–33.8 | ~2,460 |

- **Unknown:** exact source and NRO hash for runs 004–008. They were built from uncommitted work that later became part of `7509546`; run reports do not record NRO/TOML hashes.

Sources: `docs/performance/runs/<Run ID>.md`. Older pilot runs: `docs/archive/runs/`.

- **Fact:** `run-gpu-opt-008` shows Main CPU 95.9–116.2% and Render CPU 94.2–129.1% in the profile windows (`docs/performance/runs/run-gpu-opt-008.md`).
- **Unknown:** the semantics of "Main CPU%". Values above 100% for one thread appear in `run-movement-opt-004` (172.6%) and `run-gpu-opt-008`. Resolve in `sdk/src/ui/switch_perf.cpp` before using this metric to attribute a bottleneck.
- **Fact:** the current source default is `naruto_max_view_distance = 0.0` (culling off) in `app/src/renut_engine/gpu/d3d/hooks/draw.cpp`.
- **Hypothesis:** `run-gpu-opt-008` ran with view distance 0.0 and `pilot-village-view-003` with 135 m, which would explain ~940 more draws/frame. The run reports do not record the TOML hash, so this is unverified.

## Corrected claims (do not repeat without a new run)

- **Fact:** the 0.1.5 notes say "30 FPS reached". `pilot-village-view-003` measured 28.57 FPS mean, with a median interval of 33.39 ms (≈29.95 FPS) at one stationary spot. "30.0–31.5 FPS" in older notes is a profile-window value, not the segment mean (`docs/release-0.1.5.md`, `docs/performance/runs/pilot-village-view-003.md`).
- **Fact:** the 135 m culling from 0.1.5 caused sky/alpha flicker and was reverted in `7509546`. Its draw/GPU savings are therefore no longer present in the current source (`docs/archive/handoff-2026-11-09.md` §B).
- **Fact:** the handoff claim "Main XThread 95% → 33.4% (Run 7)" has no run report in `docs/performance/runs/`. The later `run-gpu-opt-008` contradicts it.

## Hypotheses awaiting `run-gpu-opt-009` (task `docs/tasks/T001-verify-7509546.md`)

Commit `7509546` bundles these changes without separate A/B. Each is a **Hypothesis** until measured:

1. SDK: 2 MB guest-memory alignment, `.text`/`.rodata` 2 MB remap, 16-entry dispatcher cache, permanent FZ/DN (`sdk/src/core/guest_memory_switch.cpp`, `sdk/src/ui/switch_code_blocks.cpp`, `sdk/src/system/function_dispatcher.cpp`, `sdk/include/rex/platform/fpscr.h`). These are generic SDK changes: decide on upstream versus local before keeping them.
2. Renut: lock-free render queue (`app/src/renut_engine/gpu/backend/render_thread.cpp`), fastpath expansion and clear-repeat skip (`app/src/renut_engine/gpu/render/draw.cpp`, `surfaces.h`).
3. Hooks: resolve collapsing in `sub_821398C8` and telemetry gating (`app/src/renut_engine/gpu/d3d/hooks/draw.cpp`); math hooks (`app/src/cpu/naruto_math_hooks.cpp`).

- **Decision:** after `run-gpu-opt-009`, the owner decides whether to split `7509546` into an SDK part and an app part, and to run per-part A/B tests.

## Unknowns

- **Unknown:** canonical scenario: save file, route and camera are not frozen (`docs/performance/scenarios.md`).
- **Unknown:** run-to-run noise at one spot. No repeated identical runs exist, so a delta under ~1.5 FPS cannot be attributed.
- **Unknown:** exit crash, black save thumbnail, three-core audio stutter (`README_ru.md` §State); not reproduced on current builds.
- **Unknown:** exact FTP upload procedure (`docs/performance/console-run-workflow.md`).

## Decisions in force

- **Decision:** acceptance runs use FTP deployment and manual launch through the Sphaira forwarder (4 cores, 39-bit). `tools/switch/nxtest.sh` is legacy (`docs/performance/console-run-workflow.md`).
- **Decision:** one task = one module, one hypothesis, one primary metric, one control Run ID, one commit (`AGENTS.md` §Task cycle).
- **Decision:** Codex is the primary editing agent; Antigravity/Gemini is a read-only researcher. Its reports are Hypotheses (`AGENTS.md` §Agent Roles).
- **Decision:** dependency updates (ReXGlue v0.10.1, sa2-nx v1.0.6, PGO refresh) wait until a baseline exists (`docs/project/toolchain.md`).

## Next action

Owner runs `run-gpu-opt-009` on the installed candidate. Then:
`python3 tools/switch/ftp_run_summary.py run-gpu-opt-009 --control run-gpu-opt-008 --output docs/performance/runs/run-gpu-opt-009.md`, and update task T001 and this file.

## Read on demand

| Question | Document |
|---|---|
| Which module owns what, upstream boundary | `docs/architecture/subsystem-map.md` |
| How to run and collect a console measurement | `docs/performance/console-run-workflow.md`, `docs/performance/measurement-protocol.md` |
| What each metric means | `docs/performance/metric-catalog.md` |
| Scenarios and saves | `docs/performance/scenarios.md` |
| Installed console files | `docs/project/console-install-snapshot.md` |
| Toolchain and dependency versions | `docs/project/toolchain.md` |
| Quality targets / versioning | `docs/project/quality-goals.md`, `docs/project/versioning.md` |
| Roadmap | `ROADMAP.md` |
| Historical "what was tried" | `docs/archive/` (only for a named question) |
