# Project Instructions for Codex

Speak Russian with the user. Write saved project documentation in English. Read `PORT_DEV_LOG.md`, `docs/project/current-state.md`, the relevant subsystem row and scenario before editing. User instructions take precedence. `GEMINI.md` contains hardware, asset and log-handling constraints. `docs/archive/` is excluded from routine context: read a specific archived file only for a concrete historical question, then verify its claims against current source or a new run.

## Work boundary

- Start with `git status --short --branch` and a source/read-only audit. Preserve user changes. Never touch `game/`, saves or generated game content unless an explicit task requires it; never commit them.
- A performance task has one named module, one falsifiable hypothesis, one primary metric, scenario/config IDs, a control and regression checks. Propose the smallest change. No broad refactor or rewrite without an ADR supported by run evidence.
- Separate **Fact** (source or run evidence), **Hypothesis**, **Unknown** and **Decision**. Cite file/section, commit or Run ID. Old release reports are historical, not proof for the current binary.
- ReXGlue SDK and vendored Renut changes require a clear local-vs-upstream boundary (`docs/architecture/subsystem-map.md`). Do not alter a generic dependency to work around an unmeasured game issue.
- Do not run long or destructive build/test/package commands merely for exploration. `tools/codegen.sh` rewrites generated output; `tools/switch/package.sh` replaces the staged `game/`. The accepted console path is manual launch through the owner's Sphaira forwarder, with files/logs moved by FTP (`docs/performance/console-run-workflow.md`). `nxtest.sh` is legacy netloader tooling, not an acceptance run. Use unique Run IDs and protect saves.
- Do not use `grim` or `hyprctl` screenshots (`GEMINI.md` §Desktop Safety). Routine performance runs are log-first; ask for media only if numeric/checkpoint data cannot establish scene equivalence or a visual defect needs evidence. For every console log received through FTP, create one compact English Markdown summary using `docs/performance/console-log-summary-template.md`. Never retain or paste the full log in the repository, `out/`, chat or agent context. Use `tools/switch/ftp_run_summary.py` or the compatible `ftp_logs.py`: both read raw logs into memory and save only a compact report (`GEMINI.md` §Log Handling).
- The agent may inspect, draft, make reversible scoped edits and run proportionate checks under the user's task. **Do not commit, publish releases, change CI/workflow or upload artifacts without an explicit owner decision.** Do not treat a request to investigate as permission to deploy.

## Commands (read their scripts before running)

- Host code generation: `tools/codegen.sh` (`app/generated/` changes; requires own game data).
- PC build: `cmake --build out/pc -j6` (`docs/project/current-state.md` §Build and launch path; historical command in `docs/archive/HANDOFF.md`).
- Switch build: `tools/switch/build.sh`; release-style flags are recorded in `docs/project/current-state.md`.
- Console test: follow `docs/performance/console-run-workflow.md`: FTP transfer, owner-operated Sphaira forwarder, FTP log retrieval and compact summary. The exact FTP upload command/service is not yet documented; ask the owner when needed.
- CPU attribution: `python3 tools/switch_profile_report.py <rex_profile.log> --elf <matching ELF>`; read its filter defaults first.

## Task and report template

Issue fields: symptom and user impact; owner/module; evidence class and source; scenario/config/build IDs; primary metric and predicted direction; A/B control; smallest proposed edit; regression checks; risk; acceptance rule; missing owner decision. Suggested labels: `audit`, `baseline`, `scenario`, `telemetry`, `cpu`, `gpu`, `memory`, `io`, `audio`, `input`, `graphics`, `stability`, `build`, `needs-evidence`, `upstream-candidate`, `blocked`.

Review stages: source/ownership review → frozen scenario and metric → scoped implementation → same-condition A/B → functional regression → ADR/current-state update. Final Codex report: what changed, why, exact checks and Run IDs, measured result vs control, uncertainty, remaining risks and next action. If no run occurred, say so. Ask the owner only for information or decisions unavailable from connected sources or the repository; continue independent work where possible.
