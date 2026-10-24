# Naruto: Rise of a Ninja port journal

From `x360-switch-ports/skill/templates/port-journal.md`. The place to think, not a log of everything.

## The game

- Title: Naruto: Rise of a Ninja (Ubisoft Montreal, 2007). Title ID `555307E5` (naruto-rise-recomp docs/dlc.md).
  Region/edition: to confirm (the disc has `Credits_US.bik` and `Credits_EMEA.bik`; sound in en/fr).
- `default.xex` SHA-256 `f8fd8a979fb5451460f820303a6ca4c75e01fd943aed600983cb68fc491af7bd` (7,516,160 bytes).
  Title update: none in our files yet.
- Disc. Code modules (all XEX2):
  - `default.xex`: base 0x82000000, entry 0x821776A0. Draws (D3D9LTCG, XGRAPHC, D3DX9), audio (XAUDLTCG, X3DAUD,
    XMP), online (XONLINE, XHV, XRNMS).
  - `AI2C.dll`: base 0x88000000, entry 0x88399178, SHA-256 `ed760975…0d3d`. Imports only XBOXKRNL/XAPILIB/LIBCMT: the
    game's engine logic, no Direct3D. Character DLCs replace it with `AI2C@1/@2/@3.dll`, each a different code layout
    that needs its own recompiled module (entries 0x883A0CF8, 0x883ADD48, 0x883AEF88; naruto-rise-recomp docs/dlc.md).
  - `LinkApp.xex`: base 0x82000000, entry 0x8205A050, SHA-256 `6b4035d0…198a`. D3D9 (not LTCG) + XUI + XNET: a
    separate application (not in the PC base's manifest). Purpose to confirm.
- Direct3D / XDK build: **2.0.6274** for every library of all three modules (XEX static library list, key 0x200FF).
  Older than Renut's references (N&B 2.0.7645, SA2 2.0.21076); `default.xex` links the **LTCG** Direct3D.
- On the 360: logic in fixed steps, 1/30 s in the open world and menus, 1/60 s in fights; animation, physics and
  timers follow the step (naruto-rise-recomp docs/renderers.md). Video: Bink (`*.bik`). Shaders in `xeshader.sdb`.
- Existing work:
  - PC: jorjbarbosa/naruto-rise-recomp (GPL-3.0, ReXGlue SDK 0.10.0, v0.3.0-beta 2026-10-23), checked at `93feca6`.
    Plays menus, open world, missions and fights with its native renderer; not verified across the whole game.
  - Switch: nobody (refresh 2026-10-24T03:11Z, SwitchPorts README, GitHub search). Relatives: Android ARM64 port
    Masterllgod/naruto-rise-of-a-ninja-port-nativo (static recomp + Vulkan, from 2026-10-14); madkils PC port
    (translation patches).
- Go / no-go: **go** (game-selection.md, candidate 3, taken 2026-10-24): 360 exclusive, a working PC recompilation,
  30 Hz logic in the open world.

## Current stage

Stage: 2 (translate and sweep missed code).
Goal: codegen clean for `default.xex` + `ai2c.dll`, the missed-code sweep (SOL-CODE-1) done, every manifest fix with
evidence. First codegen and the SOL-CODE-1 sweep done 2026-10-24 (below). Next: the PC build of the app (stage 3).

## Known (with evidence)

- XDK 2.0.6274 in all three modules — XEX header 0x200FF (scratch script `xexlibs.py`).
- The D3D device is 22,400 bytes (0x5780) — naruto-rise-recomp `app/src/gpu/d3d/device.h:575` `kDeviceBytes`.
  N&B 0x5E00, SA2 0x6080 (sa2 renut-renderer.md): Renut's offsets must all be re-read for this game.
- The Direct3D functions Renut hooks exist as separate functions despite LTCG; the PC base names them:
  Swap 0x821280B0, DrawIndexed 0x821024A8, DrawVertices 0x8212C7E8, BeginVertices 0x8212EA18, Resolve 0x8212D750,
  BlockOnFence 0x82139090, SetGammaRamp 0x8212B3E0, a window-scissor writer 0x82128270, the ring reserve 0x8212F608,
  a packet-writing leaf 0x8212F7E0, the scene flush 0x821083B8 — `app/src/gpu/d3d/*` (69 `REX_HOOK_RAW` in all).
- The PC base's renderer (`app/src/gpu/`, ~45,000 lines) = the same idea as Renut: hooks at the D3D level, the
  ring's packets discarded, draws translated on its own thread, shaders by XenosRecomp ahead of time — but:
  - its two back ends are written to the APIs directly: `backend/d3d12/backend.cpp` 3,841 lines (502 D3D12
    references), `backend/vulkan/backend.cpp` 1,977 lines (raw `vk*`); plume only in part. A Switch back end would be
    a third one from scratch behind `backend/backend.h` (45 virtual methods);
  - 42 of its files include `<windows.h>`;
  - PC features on the hot path: interpolated frames above 30 FPS (objects, camera, skinned poses, particles), MSAA,
    1.5x, 25 diagnostics files, a failure channel;
  - shaders compiled at build time from `xeshader.sdb` and embedded in the executable (fine on PC, not shippable on
    the Switch: SOL-SHIP-1);
  - occlusion queries (light glows only) answered with a fixed value; options-menu labels missing (open defect).
- The PC base's SDK patches we will likely need: `codegen-alt-version-dll-modules.patch` (DLC engines),
  `obdosdevices-relative-paths.patch`; the others are PC/Xenos specific.

- **Guest DLLs on the Switch are solved by sa2-nx** (its `Data_DLL.xex`, sa2-nx `adf3a4e`): CMake builds the module
  as a static archive, `ld -r --force-group-allocation` + `objcopy --localize-hidden --redefine-sym` make one object
  with renamed `ReXModule_Register_<name>` / `ReXModule_GetImageInfo_<name>` (`app/CMakeLists.txt:373-396`),
  `src/sa2_static_modules.cpp` registers them (`rex::system::RegisterStaticModule`), and
  `KernelState::LoadUserModule` looks there first (`sdk/src/system/kernel_state.cpp:769`). Registration of the function
  table happens **at load time**, keyed by guest path, with an image base/size check: four AI2C revisions sharing base
  0x88000000 can sit in one NRO because the game loads one per session (naruto-rise-recomp docs/dlc.md).
- The PC base's `codegen-alt-version-dll-modules.patch` (codegen only: snapshot each DLL image before the next one
  at the same base overwrites it; DLL-DLL overlap = alternative versions, a warning) does not apply to the sa2-nx
  fork as is (`git apply --check`: context at `project_recompiler.cpp:262`, sa2's `REXGLUE_DUMP_IMAGE` block); its
  logic is small and ports by hand. `obdosdevices-relative-paths.patch` applies cleanly.
- Both SDKs are upstream ReXGlue v0.10.0 (sa2-nx fork from `c94f5eb`, PC base manifest `sdk_version = "0.10.0"`):
  the PC base's seeds (`analysis-seeds.toml` 40 lines, `ai2c*-seeds.toml`) should carry over.

- **First codegen (2026-10-24)**: the sa2-nx SDK fork (`sdk/`, our two changes in
  `patches/sdk-naruto-on-sa2-fork.patch`), host `rexglue` built with `cmake --preset linux-amd64` (clang 22),
  `rexglue codegen app/naruto_manifest.toml` with the PC base's seeds: exit 0, 0 warnings, 13.8 s, 316 files;
  30,466 functions registered (24,123 `default.xex`, 6,343 `AI2C.dll`). Two lines
  `BaseHeap::Release failed because address is not a region start` (after AI2C's Validate and at exit): to check
  whether the second same-base DLL load path causes it (only one DLL now, so probably not; watch when DLC engines
  are added).
- **Same disc revision as the PC base**: every `sub_*` address their source names (116, hooks and helpers) is a
  function start in our codegen (`out/pc_hooks.txt` vs `SetFunction` list). Their hook map applies as is.

- **SOL-CODE-1 sweep (2026-10-24)**, tools from sa2-nx (`tools/`, GPL-3.0) with Naruto's code ranges from the PE
  section tables (`default` .text+BINK 0x820C0000-0x826CFE34, AI2C .text 0x88040000-0x883A0C20):
  - gaps + data pointers into gaps (`tools/gap_pass.py`, our one-pass take on `gap_fixpoint.py`): `default` 106 + 8
    accepted (2 passes, then fixpoint) in `app/gap-seeds.toml`, 36 of them targets of data words (vtables at
    0x8208C4xx-0x8208C9xx); AI2C 0 (1 candidate, rejected). Functions 23,857 -> 23,965.
  - `find_gaps.py` miscounted: the generator drops unreachable instructions (`b` after `b`), so "start + 4 x
    comments" ended functions early (sub_880412C8: 309 comments, 318 instructions, its tail 0x8804179C-0x880417BC
    reported as a gap). Fixed to measure from the last label: AI2C gaps >= 8 bytes 3,115 -> 11, `default` 624 -> 408
    (the rest: 305 data pairs inside .text, C++ EH data, 11 zero runs).
  - jump tables (`switch_check.py`): truncated 0, wrong targets 0, missed 0 in both modules. 6 "odd shapes" in
    `default` are function-pointer tables in .data/.rdata (every code value a registered function): safe.
    `pointer_audit.py` "built in code" 239 = inline jump tables after `bctr`: not entries.
  - setjmp/longjmp: `default` 0x822CC540/0x822CC220 (PC base seeds, the only functions storing/loading r1 through
    r3/r7); AI2C has none (no r1 store/load through any register but r1).
  - Exceptions: `default` imports RtlRaiseException, RtlUnwind, RtlCaptureContext; `sub_822D837C` restores a whole
    context and jumps to r3 (EH unwinding, called from sub_822CFB70 <- sub_822CFCB8/sub_822CFE28). The SDK's
    RtlUnwind is a stub that logs `[STUB] RtlUnwind called`: watch the PC logs for it.

## Open questions and hypotheses

| Question | Hypotheses | Cheapest experiment that separates them | Result |
|---|---|---|---|
| How do `ai2c.dll` (and DLC `ai2c@N.dll`) become part of one NRO? | (a) the sa2-nx SDK fork already handles `[[modules]]` statically; (b) needs a static module table in place of host DLLs | grep the sa2-nx SDK fork for module registration / `XexLoadImage` on Horizon | **(a)**, see Known "Guest DLLs" |
| Is our `default.xex` the revision the PC base's seeds and hook addresses were made for? | (a) yes (one retail disc revision); (b) another revision/region | first codegen with their `analysis-seeds.toml`: clean analysis and hooked addresses at function starts | **(a)**: all 116 `sub_*` addresses in their `app/src` are function starts in ours |
| Is `LinkApp.xex` ever run? | (a) system-link/online launcher, never in single player; (b) needed for a mode we want | grep the PC base and its logs for `LinkApp`/`XLaunchNewImage`; strings in `default.xex` | PC base: no reference |
| Does Renut's device-reading work with the 6274 device layout? | (a) same shadow registers and bound-object fields, only moved; (b) 6274 keeps state elsewhere (older private part) | diff the offsets the PC base reads (`d3d/device.*`, `state.*`) against Renut's `d3d_native.h` list | |
| Does the game raise exceptions in play (RtlUnwind is a stub)? | (a) never in normal play (the PC base plays through); (b) some path (shader compiler, file errors) | grep PC-boot logs for `[STUB] RtlUnwind` | |
| DLC support on the Switch: v1 or later? | 3 extra recompiled engines ≈ 3x the AI2C code in the NRO | size of generated `ai2c*` after codegen | |
| Can the 1020 MHz A57 hold 30 FPS in the open world? | game thread or render thread limits | stage 7 measurements | |

## Decisions

| Date | Decision | Alternatives considered | Why |
|---|---|---|---|
| 2026-10-24 | **Renderer: Renut on plume/deko3d (sa2-nx), retargeted to XDK 6274 using the PC base's renderer as the map** (its addresses, device offsets with their source, and game-specific fixes: gamma, scissor, occlusion queries, resolve), not its engine. | (1) The PC base's renderer with a new deko3d back end. (2) A hybrid: the PC base's `d3d/` front end on a plume-deko3d implementation of its `Backend`. | Renut's deko3d back end, render-thread optimisations (SOL-REND-4: 17.6 -> 11.1 ms on sa2), shader chain and browser installer are console-proven in ~10 ports; the PC base's renderer has never run on a Switch, its back ends bypass plume (a third back end from scratch), it is Windows-bound (42 files), carries PC-only work on the hot path (interpolation, MSAA, diagnostics) and embeds game shaders. Its real value — the census and device layout of a 6274 Direct3D — is what SOL-REND-1 costs, and we get it by reading it. Option (2) is the fallback if the 6274 device turns out not to fit Renut's draw-time state reading (open question 3). |
| 2026-10-24 | SDK: the sa2-nx fork (SOL-ROUTE-1) + the PC base's DLC codegen patch ported by hand + its relative-paths patch. | Upstream 0.10.0 with the PC base's patches and a Horizon layer of our own. | The fork already has the Horizon layer and static guest modules; the PC base's other patches are PC/Xenos only. |
| 2026-10-24 | v1 links the base engine `ai2c.dll` only; the three DLC engines behind a CMake option (`NARUTO_DLC_ENGINES`), on by default once NRO size and memory are measured. | All four from the start. | Each engine is a full code module (3.8 MB XEX): 3 more of them grow the NRO and the link time before the base game boots. |
| 2026-10-24 | Frame rate on the Switch: the game's own (30 open world / 60 fights); no interpolation. | The PC base's interpolated 60 FPS. | SOL-REND-3: never decouple; interpolation is extra CPU on 1020 MHz. |

## Deviations from the default road

- **Older Direct3D than any Renut port (2.0.6274, LTCG)**: SOL-REND-1 expects matching against N&B (7645) with
  `d3d_match.py`; for this game the census comes from the PC base's hooks instead, then confirmed by call layout.
  If it works, add to solutions.md: "a PC recompilation with its own D3D-level renderer is the census".
- **Guest DLL modules (engine + 3 DLC revisions)**: not covered by the sa2-nx road; to be solved in stage 2.

## Measurements (console)

| Date | Build | Clocks | Scene | FPS / frame time spread | Game thread | Render thread | GPU |
|---|---|---|---|---|---|---|---|
