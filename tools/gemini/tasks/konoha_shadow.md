# Task: why Renut draws a round ground shadow as radial wedges (Konoha plaza)

Read docs/port-journal.md, entry "Ground shadow wedges in Konoha". Summary of the evidence (PC, Renut on Vulkan, and
the Switch alike; the SDK's Xenos emulation draws a smooth round dark disc there):
- The draw: PS F3B309BF6DE665D3 with VS 21FBA449AABA14E9, triangle list, 14124 indices, ~5,669 vertices, declaration
  POSITION float3 at +0, COLOR1 D3DCOLOR at +12, stride 16. VS: COLOR0 = lerp(c38, 1, pow(sat(c39.x*COLOR1.x), c39.y)),
  position = c0..c3 * POSITION. PS: oC0 = sat((COLOR0 - 1) * constColor.w + 1), multiply-style blend 04000400.
- Its state: depth_control 00708563 (stencil on, z test GEQUAL, no z write; stencil front NOTEQUAL ref 0x40 read 0x40
  write 0x40, pass REPLACE), mode_control 2 (cull back, CCW front). The stencil is only ever used as a mask in this
  frame (REPLACE with ALWAYS/EQUAL/NOTEQUAL), never incr/decr.
- Without its stencil test the disc is mostly there but whole triangles (centre to rim) are still missing; the missing
  set changes every frame as the camera moves (also with every cache off, culling off, depth clip off).
- Ruled out: index width/endian/base vertex, an index race (hashes at the call and at the read always equal), the
  vertex range, stream caches and copies (cards prove the bytes unchanged, data hashes equal), deko3d-only options,
  the GLSL passes.
Look in app/src/renut_engine/gpu/ (render/draw.cpp DrawStateLocked, PrepareGeometry, viewport/scissor code
ComputeViewport, render/pipeline.cpp, d3d hooks for Naruto in d3d/hooks/draw.cpp incl. BeginTiling/EndTiling and the
tiling extent in render/surfaces.cpp, predication/tile predication) for what could drop whole triangles of one
draw differently per frame: per-tile scissor/viewport with the window offset (vte, window offset, screen scissor
logged by "[naruto] window offset"), predicated tiling (only some tiles drawn), a guard band / clip-space
convention (PA_CL_VTE_CNTL, PA_CL_CLIP_CNTL, DX clip space vs GL), half-pixel, a w-sign issue. Propose the 3 most
likely causes with the exact code location and a cheap PC experiment for each (the PC run is deterministic:
REPLAY=tools/pc/inputs/new_game_to_autosave1.nxinput tools/pc/frames.sh NAME 60 54 2 12 '' --sa2_renderer=renut).
