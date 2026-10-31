# Project Rules & Guidelines for Naruto: Rise of a Ninja NX

## Log Handling & Context Optimization
- **Never store raw or full log files in the repository or project directory** (e.g. `out/`, repo root, etc.).
- When reading logs from the console (via FTP or local runs):
  1. Retrieve/stream them into `/tmp/` or read them in memory/temporary streams.
  2. Parse and summarize key performance metrics:
     - Render resolution and swapchain resolution
     - Clocks (CPU, GPU, RAM)
     - Framerate (FPS), render thread time, and GPU frame time
     - Hitches, audio starvation / miss count, and file system / range-cache hit rates
  3. Immediately delete temporary raw log files from disk.
  4. Output only concise summaries, tables, or key excerpts to save context budget and avoid workspace clutter.

## Workflow, Incremental Progress & Verification
- **Communication:** Talk to the user in **Russian** with clickable `file://` links for referenced code.
- **Incremental Steps:** Work in small, thoughtful, verifiable steps. Before making changes, explain what is expected and how to measure it. Verify after every change.
- **Stock Hardware Baseline:** Prioritize optimizations targeting stock handheld hardware (CPU 1020 MHz, GPU 460 MHz) to achieve a solid 30/60 FPS experience out-of-the-box. Check the `clocks:` line of `rex_profile.log` before comparing runs.
- **Saves & Assets Safety:** Never overwrite or delete user saves (`/switch/naruto-nx/naruto/`) or game assets (`game/`).
- **Git Cleanliness:** Never commit game data or generated artifacts (`game/`, `app/generated/`, `out/`, shader dumps, GLSL/DKSH, saves).
- **Desktop Safety:** No screen grabs via `grim`/`hyprctl` (can crash compositor). Keep ≥ 3–4 GB RAM free, monitor `/dev/shm` (`tools/pc/shm_clean.sh`).
- **Codegen Safety:** Any manual `rexglue codegen` must be followed by `tools/post_codegen.sh`. Compiler flags `-ffp-contract=off -fno-strict-aliasing` on generated code are required for correctness.

## Reference Repositories
- `~/Projects/cloned/sa2-nx`: The template port. Its `docs/` cover every optimization round, and its renderer (`Renut`) is the source for this project.
- `~/Projects/cloned/naruto-rise-recomp`: The PC recompilation reference (seeds, hooks, D3D map, `WriteBackResolve`).
