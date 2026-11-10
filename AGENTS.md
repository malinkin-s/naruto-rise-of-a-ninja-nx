# Project Instructions for AI Agents (Codex & Antigravity)

Speak Russian with the user. Write saved project documentation and task files in English. User instructions take precedence. This file is the single canonical rule set for every agent.

## Start-up context (read only these)

1. `AGENTS.md` (this file).
2. `STATE.md`: the only current-state file (≤150 lines; Facts with Run IDs, Hypotheses, Unknowns, Decisions, Next action).
3. The active task file `docs/tasks/T*.md` named by the user or by `STATE.md` §Next action.

Open other documents through `STATE.md` §Read on demand, only for the question at hand. `docs/archive/` is cold storage: open one specific file only for a concrete historical question, then verify its claims against current source or a new run. Historical development logs and handoffs in archive are history, not current state.

## Agent Roles

- **Codex: primary editing agent.** Edits code and docs within an active task file's scope.
- **Antigravity / Gemini: read-only researcher.** Runs through `tools/gemini/run_task.sh` (rules in `tools/gemini/rules.md`), never edits the tree, builds or runs the game unless explicitly instructed by the user. Its reports land in `out/gemini/` and are **Hypotheses** until verified against source or a run.
- Only one agent edits the tree at a time.

## Task cycle (mandatory for code changes)

1. **Task file first.** Copy `docs/tasks/TASK-TEMPLATE.md` to `docs/tasks/T<NNN>-<slug>.md` and fill in: module, one falsifiable hypothesis, primary metric and predicted direction, scenario/config IDs, control Run ID, file scope, regression checks, acceptance rule. Status `draft` → `ready` after owner agreement.
2. **Scoped change.** Touch only files listed in the task scope. Propose the smallest change. No broad refactor or rewrite without an ADR (`docs/decisions/ADR-TEMPLATE.md`) supported by run evidence.
3. **One task = one commit.** Changes under `sdk/` (ReXGlue fork) or vendored Renut go in a separate commit labelled `local` or `upstream-candidate` (`docs/architecture/subsystem-map.md`). Never bundle independent optimizations: a bundle cannot be A/B-attributed (counter-example: `7509546`).
4. **Measure.** Status `measuring` (at most one task at a time). Owner runs the candidate; collect the result with `tools/switch/ftp_run_summary.py <run-id> --control <control-run-id> --output docs/performance/runs/<run-id>.md`.
5. **Close.** Record the result in the task file (`accepted` / `rejected`), update `STATE.md`, run `python3 tools/agent/check_docs.py`.

Documentation-only and tooling tasks may skip steps 4–5's run but still use a task file when they change behaviour.

## Evidence rules

- Separate **Fact** (source, commit or Run ID with a report in `docs/performance/runs/`), **Hypothesis**, **Unknown** and **Decision**. A `**Fact:**` line in `STATE.md` must cite a Run ID, commit hash or existing file; `tools/agent/check_docs.py` enforces this.
- Script output is data, not a verdict. Do not promote an automatic classification, a researcher report or a handoff narrative to Fact without checking it against the run report. Old release notes and handoffs are history, not proof for the current binary.
- A delta between two runs is an observation unless the scene/save/route, build and TOML identities match and the noise floor is known.
- Handoff files are optional attachments; the truth is `STATE.md` plus the active task file.

## Hardware, Platform & Safety

