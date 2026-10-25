# Task: the open world (Konoha) on the Switch: what to optimise next

At stock clocks (CPU 1020 MHz, GPU 460 MHz) the story mode in Konoha runs at about 20 FPS; with the CPU overclocked
to 1785 MHz it is nearly a stable 30 (the game's logic runs at 30 there): the CPU is the limit in the open world.
Logs: out/gemini/inputs/konoha_stock_nx.log (Renut, before store cards), and the journal's entries. The game thread
"Main XThread" plus several guest XThreads; the render thread ~13 us a draw for 2,000-2,900 draws.
Read your own earlier reports in out/gemini/plans/ (cpu_threads_and_runtime_plan.md, renut_render_thread_plan.md,
sa2_nx_codegen_optimizations_plan.md) and the current state of app/codegen_flavor.toml (float-mode options are now
on) and propose the next 5 changes by expected gain for the open world specifically, with the exact steps, and how to
measure each with tools/switch/nxtest.sh (a recorded pad session of Konoha replays with --input_replay; frames,
profile with NX_PROFILE=1 NX_PROFILE_THREADS=Main, "[renut]" lines). Prefer changes that need no game-specific audit
first.
