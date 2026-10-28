# naruto-nx: handoff (2026-10-28)

Hand-off of the Naruto: Rise of a Ninja (Xbox 360) → Nintendo Switch port, written for the next agent. Read this first, then `docs/port-journal.md` (every step with its evidence and measurements) and
`README.md`. Talk to the user in **Russian**; work in **small steps**, say before each step what you expect and how to
measure it.

## 1. Where the project is

- **Released**: 0.1.2 (pre-release, 2026-10-28) — https://github.com/malinkin-s/naruto-rise-of-a-ninja-nx/releases/tag/v0.1.2
  (0.1.1 before it). The release holds only `naruto.nro` (no game data). Players make the game's shaders with the
  **installer page** https://malinkin-s.github.io/naruto-nx-installer/ (repo `malinkin-s/naruto-nx-installer`, local
  `~/Projects/naruto-nx-installer`): two files of their disc (`default.xex`, `xeshader.sdb`) in, a zip out (`naruto.nro`,
  `deko3d_glsl.bin`, `deko3d_shaders.bin`). 0.1.2 did not change the shader package or the DKSH cache (same
  `package_sha256` / `cache_sha256` as 0.1.1); only the manifest's `version`, `nro_sha256`, `nro_size` changed.
- **Works on the console**: boot, menus, saves, cutscenes, story mode (Konoha), fights, controller, sound.
- **Performance**:
  - stock clocks (CPU 1020 / GPU 460.8 MHz), 0.1.1 figures, not repeated: fights 32–47 FPS at 720p, 46–58 at 480p;
    Konoha about 20 FPS at its worst spot.
  - **the console overclocked by hand (CPU 1785 / GPU 768 MHz), which is what the 30-FPS work is measured at**: the worst
    spot of Konoha runs 26–28 FPS (three cores) and +0.5–1.2 FPS with four cores; lighter parts of the village 29–30; fights
    run at 60 FPS (the user's observation, not logged in a run).
    Steps 1–10 of `docs/konoha-optimization-log.md` left the frame rate at those clocks where it was (26.2–27.5 FPS, noise);
    the 20 → 27 FPS was the CPU overclock. Check the `clocks:` line of `rex_profile.log` before comparing runs.
  - the limit at the worst spot: three heavy threads at 80–95 % of a core each (the game's main thread, its drawing
    thread `T_820F02C0`, Renut's render thread at 94 %); the render thread (≈34 ms a frame, a flat profile) has no slack.
- **Four cores** (new in 0.1.2): a HOME Menu forwarder started with 4 cores (Sphaira: CPU cores 4, address space 39-bit)
  gives the process mask 0xF; the SDK (`RexSwitchProcessCoreMask`, `sdk/src/system/xthread.cpp`) then puts audio, XMA and
  the guest pool on core 3. No audio lag, smoother play. From hbmenu the port runs on three cores as before.
- **Experimental, off by default, never run on the console**: `naruto_deko3d_record_worker` (stage A, see below).

## 2. The user's rules (keep them)

- Answers in Russian, short steps, hypotheses + the cheapest experiment before each step.
- **Never commit game data or code generated from it**: `game/`, `app/generated/`, `out/`, shader dumps, GLSL,
  DKSH, saves, `installer test/` are git-ignored. The release NRO must be built with `SA2_RENUT_RELEASE_SHADERS=ON`
  (no translated game shader inside).
- **Desktop safety** (Hyprland crashed twice): no screen grabs (no grim/hyprctl screenshots); frames only from the
  renderer (`tools/pc/frames.sh`, the console's `test_shots`); watch RAM (keep ≥ 3–4 GB free) and `/dev/shm`; PC runs
  clean `/dev/shm/xenia_memory_*` before/after (`tools/pc/shm_clean.sh`, done by `launch.sh`); PC game windows on
  workspace 2; no virtual input devices.
- The user builds and tests when they want to: give them the exact command (below) and say what to look at.
- The user sometimes overclocks by hand: **check the `clocks:` line of `rex_profile.log` before comparing runs**.
- Publishing (releases, Pages) needs the user's go-ahead.

## 3. Build and test

Host: Arch Linux. Switch builds run in Docker (`naruto-nx/devkita64`, devkitA64 r30 GCC 16.1).

```bash
tools/codegen.sh                      # the game's code into app/generated + post-codegen steps (both trees)
cmake --build out/pc -j6              # PC build (Renut on Vulkan); also regenerates code when inputs change
tools/switch/build.sh                 # dev NRO with the game's shaders built in: out/nx/naruto.nro
NX_BUILD_DIR=$PWD/out/nx-release tools/switch/build.sh [-reconfigure]   # release NRO (no game shaders)
```

Console test (the user only opens hbmenu's netloader; IP in `tools/switch/nx.env`, 192.168.0.165):

```bash
NX_NRO=$PWD/out/nx-release/naruto.nro tools/switch/nxtest.sh NAME 300 ''          # 5 minutes, the user plays
NX_PROFILE=1 NX_PROFILE_THREADS=Main tools/switch/nxtest.sh NAME 150 '<input script>'   # + stack samples of a thread
```

Results in `out/runs/NAME/`: `nx.log` (every log line; `[renut]` 10-s reports: FPS, render thread busy, GPU,
draws, caches), `rex_profile.log` (each thread's CPU, clocks, audio misses), `shot_<s>.png` + `sheet.jpg` (renderer
frames), `naruto.elf` (for `tools/switch_profile_report.py` and crash reports), crash reports fetched over the
console's FTP (port 5000, when the user turns it on). The release NRO needs `deko3d_glsl.bin` (+ ideally
`deko3d_shaders.bin`) from the installer beside it on the SD (already there on the user's card).

Useful one-liner, game-thread CPU per frame per 10-s interval:
```bash
awk '/^==== /{split($0,a,"game "); split(a[2],b," "); fps=b[1]} /audio:/{match($0,/[0-9]+ requests without data/); r=substr($0,RSTART,RLENGTH)+0} /"Main XThread/{match($0,/CPU [0-9.]+%/); c=substr($0,RSTART+4,RLENGTH-5); printf "%s fps | main %.1f ms | audio miss %d\n", fps, c*10/(fps>0?fps:1), r}' out/runs/NAME/rex_profile.log
```

PC: deterministic replay `REPLAY=tools/pc/inputs/new_game_to_autosave1.nxinput tools/pc/frames.sh NAME 125 20 60 50 ''
--sa2_renderer=renut --renut_vsync=false` (frames in `out/runs/NAME/`); without `--sa2_renderer=renut` the SDK's
Xenos emulation draws the reference picture. Use it to check a codegen change keeps the game logic (same scenes at
the same moments).

## 4. Architecture in brief

- ReXGlue SDK (fork of sa2-nx's, `sdk/`, our changes also in `patches/`), static recompilation of `default.xex`
  and the engine DLL `AI2C.dll` (linked into the NRO). Manifest `app/naruto_manifest.toml`.
- Optimised code generator: `app/codegen_flavor.toml` (registers as locals, float-mode options, step 2 options) +
  `tools/post_codegen.sh` (no-volatile guest memory, loop barriers, direct calls, store cards). Compile flags in
  `app/CMakeLists.txt` (`-ffp-contract=off -fno-strict-aliasing` are REQUIRED; `-fno-math-errno`).
- Renderer: Renut (Direct3D-level, from sa2-nx/banjo-nx) on plume's deko3d back end, `app/src/renut_engine/`,
  retargeted to Naruto's XDK 6274 (`docs/renut-retarget.md`, `docs/d3d-census.md`). Many `naruto_debug_*` cvars for
  diagnostics (skip/log by pixel shader, stencil, caches...).
- Player settings `naruto.toml` next to the NRO (template `app/naruto_switch.toml`); fixed settings
  `app/naruto_switch_defaults.toml`.
- Thread layout: game main thread alone on core 0, render thread pinned to core 1 (priority 0x2C), other guest
  threads on mask 0x7 (`naruto_guest_cores`, new default: fixed most audio starvation).

## 5. Next steps (in this order)

1. **Run stage A on the console** (written, built, not run): `naruto.toml`: `naruto_deko3d_record_worker = true`; for an
   in-session comparison also `banjo_renut_ab_target = 14` and `banjo_renut_ab_s = 15` (the `[renut A/B]` line gives both
   halves' FPS, render thread and GPU time). Look at the `[renut] record worker` line (lists through it, worker busy
   time, drains) and for glitches (wrong textures, missing draws: the worker keeps its own copy of the shared constants,
   `Deko3DSetSharedWords`; descriptor sets are bound by pointer). Expected: render thread ≈34 → ≈31 ms. Needs the 4-core
   forwarder (the worker goes to core 3); logs of forwarder runs: `python3 tools/switch/ftp_logs.py NAME` (console FTP on).
2. **Stage B** if A is not enough: Renut's per-draw preparation (`DrawStateLocked`, geometry, streams, constants, textures:
   ≈50–60 % of the render thread) ahead of the render thread on core 3, command recording on core 1.
3. **PGO / clang for the game code** (sa2-nx PGO ≈ 15 %, mgr clang ≈ 8 %, `x360-switch-ports` SOL-CPU-1/-2/-5): the only
   measured across-the-board CPU gain in the other ports; not tried here.
4. Hot guest functions of `T_820F02C0` as guarded natives (`sub_82105648`, `sub_820FD5F8`, `sub_82137E00` are ≈78 % of its
   guest samples; SOL-CPU-3).
5. Reducing the scene (draw distance / LOD) only as a player option: at this spot cutting draws late in the render thread
   did not help (`skip1`), small draws are mixed with the HUD, and the other ports' gains came from the game's own LOD.
6. **Sound**: with four cores there is no audio lag; on three cores it still stutters when FPS dips.
7. Not performance: the **save thumbnail** (black on Load Game), **controls** (letter-position default, Joy-Con assist), the
   "Saved Game Warning" scroll border. See the previous version of this section in git history for the details.

How to measure: stand at the worst spot for a minute or more; compare inside one session (A/B), not between runs;
`NX_PROFILE=1 NX_PROFILE_THREADS="renut render,Main,T_820F02C0"` and `tools/switch_profile_report.py`; per-line attribution
with `llvm-addr2line` on the run's `naruto.elf`; `--naruto_debug_census=true` logs the draw census every 10 s.

## 6. Releasing a new version

1. Bump `VERSION` in `app/CMakeLists.txt`; build the release NRO (`NX_BUILD_DIR=$PWD/out/nx-release ...`).
2. Pipeline lists from new console sessions (`switch/naruto-nx/pipeline_list.bin` over FTP) into
   `data/pipeline_lists/`; variants: `python3 tools/deko3d_variant_cache.py --list data/pipeline_lists/*.bin --glsl
   <installer GLSL> --emit-variants ~/Projects/naruto-nx-installer/release/deko3d_variants.json --dry-run`.
3. Installer manifest: `node test/naruto_manifest.mjs <game> out/nx-release/naruto.nro <version> out/deko3d_shaders/glsl_opt`
   in `~/Projects/naruto-nx-installer`; `node test/worker_node.mjs <default.xex> <xeshader.sdb>` runs the page's
   worker end to end.
4. GitHub release with `naruto.nro` + `SHA256SUMS.txt` (notes in English and Russian), **then** push the installer (its
   Pages workflow takes the NRO from the newest release, pre-releases included, and fails with "not a build of the
   manifest" when the NRO's SHA-256 is not in `release/manifest.json`: the manifest must be made from the very NRO that is
   published, and the NRO must not be rebuilt after it). For 0.1.2 only `version`, `nro_sha256` and `nro_size` changed.
   `node test/worker_node.mjs <default.xex> <xeshader.sdb>` (with the NRO copied to the installer's `release/`) runs the
   page's worker end to end. README in both languages
   (`tools/readme_badges.py` for the status badge).

## 7. Where things are

| What | Where |
|---|---|
| Journal (read it) | `docs/port-journal.md` |
| Gemini task pipeline | `tools/gemini/` (`run_task.sh`, `rules.md`, `tasks/*.md`); reports `out/gemini/`, plans `out/gemini/plans/` |
| Reference ports | `~/Projects/cloned/sa2-nx` (docs on every optimisation round), `~/Projects/cloned/naruto-rise-recomp` (PC base) |
| Recent console runs | `out/runs/cpu2` (worst spot), `rel3`, `rel2`, `konoha2`, `cards2` (fight) |
| Recorded pad input | `tools/pc/inputs/*.nxinput` (PC replays; console replays drift with load times) |
