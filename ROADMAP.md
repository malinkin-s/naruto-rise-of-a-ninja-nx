# Evidence-Based Roadmap

Statuses as of 2026-11-02: documentation audit exists; clean build, canonical scenarios and new baseline are **not verified**. Sources: `docs/project/current-state.md`; `PORT_DEV_LOG.md`. Each stage is complete only with its listed artifact/evidence, not because a related script exists.

| Stage | Goal and prerequisites | Deliverables and tasks | Completion evidence | Risk / owner question | Status |
|---|---|---|---|---|---|
| A. Source snapshot / clean build | Base tag and own game data | Build manifest, hashes, toolchain digest; reproduce NRO without replacing release artifacts | Build ID and matching/explicitly different hash; launch record | Published 0.1.4 artifact identity? | Not started |
| B. Architecture / owners | A source inventory | Map each layer, vendored revision and local modifications | Reviewed subsystem map with source evidence | Which generic fixes go upstream? | Draft map |
| C. Quality scope | Owner intent and A facts | Matrix of modes, behavior and TBD thresholds | Owner-approved criteria after baseline | Required docked/DLC scope? Four-core forwarder is already required | Draft goals |
| D. Scenarios / replay | A plus candidate saves | Frozen initial states, route/checkpoint definitions, replay pilot | Repeated checkpoint-matching runs | Save vs reset; replay clock? | Not started |
| E. Baseline / diagnosis | C/D and sufficient telemetry | Immutable Run IDs, spread, CPU/GPU/memory/wait classification | Comparable repeated runs for required modes | Missing frame-time stream? | Not started |
| F. Measured optimization | E and one falsifiable hypothesis | Small change, A/B, regression report, ADR if architectural | Primary metric improves beyond noise; guardrails pass | Rewrite only after evidence | Not started |
| G. Full regression / stability | F or baseline candidate | Coverage checklist, long sessions, crash/save/audio review | No unresolved agreed-gate failures | Full-game coverage and session length? | Not started |
| H. Package / release | G and owner approval | Hash-bound NRO/shaders/installer manifest and notes | Installed package matches approved Build ID | Release authorization? | Not started |

## First issues, dependency order

1. `build-identity`: obtain published 0.1.4 NRO hash, exact CMake/toolchain/PGO/shader identity (A; blocker).
2. `clean-build`: reproduce a separate NRO and document any hash difference and launch result (A; depends on 1 and own data).
3. `ownership-review`: inventory ReXGlue/Renut/plume revisions and project patches; validate map (B).
4. `scenario-state`: locate/hash the owner's save near the sub-30-FPS hotspot; freeze route, camera and checkpoint first, then choose fight and save/load controls (D; owner input; `docs/performance/scenarios.md`).
5. `replay-pilot`: test existing PC and Switch paths for checkpoint drift, input-clock/loading behavior (D; depends on 4).
6. `console-log-output`: memory-only FTP collector and compact Markdown report are implemented; four window-join tests pass and old console logs yield `pending`; validate against a measured console run (E; `tools/switch/ftp_run_summary.py`).
7. `run-markers`: opt-in Run ID, FTP start marker, segment start/end, guest-frame ordinals and common system ticks in CPU and Renut windows are implemented; verify on console (E; `frame_stats.cpp`, `device.cpp`, `banjo_renut_tuning.cpp`, `switch_perf.cpp`).
8. `frame-intervals`: bounded in-memory guest-Swap/host-present interval statistics and 1% low are implemented in a locally linked diagnostic NRO; validate event semantics and telemetry overhead on console. Export a raw numeric stream only if a named diagnostic needs per-frame attribution (E; `docs/project/measurement-build-2026-11-02.md`).
9. `simulation-checkpoint`: expose an independent game-clock/checkpoint marker and test route drift against wall time (D/E; depends on 5 and 7).
10. `baseline-handheld`: run cold and warm stock handheld scenarios with pilot repeats and spread report using the metric catalog's low-overhead set (E; depends on 1, 4, 6–9).
11. `quality-decision`: owner sets numerical thresholds and required coverage from baseline (C/E; depends on 10).
12. `baseline-docked`: repeat approved suite at documented docked stock conditions (E; depends on 11 if docked required).
13. `first-bottleneck-ADR`: align main/render/GPU/wait data, choose one failing module metric and a falsifiable A/B test; enable stack or GPU work-by-kind profiling only if needed (F; depends on baseline).

**Blocking unknowns:** exact release artifact, FTP upload procedure and installed-file identity, console setup and game-data validation, canonical initial save/route, equivalence of replay paths under the forwarder, shared cross-log markers, durable present intervals and independent game-clock drift, and owner decisions on mandatory modes/coverage. Do not schedule a renderer or SDK rewrite before these are resolved.
