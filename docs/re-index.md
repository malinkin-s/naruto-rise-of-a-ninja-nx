# Game Function Index (`tools/re/index.py`)

Static analysis tooling for the recompiled codebase. Because REA does not directly open Xbox 360 PE/COFF images (machine `0x01f2`) without PowerPC disassembly in raw-binary mode, the recompiled C++ in `app/generated/` serves as human-readable source code (each line retains the original PowerPC instruction in comments).

`tools/re/index.py` builds a symbol cross-reference index across all 29,967 functions in `default.xex` and `AI2C`: function sizes, FP/vector/indirect call statistics, referenced string literals (addresses from `lis`/`addi` pairs, string tables from module images), caller/callee trees, and string tags. It is read-only and requires no compilation (`out/re/index.json`, outside Git).

```bash
python3 tools/re/index.py build
python3 tools/re/index.py find FadeDist        # find who references a string
python3 tools/re/index.py func 825DA240        # inspect single function
python3 tools/re/index.py callers 82137E00 -d 3
python3 tools/re/index.py tag vegetation
python3 tools/re/index.py hot FILE             # FILE: "ADDR weight" lines -> index entries sorted by weight
```

## Static Findings (No Run Required)

- **No Named Cull/LOD Distances:** The engine lacks string-based `cull` or `lod` distance parameters; visibility and distance thresholds are embedded in data assets. The only related named identifiers are `_f_FullFadeDist` / `_f_BeginFadeDist` (parameter checks in `ai2c` `sub_881EE440`), `_vVegetationWindParams` (foliage wind: vertex shader, does not affect draw count), and `NearFarCtrl` (camera).
- **Draw Call Pipeline:** `T_820F02C0` (`sub_820F02C0`) → `sub_820FC008` → `sub_820F2470` / `sub_82120FF8` → 32 emitter functions (`0x82102890`…`0x82120FF8`, one per primitive/material type) → `sub_821024A8` → `D3DDevice_DrawIndexedVertices` (`sub_82137E00`) and `DrawVertices` (`sub_82137A18`). Three emitters (`82105648`, `82107498`, `821039A0`) are called through the dispatcher `sub_820FD5F8` via jump tables (see `app/indirect_promotions.txt`).
- **Culling Location:** Draw inclusion decisions are made upstream in `Main XThread` when command packets are queued for worker thread `T_820F02C0`. Skipping draws inside emitters saves render thread and `T_820F02C0` time; saving `Main XThread` time requires locating the queue enqueue point.

## Frame Structure in Thread `T_820F02C0` (`sub_820F02C0`, `sub_820FC008`, `sub_820FC2E0`, `sub_820FD5F8`)

- The main thread builds a frame packet (3,208 bytes, double-buffered: index `(counter - 1) & 1`, counter at structure offset +6416). Thread `T_820F02C0` loops, takes the packet (mode 1 = draw, 2 = exit), and invokes `sub_820FC008(packet)`.
- The packet contains a linked list of render items with its head at offset **+2240**, linked by field **+216** (item size 216 bytes). `sub_820FC2E0` traverses the list and invokes `sub_820FD5F8(packet, item)` for each element (state setup followed by primitive emitters). Pass lists at +2288 and +2504 (up to 9 groups of 20 bytes) are traversed by `sub_820FC9C0`.
- Each list item is a complete unit that can be culled as a batch (saving `T_820F02C0`, `CaptureDelta`, and render thread time). Item contents (+8 flags, +12 / +28 material and vertex buffer references, +24 sub-item count) require console logging to correlate with foliage clusters.
