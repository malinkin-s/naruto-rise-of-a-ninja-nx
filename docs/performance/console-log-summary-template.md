# Console Log Summary — TEMPLATE

One short English Markdown file per Run ID, for example `run-...-console-summary.md`. This is the retained result of parsing a console log, **not a copy of that log**. Use `unknown` when absent; use `not measured` when telemetry did not collect the metric. Never fabricate percentiles from 10-second averages. Source policy: `GEMINI.md` §Log Handling; run identity: `docs/project/versioning.md`.

## Identity and validity

| Field | Value / source line or artifact |
|---|---|
| Run ID; scenario/version; config ID | TBD |
| Commit; Build ID; NRO SHA-256; shader package SHA-256 | TBD |
| Console model, firmware, launch method/core mask | unknown |
| Handheld/docked; render and swapchain resolution | unknown |
| Observed CPU/GPU/RAM clocks; clock changes | unknown |
| Warm-up class; measured start/end; duration; game state/checkpoints | unknown |
| Measurement START/END ticks; guest-frame first/last ordinal | not measured |
| Valid / invalid / pending; reason | pending |

## Metrics for the declared segment

| Metric | Result; aggregation and sample count | Evidence |
|---|---|---|
| Guest Swaps, host presents, FPS mean/range; interval percentiles only from per-frame data | not measured | |
| Swap-to-Swap work/pacing/late/hitches; game-clock drift | not measured | |
| Main/game draw/render thread CPU and wait time | not measured | |
| Render busy, GPU mean, draw calls by type | not measured | |
| Pipeline/shader creations and cache hits | not measured | |
| Process/guest/GPU memory peaks; filesystem/range-cache hits/misses and load time | not measured | |
| Audio requests without data / starvation; input/replay divergence | not measured | |

## Findings

- **Errors/crashes:** count and one short diagnostic excerpt per distinct issue, with timestamp; `none observed` only if the log covers the full run.
- **Primary module metric and control:** TBD; link A/B Run IDs when applicable.
- **Fact:** observed result and its precise log field or artifact reference.
- **Hypothesis / unknown:** possible cause and the next discriminating test.
- **Artifacts:** hashes/references to matching ELF, profile and crash report; optional renderer capture only for a scene/visual question. No full log in this repository.

Keep this summary compact (normally one page). If the source log is incomplete, mark the missing interval and do not call the run valid.
