# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Nintendo Switch homebrew (NRO) port of *Naruto: Rise of a Ninja* (Xbox 360). The game's PowerPC code (`default.xex`
plus the engine DLL `AI2C.dll`) is statically recompiled to C++ with the ReXGlue SDK (sa2-nx's fork). The Xenos GPU is
**not** emulated. Instead, Renut, a Direct3D-level renderer, draws the game's D3D calls on deko3d.

Read first: `docs/port-journal.md` (every step with its evidence and measurements), `docs/HANDOFF.md` (state, rules,
next steps), `docs/konoha-optimization-log.md` (open-world perf work, in Russian; stage 11 has the latest findings). The
root `HANDOFF.md` (Russian) is superseded by those two: its `oc_*` runs were at CPU 1785 / GPU 768 MHz, not stock.

## Working rules (from the user)

- Talk to the user in **Russian**. Work in small steps. Before each step, say what you expect and the cheapest way to measure it.
- **Never commit game data or anything generated from it**: `game/`, `app/generated/`, `out/`, shader dumps,
  GLSL/DKSH, saves, `installer test/`. All of these are git-ignored, so keep it that way. Release NROs must be built with
  `SA2_RENUT_RELEASE_SHADERS=ON` (the `out/nx-release` tree), so no translated game shader ends up inside.
- `app/thirdparty/` (plume, XenosRecomp, uam, imgui) is git-ignored and fetched by `tools/fetch_renut_deps.sh`. Edits
  there (e.g. `plume_deko3d*.{h,cpp}`) are **not tracked**, so say so whenever you change them.
- Desktop safety (Hyprland crashed before): no screen grabs (no grim/hyprctl screenshots). Get frames only from the
  renderer (`tools/pc/frames.sh`, the console's `--test_shots`). Keep ≥3–4 GB RAM free and watch `/dev/shm`
  (`tools/pc/shm_clean.sh`). Switch builds are memory-capped by `NX_BUILD_MEM` (default 7g).
- The user sometimes overclocks the console by hand, and the 30-FPS work is measured at CPU 1785 / GPU 768 MHz on purpose.
  Check the `clocks:` line of `rex_profile.log` before comparing two runs; compare at the same spot, standing still for a
  minute or more, and prefer an in-session A/B (`banjo_renut_ab_target`, `banjo_renut_ab_s`) to two separate runs.
- Release steps (`docs/HANDOFF.md` §6): the installer's `release/manifest.json` must hold the SHA-256 of the published
  `naruto.nro` (its deploy fails otherwise), so make the manifest from the final NRO, never rebuild the NRO after it, publish
  the GitHub release first and push the installer after.
- Publishing (GitHub releases, the installer's Pages) needs the user's go-ahead.

## Build

Host: Arch Linux. Switch builds run in Docker (`naruto-nx/devkita64`, devkitA64 r30 / GCC 16.1). The repo is mounted
at its own path, so the absolute paths in `app/generated/*.cmake` still resolve.

```bash
python3 tools/fetch_thirdparty.py      # SDK third-party sources (only patched files are tracked)
tools/fetch_renut_deps.sh              # plume, XenosRecomp, uam, imgui into app/thirdparty/
# host rexglue: sdk/, cmake --preset linux-amd64 -> sdk/out/linux-amd64/Release/rexglue
tools/codegen.sh                       # rexglue codegen app/naruto_manifest.toml + tools/post_codegen.sh (both trees)
cmake --build out/pc -j6               # PC build (Renut on Vulkan); re-runs codegen when its inputs change
tools/switch/build.sh [-reconfigure] [-DOPT=...]                  # dev NRO, game shaders built in: out/nx/naruto.nro
NX_BUILD_DIR=$PWD/out/nx-release tools/switch/build.sh            # NRO without game shaders (the PGO + LTO release tree is below)
tools/switch/package.sh [-nogame]      # out/nx/sdcard/ for the SD card
```

**PGO** (profile-guided optimisation, from sa2-nx; about -12 % of the render thread's CPU, +1.5-2 FPS at Konoha's worst spot):
`NX_BUILD_DIR=$PWD/out/nx-pgo tools/switch/build.sh -reconfigure -DNARUTO_PGO=generate -DSA2_RENUT_RELEASE_SHADERS=ON` makes an
instrumented NRO (copy `renut_gpu/host_shaders` from `out/nx-release/` into the new tree first); play it, fetch
`/switch/naruto-nx/pgo/*.stream` over FTP, `tools/pgo_merge.sh <folder>` writes `pgo/*.gcda`, then a build with
`-DNARUTO_PGO=use` (own tree) uses them. `pgo/` is committed (counters only). Change no source and no generated code between
the instrumented build and the use build. **The release NRO since 0.1.3** is built in `out/nx-pgo-lto` with
`-DNARUTO_PGO=use -DNARUTO_SWITCH_LTO=ON -DSA2_RENUT_RELEASE_SHADERS=ON` (PGO + LTO: render thread -21 % CPU at equal load).

`tools/codegen.sh` variants: `NARUTO_CLASSIC=1` (generator output only), `NARUTO_VOLATILE=1` (direct calls only),
`NARUTO_NO_CARDS=1` (skip store cards). **Any manual `rexglue codegen` must be followed by `tools/post_codegen.sh`**,
because the generator rewrites the files without the post-processing.

## Test

**Console** (the main loop): run it yourself. The user only reopens hbmenu's netloader (Y) after each run. The console
IP is in `tools/switch/nx.env`.

```bash
NX_NRO=$PWD/out/nx-release/naruto.nro tools/switch/nxtest.sh NAME 300 ''            # user plays for 5 min
tools/switch/nxtest.sh NAME 120 '10:START,14:START' --some_cvar=value                # scripted input + cvars
NX_PROFILE=1 NX_PROFILE_THREADS=Main tools/switch/nxtest.sh NAME 150 '<script>'      # + 1 kHz stack samples
```

Output goes to `out/runs/NAME/`:
- `nx.log`: the full log, with a `[renut]` report every 10 s (FPS, render thread busy, GPU, draws, caches).
- `rex_profile.log`: per-thread CPU, clocks, audio misses.
- `shot_*.png` and `sheet.jpg`: renderer frames.
- `naruto.elf`: for `tools/switch_profile_report.py` and crash symbolisation.
- Atmosphère crash reports, fetched over FTP on port 5000 when the user turns that server on.

For a fair A/B, use the same spot and camera view. Console input replays drift with load times.

**Four-core runs (HOME Menu forwarder, no netloader).** A forwarder started with 4 cores gives mask 0xF (`rex_profile.log`:
`process cores 4 (mask 0xF)`); the SDK then puts audio, XMA and the guest pool on core 3. There is no nxlink then: the
user copies `naruto.nro` to the SD card and starts the game from the HOME icon; turn the console's FTP server on and run
`python3 tools/switch/ftp_logs.py NAME` to fetch `rex_profile.log` and the file log into `out/runs/NAME/`. Settings come
from `naruto.toml` (e.g. `test_exit_after_s`, `naruto_deko3d_record_worker`). Diagnostics: `--naruto_debug_census=true`
(draw census every 10 s), `NX_PROFILE=1 NX_PROFILE_THREADS="renut render,Main,T_820F02C0"` with
`tools/switch_profile_report.py`; for lines of code run `llvm-addr2line` on the run's `naruto.elf`.

**PC deterministic replay**, to check that a codegen change keeps the game logic (same scenes at the same moments):
```bash
REPLAY=tools/pc/inputs/new_game_to_autosave1.nxinput tools/pc/frames.sh NAME 125 20 60 50 '' --sa2_renderer=renut --renut_vsync=false
```
Without `--sa2_renderer=renut`, the SDK's Xenos emulation draws the reference picture.

**SDK unit checks** (`sdk/tests/*.cpp`) are standalone. Each file's header comment gives its exact `clang++` command
(output into `out/tools/`). `arm_forms_check.cpp` is compile-only for the Switch compiler.

## Architecture

- **`sdk/`**: ReXGlue SDK, vendored from sa2-nx's fork with this port's changes. `patches/sdk-naruto-on-sa2-fork.patch`
  records the codegen-side delta. It holds the recompiler (`src/codegen`), the Xbox 360 kernel/XAM HLE (`src/kernel`),
  threads (`src/system/xthread.cpp`, `src/core/threading_switch.cpp`), audio (`src/audio/switch/`), and the Switch
  profiler (`src/ui/switch_perf.cpp`).
- **Recompilation inputs (`app/*.toml`)**:
  - `naruto_manifest.toml`: two modules, `default.xex` at 0x82000000 and `AI2C.dll` at 0x88000000. AI2C is linked
    into the NRO as a static module (`src/naruto_static_modules.cpp`, `ld -r` in `app/CMakeLists.txt`).
  - `*-seeds.toml`: function seeds and gap fixes. `gap-seeds.toml [rexcrt]` maps the guest's memcpy/memset/memmove to
    native NEON.
  - `ai2c-overrides.toml`.
  - `non_arg_keep_*.toml`: functions excluded from `non_argument_as_local`, produced by `tools/non_argument_audit.py`.
  - `codegen_flavor.toml`: the "optimised flavour" generator options. Each option's comment records its risk and its
    source.
- **Post-codegen passes (`tools/post_codegen.sh`)**: Python rewrites of `app/generated/{default,ai2c}`:
  - guest memory without `volatile` (`pch_no_volatile.py`), which **requires** `loop_barriers.py` (otherwise GCC hoists
    polling loads and a thread spins forever);
  - `direct_calls.py`, `guest_cas.py`, `vec_byteswap.py`, NEON shuffles, cold traps;
  - `store_cards.py`: guest stores mark 4 KB page cards, so Renut can validate cached vertex/index copies without
    hashing. It defines a strong `g_banjo_store_cards`, overriding the weak one in `src/naruto_renut_glue.cpp`.
- **Compile flags**: `-ffp-contract=off -fno-strict-aliasing` on the generated code are **required** for correctness
  (guest fmul/fadd must not fuse), and they are repeated at the LTO link. `-fno-math-errno` is on.
  `-fno-trapping-math` is deliberately off.
- **Renderer, `app/src/renut_engine/gpu/`** (from sa2-nx/banjo-nx, retargeted to Naruto's older XDK 2.0.6274, see
  `docs/renut-retarget.md` and `docs/d3d-census.md`):
  - `d3d/hooks/` intercept the game's D3D device functions;
  - `backend/queued.cpp` snapshots the private device state per draw and ships deltas to the render thread
    (`backend/render_thread.cpp`);
  - `render/` issues draws on plume's deko3d backend;
  - the game draws 3D in three 1280×256 4×MSAA tiles (EDRAM), and Renut's targets cover all of them;
  - game shaders come from `xeshader.sdb` (XenosRecomp → DXC → SPIRV-Cross → uam), see the `tools/deko3d_*.py` chain;
  - many `naruto_debug_*` cvars exist for diagnostics.
- **Config**:
  - players edit `naruto.toml` next to the NRO (template `app/naruto_switch.toml`);
  - `app/naruto_switch_defaults.toml` holds fixed settings and is built into the NRO;
  - `VERSION` lives in `app/CMakeLists.txt`.
- **Threads**: the game's main thread runs alone on core 0. The render thread is pinned to core 1 (priority 0x2C).
  Other guest threads run on mask 0x7 (`naruto_guest_cores`). Konoha's worst spot is CPU-bound on all three cores,
  and the render thread is the first limit.
- **Shader distribution**: the release ships only `naruto.nro`. Players build shaders from their own disc with the
  installer page (separate repo `~/Projects/naruto-nx-installer`). Release steps: `docs/HANDOFF.md` §6.

## Reference checkouts

- `~/Projects/cloned/sa2-nx`: the template port. Its `docs/` cover every optimisation round, and its
  `tools/post_codegen.py` is the source of the post-codegen passes.
- `~/Projects/cloned/naruto-rise-recomp`: the PC recompilation (seeds, hooks, D3D map, `WriteBackResolve`).
- `tools/gemini/`: a task pipeline for a research-only Gemini agent (`run_task.sh`, `rules.md`, `tasks/`). Reports go
  to `out/gemini/`.
