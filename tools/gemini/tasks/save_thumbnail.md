# Task: the save picture in the Load Game screen is a black rectangle

On the Switch (and check: on the PC with Renut), the Load Game screen shows a black rectangle on the right where the
Xbox 360 shows a picture of the place the game was saved. Find how Naruto makes and shows that picture and why it is
black here. Candidates: (a) the game takes a screenshot itself (a D3D resolve of the front/back buffer into a small
texture, or D3DDevice_... / XGraphics thumbnail helpers) and stores it in Save.dat or a separate content file, which
Renut does not support (resolves into a texture that the CPU then reads: Renut keeps resolves on the host GPU, the
guest memory stays black); (b) the XContent thumbnail (XamContentSetThumbnail / XamContentGetThumbnail /
XContentGetThumbnail in sdk/src/kernel/xam/, content_manager.cpp) is stubbed or not stored; (c) the picture is a
texture loaded from Save.dat that is decoded wrong.
Read: sdk/src/kernel/xam/*content* and their logs ("[save]" lines in out/gemini/inputs/*.log), the PC base
~/Projects/cloned/naruto-rise-recomp (does it show the picture? grep thumbnail/screenshot/Thumbnail, its docs), Renut's
resolve path (app/src/renut_engine/gpu/render/draw.cpp Resolve, render/textures.cpp "resolve destination",
banjo_renut_* cvars about readback / CPU-visible resolves, sa2-nx docs/renut-renderer.md on readbacks).
Give: the most likely mechanism with evidence (file/function), and the fix with the exact code locations.
