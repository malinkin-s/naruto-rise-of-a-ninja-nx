# Task: GPU time on the Switch (deko3d), fights and the open world

At stock handheld clocks (GPU 460.8 MHz) fights are GPU-bound: 21-31 ms of GPU a frame at 1280x720 (8-16 ms at
853x480). out/gemini/inputs/fight_gpu_shaders_nx.log holds "GPU profile" blocks split by pixel shader
(renut_gpu_profile + banjo_renut_diag_gpu_shaders: ms per frame, draws per frame, "blended"); the scene pass is
15-28 ms. The heaviest pixel shaders are trivial (one texture, fog, alpha test), the scene is 4x MSAA on the 360
(naruto_guest_msaa_max = 1 gained only 8-10 %). A 768 MHz run cut GPU time ~30 %. ~40 fragment barriers, ~6 full
barriers and ~7 texture uploads a frame (the "[renut] deko3d:" lines of out/gemini/inputs/fight_stock_nx.log).

Using sa2-nx's and banjo-nx's GPU work (~/Projects/cloned/sa2-nx/docs/gpu-optimisation-candidates.md,
docs/renut-renderer.md, docs/deko3d-renderer-guide.md, the banjo_deko3d_* / banjo_gpu_* / banjo_renut_* cvars in
app/src/renut_engine/gpu/banjo_renut_tuning.cpp and their defaults, tools/deko3d_glsl_opt.py passes):
1. Read the profile: is it fill, blending, overdraw, vertex or barrier bound? Which shaders/targets dominate.
2. Which off-by-default options to A/B on the console for Naruto (each: cvar, what it does, why it may help here,
   risk), e.g. banjo_deko3d_alpha_spec, banjo_renut_blend_skip, gpr32, latency trim, depth-only paths, MSAA handling.
3. Why barriers happen per frame here (resolves, render-to-texture, texture uploads) and how sa2-nx reduced them.
4. Anything specific to Naruto's tiled 4x MSAA scene (BeginTiling/EndTiling hooks in
   app/src/renut_engine/gpu/d3d/hooks/draw.cpp, render/surfaces.cpp) that wastes GPU time on the host.
