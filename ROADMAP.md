# Evidence-Based Roadmap

Statuses as of 2026-11-09. Current facts live in `STATE.md`; this file tracks stages only. A stage is complete when its evidence exists, not when a related script exists. Each change of status cites a Run ID, commit or file.

| Stage | Goal | Completion evidence | Status (evidence) |
|---|---|---|---|
| A. Build identity | Reproducible NRO with recorded toolchain | Toolchain digest, NRO hash, Build ID per run | **Partial.** Toolchain recorded (`docs/project/toolchain.md`); candidate NRO hash in `STATE.md`. Missing: published 0.1.5 hash, NRO/TOML hash inside run reports |
| B. Architecture / owners | Module map with upstream boundary | Reviewed `docs/architecture/subsystem-map.md` | **Draft.** SDK changes in `7509546` still lack an upstream/local decision |
| C. Quality scope | Owner thresholds and coverage | Owner-approved criteria | **Not started** (`docs/project/quality-goals.md`: all TBD) |
| D. Scenarios | Frozen save, route, camera, checkpoints | Repeated checkpoint-matching runs | **Partial.** Village view spot used repeatedly; save/route not frozen (`docs/performance/scenarios.md`) |
| E. Baseline / telemetry | Run ID markers, interval stats, repeatable spread | ≥3 identical runs per scenario with spread | **Partial.** Run ID markers, guest/present intervals and FTP collector work on console (`pilot-village-view-003`, `run-gpu-opt-008`); no repeated identical runs; Main CPU% semantics unknown |
| F. Measured optimization | One hypothesis per task with A/B | Task file + control and candidate Run IDs | **In progress, non-compliant history.** 0.1.5 and `7509546` bundled several changes without A/B; T001 (`docs/tasks/T001-verify-7509546.md`) is the first compliant task |
| G. Regression / stability | Long sessions, crash/save/audio review | Coverage checklist without blocking failures | **Not started** |
| H. Package / release | Hash-bound NRO, shaders, installer | Installed package matches approved Build ID | 0.1.5 published; release notes overstate FPS (`STATE.md` §Corrected claims) |

## Ordered issues

1. `T001-verify-7509546`: run `run-gpu-opt-009` against control `run-gpu-opt-008` (F; owner run).
2. `cpu-metric-semantics`: define "Main CPU%" and fix or relabel values above 100% (E; `sdk/src/ui/switch_perf.cpp`).
3. `run-identity-in-report`: record NRO and TOML SHA-256 in each run report (A/E; `tools/switch/ftp_run_summary.py`).
4. `noise-floor`: three identical runs of one build at one spot to measure spread (E; depends on 2–3).
5. `split-7509546`: depending on T001, split into SDK and app commits and A/B each part (F; owner decision).
6. `scenario-freeze`: freeze the save, route and camera for `village-view-v1` (D; owner input).
7. `pgo-refresh`: regenerate the PGO profile after the code stabilizes (A; changes binary identity).
8. `deps-update`: evaluate ReXGlue v0.10.1 and sa2-nx v1.0.6 against local patches (B; after baseline; `docs/project/toolchain.md`).
9. `quality-decision`: owner sets thresholds from the baseline (C).
10. `docked-baseline`, `stability-suite` (E/G; after 9).

**Rule:** no renderer or SDK rewrite before stages D and E produce repeatable evidence and an ADR compares alternatives.
