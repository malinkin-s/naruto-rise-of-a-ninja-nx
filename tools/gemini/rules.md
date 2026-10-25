You are helping port Naruto: Rise of a Ninja (Xbox 360) to the Nintendo Switch by static recompilation (ReXGlue SDK,
the sa2-nx fork) with Renut, a Direct3D-level renderer, on deko3d. Repository: the current directory. Read
docs/port-journal.md first (the state of the port, every measurement, what was tried). The reference port this one
copies from is ~/Projects/cloned/sa2-nx (Sonic Adventure 2 on the Switch: its docs/ describe every optimisation round).

Rules:
- Research only: do not edit, create or delete any file, do not build, do not run the game.
- Never open game data or code generated from it: game/, app/generated/, out/renut_shader_dump/, out/deko3d_shaders/,
  app/out/, out/pc/renut_gpu/, *.bin, *.dksh, saves. Logs in out/gemini/inputs/ are fine.
- Be concrete: name files, functions, cvars, CMake options and the exact change; say what to measure on the console
  and how (tools/switch/nxtest.sh), and what could break. Rank by expected gain for the effort. No generic advice.
- Answer in English, as a Markdown report.