- **Stock Hardware Baseline:** Prioritize optimizations targeting stock handheld hardware (CPU 1020 MHz, GPU 460.8 MHz, RAM 1600 MHz, 4 Cores, 39-bit ASLR) to achieve a solid 30/60 FPS experience out of the box. Check the `clocks:` line of `rex_profile.log` before comparing runs.
- **Console Launch Policy:** Acceptance runs use FTP deployment and manual launch through the owner's Sphaira forwarder (4 cores, 39-bit address space) (`docs/performance/console-run-workflow.md`). `tools/switch/nxtest.sh` is legacy netloader tooling, not an acceptance run.
- **Saves & Assets Safety:** Never overwrite or delete user saves (`/switch/naruto-nx/naruto/`, `out/saves/`) or game assets (`game/`). Never touch `game/`, saves or generated game content unless an explicit task requires it; never commit them.
- **Git Cleanliness:** Never commit game data or generated artifacts (`game/`, `app/generated/`, `out/`, shader dumps, GLSL/DKSH, saves).
- **Desktop Safety:** Do not use `grim` or `hyprctl` screenshots (can crash the compositor). Keep ≥ 3–4 GB RAM free, monitor `/dev/shm` (`tools/pc/shm_clean.sh`).
- **Codegen Safety:** Any manual `rexglue codegen` must be followed by `tools/post_codegen.sh`. Compiler flags `-ffp-contract=off -fno-strict-aliasing` on generated code are required for correctness.
- **Work boundary:** The agent may inspect, draft, make reversible scoped edits and run proportionate checks under the user's task. **Do not commit, publish releases, change CI/workflow or upload artifacts without an explicit owner decision.** Do not treat a request to investigate as permission to deploy.

## Log Handling & Context Optimization

- **Never store raw or full log files in the repository or project directory** (`out/`, repo root, etc.).
- When reading logs from the console (via FTP or local runs):
  1. Retrieve/stream them into `/tmp/` or read them in memory/temporary streams.
  2. Create **one compact English Markdown report per Run ID** using `docs/performance/console-log-summary-template.md`. Include run/build/scenario/config identity, observed clocks and core mask, resolution, measured interval, available FPS/frame-time/CPU/GPU/draw/memory/IO/audio metrics, errors and validity. Use `unknown` for fields absent from the log; do not infer a percentile from aggregate FPS.
  3. Immediately delete temporary raw log files from disk.
  4. Do not paste or retain the full log in chat, agent context, `out/` or the repository. Keep only the compact report, small diagnostic excerpts and artifact hashes/references.
  5. Use `tools/switch/ftp_run_summary.py` or the compatible `ftp_logs.py`: both read raw logs into memory and save only a compact report.

## Reference Repositories

- `~/Projects/cloned/sa2-nx`: The template port. Its `docs/` cover every optimization round, and its renderer (`Renut`) is the source for this project. Pinned commit and gap to upstream: `docs/project/toolchain.md`.
- `~/Projects/cloned/naruto-rise-recomp`: The PC recompilation reference (seeds, hooks, D3D map, `WriteBackResolve`).

## Commands (read scripts before running)

- Docs/state check: `python3 tools/agent/check_docs.py` (optional local hook: `ln -s ../../tools/agent/pre-commit .git/hooks/pre-commit`, owner decision).
- Tool tests: `python3 tools/switch/test_ftp_run_summary.py`, `python3 tools/agent/test_check_docs.py`.
- Host code generation: `tools/codegen.sh` (`app/generated/` changes; requires own game data).
- PC build: `cmake --build out/pc -j6`.
- Switch build: `tools/switch/build.sh` (default tree `out/nx`); release-style tree: `NX_BUILD_DIR=$PWD/out/nx-pgo-lto tools/switch/build.sh -reconfigure -DNARUTO_PGO=use -DNARUTO_SWITCH_LTO=ON -DSA2_RENUT_RELEASE_SHADERS=ON`. Toolchain identity: `docs/project/toolchain.md`.
- Console test: `docs/performance/console-run-workflow.md`: FTP transfer, owner-operated Sphaira forwarder, FTP log retrieval and compact summary.
- CPU attribution: `python3 tools/switch_profile_report.py <rex_profile.log> --elf <matching ELF>`; read its filter defaults first.

## Final report

What changed, why, exact checks and Run IDs, measured result against control, uncertainty, remaining risks and next action. If no run occurred, say so. Ask the owner only for information or decisions unavailable from the repository; continue independent work where possible. Suggested labels: `audit`, `baseline`, `scenario`, `telemetry`, `cpu`, `gpu`, `memory`, `io`, `audio`, `input`, `graphics`, `stability`, `build`, `needs-evidence`, `upstream-candidate`, `blocked`.
