# Retargeting Renut to Naruto (XDK 2.0.6274, D3D9LTCG)

Renut (app/src/renut_engine, vendored unmodified from sa2-nx adf3a4e) hooks the game's Direct3D at fixed guest
addresses and reads/writes the device's private fields at fixed offsets. Both are SA2's (Direct3D 2.0.21076) in the
vendored code. Every one must be replaced with Naruto's, each with its source (docs/d3d-census.md for the functions).

## What must change

1. **Hooks** (`BANJO_RENUT_HOOK*` lines). Required for a picture (~25):
   - device: Direct3D_CreateDevice (native port of the whole creation: XenonGpu_Initialize, InitializeApiState,
     presentation parameters, the hardware path minus the GPU), D3DDevice_Release, InsertCallback,
     SynchronizeToPresentationInterval, KickOff, KickOffSegment, BeginRingBig, RingBufferDeviceAllocate,
     AllocateInlineData, the segment allocator, SetRingBufferParameters, Swap, BlockOnFence, CBlocker::Check,
     IsFencePending;
   - draws: DrawVertices, DrawIndexedVertices, DrawVerticesUP, BeginVertices (+ EndVertices / EndIndexedVertices);
   - shaders: XGRegisterVertexShader, XGRegisterPixelShader, CreateVertexDeclaration;
   - resources: D3DResource destruction, the game's XMemFree import.
   Optional (CPU speed, SOL-REND-4): the 247 state setter/getter ports (`state.cpp`); off at first, since the game's
   own setters keep the device's register image, which Renut reads at each draw.
   SA2-only, removed: widescreen hooks, the photo capture, SA2's segment allocator, pacing specifics.
2. **Private device offsets** (`d3d.h`, `d3d_native.h`, the constants at the top of `hooks/device.cpp`): Naruto's device
   is 0x5780 bytes. Sources: Naruto's own code (tools/d3d_census.py lists the offsets each function touches) and the
   PC base's renderer, which already uses many of them (fence writeback +10896, fence counter +10908, ring fields
   +14900..14920, index buffer +12428, render state words +10940..10943, ...).
3. **Shaders**: Naruto keeps its shaders in xeshader.sdb (the PC base reads it: shaders/shaders.cpp hooks 820F5150 /
   820F5348). The container dump for XenosRecomp must read that format (the PC base's shader-cache.cmake does).
4. **Build**: app/cmake/naruto_renut_gpu.cmake (from sa2's sa2_renut_gpu.cmake), DXC from the system package
   (`directx-shader-compiler`), the deko3d tools for the Switch (SPIRV-Cross, uam built for the host).

## Milestones

1. PC, plume Vulkan: the device created, the ring as a sink, fences completing, Swap presenting: the clear colour.
2. PC: shaders and draws; lockstep against the Xenos emulation with the recorded scenarios (tools/pc/scenarios).
3. Switch: deko3d back end and the shader package; a picture on the console through tools/switch/nxtest.sh.
