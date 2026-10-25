# Task: the game thread's time outside the recompiled code, and the other CPU threads

Console profile of a fight at stock clocks: out/gemini/inputs/fight_stock_profile.log (rex_profile.log: per 10 s,
each thread's CPU, libnx calls, waits). Renut's log of the same run: out/gemini/inputs/fight_stock_nx.log. Earlier,
stack samples of the game thread ("Main XThread") put ~9.5 % in the SDK runtime: FunctionDispatcher::GetFunction
(indirect calls), RtlEnterCriticalSection/Leave, BaseHeap::AllocRange, mutexLock/Unlock, __savegprlr helpers (the
last ones are gone since codegen step 3).

1. From the profile: which threads besides the game thread cost CPU (XMA decoder, audio worker, XThreads), how much,
   on which cores; is core placement sensible (the game thread is alone on core 0? the render thread on core 1?).
   Read sdk/src/ui/switch_perf.cpp for what each line means.
2. What sa2-nx did for the runtime part: native replacements of hot guest functions (memcpy/memset/memmove, math,
   matrix code: ~/Projects/cloned/sa2-nx/app/src/cpu/, docs/enhancements.md "native"), the critical-section and
   kernel paths, thread priorities/cores (sa2_main_thread_priority, banjo_ring_core), XMA on a worker
   (the "[xma]" lines). Which apply to Naruto, how to find Naruto's own hot CRT functions (memcpy etc. in default.xex:
   their addresses can be found from the PC base ~/Projects/cloned/naruto-rise-recomp, which hooks some), and the
   expected gain.
3. A plan to get a correct game-thread profile with symbols (NX_PROFILE=1 tools/switch/nxtest.sh with the run's ELF
   kept in out/runs/NAME/naruto.elf, tools/switch_profile_report.py) and what to look for in it.
