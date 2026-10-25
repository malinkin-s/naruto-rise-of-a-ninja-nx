# Task: the codegen optimisations of sa2-nx not yet in this port

The game thread costs ~15 ms of CPU a frame in fights at stock clocks (1020 MHz), 85 % of it recompiled default.xex
code. This port has sa2-nx's codegen steps 1-3 and the store cards (app/codegen_flavor.toml, tools/post_codegen.sh,
tools/codegen.sh; journal entries "Codegen step 2", "Codegen step 3", "Store cards"). sa2-nx went much further:
read ~/Projects/cloned/sa2-nx/docs/cpu-rounds.md, docs/enhancements.md, app/perf_overrides.toml and
tools/post_codegen.py (non_argument_as_local and its keep list, fp_moves_modeless, fp_compares_modeless,
fp_mode_lookahead, indirect call promotion with tools/indirect_calls.py, inline memcalls, ro_constants, leaf/loop
locals, guest_cas, flush_mode_flow, vec_byteswap, pch_neon_shuffles, cold traps, dcbt prefetch, -fno-math-errno...).

For each step not yet here: what it does, the gain sa2-nx measured, what it needs from this game (audits, marks,
tools to port, generator options this SDK fork already has: check sdk/src/codegen/config.cpp), the risk for Naruto
(it has setjmp/longjmp at 0x822CC540/0x822CC220 and an engine DLL, AI2C), and the order to do them in. Finish with
a step-by-step plan for the first three, with the exact commands and files.
