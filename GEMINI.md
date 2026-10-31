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

## Workflow & Safety
- **No Overclock Baseline:** Prioritize optimizations targeting stock handheld hardware (CPU 1020 MHz, GPU 460 MHz) to achieve a solid 30/60 FPS experience out-of-the-box.
- **Saves & Assets Safety:** Never overwrite or delete user saves (`/switch/naruto-nx/naruto/`) or game assets (`game/`).
- **Communication:** Provide clear, concise responses in Russian with clickable `file://` links for referenced code.
