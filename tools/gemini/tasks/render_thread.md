# Task: Renut's render thread on the Switch

In the open world (Konoha) the render thread costs 15-37 ms a frame for ~2,000-2,900 draws (~13 us a draw) at stock
clocks: out/gemini/inputs/konoha_stock_nx.log; fights 7-14 ms (out/gemini/inputs/fight_stock_nx.log). The "[renut]"
10-second lines report each render-thread optimisation; several show 0 here: "SharedConstants reused by 0
(banjo_renut_shared_dedupe)", "specialised bools: 0 draws", "cached streams" counts, "pipeline binds" vs draws,
"pushed constants", "device snapshots" (bytes kept a draw), "upload ring", "depth hand-over", "[cards]".

1. Go through those lines and the code behind each counter (app/src/renut_engine/gpu/, banjo_renut_tuning.cpp,
   render/draw.cpp, backend/queued.cpp) and say which optimisations are inactive or ineffective for Naruto and why
   (a hook that only exists for SA2/N&B behind RENUT_SA2_ONLY, a device offset of Naruto's XDK 6274 layout in
   gpu/d3d/d3d.h / d3d_native.h marked UNVERIFIED, a feature keyed to SA2's shaders), with the fix.
2. Where the ~13 us a draw goes (state reading from the device snapshot, constants, pipeline lookup, stream checks,
   deko3d command recording) and the cheapest reductions sa2-nx/banjo-nx used (docs/renut-renderer.md, docs on the
   render-thread rounds).
3. A ranked list of console A/B experiments (cvar or code change, expected gain).
