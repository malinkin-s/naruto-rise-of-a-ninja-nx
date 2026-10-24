# Naruto's Direct3D (XDK 2.0.6274, D3D9LTCG): census for Renut (SOL-REND-1)

Sources: `tools/d3d_census.py` (call graph of the generated code, kernel imports, GPU MMIO, device offsets) and the
hooks of jorjbarbosa/naruto-rise-recomp's renderer (`app/src/gpu/`, checked at 93feca6; "PC base" below).
No reference image (N&B, SA2) is available, so `d3d_match.py` cannot be used: each function is named by its evidence.
Status: hypothesis until a Renut hook on it works.

## Device layout

Public device as N&B / SA2 (Renut's `d3d.h`): fetch constants at +0x480, register packets 0x2000 at +10368 (0x2880,
DestinationPacket), 0x2100 at +10444 (0x28CC, ValuesPacket), 0x2200 at +10548 (0x2934, ControlPacket) — PC base
`d3d/state.cpp:137-141`, `d3d/draw.cpp:475-479`. The private part differs: device 22,400 bytes (0x5780; N&B 0x5E00,
SA2 0x6080; PC base `d3d/device.h:575`); index buffer header at +12428 (N&B 0x3094 = 12436).

## Functions

| Naruto | Renut's function (hypothesis) | Evidence |
|---|---|---|
| 8213ECE8 | Direct3D_CreateDevice | calls VdInitializeEngines, VdSetGraphicsInterruptCallback, VdIsHSIOTrainingSucceeded; PC base "Device creation" |
| 8213EF10 | device destruction | VdShutdownEngines, VdSetGraphicsInterruptCallback; PC base: last reference destroys the device |
| 82138A20 | D3DDevice_Swap (CDevice swap) | the only caller of VdSwap and VdGetSystemCommandBuffer; also VdSetDisplayMode, VdPersistDisplay |
| 8212FA80 | ring initialisation (RingBufferDeviceAllocate side) | VdInitializeRingBuffer, VdEnableRingBufferRPtrWriteBack, MmGetPhysicalAddress |
| 8212EF28 | KickOff (internal) | writes CP_RB_WPTR (lis 0x7FC8, +0x714); called by 8212F530, 82146C48, 82147370 |
| 8212F530 | KickOff | calls 8212EF28; called by 8212F608 |
| 8212F608 | ring reserve (MakeSpace / BeginRing) | 63 instructions, 43 callers; calls EA18, F0D0, F3A8, F530, F708; PC base "RingReserve" |
| 8212F708 | BlockOnFence | fence counter +10908, writeback +10896; PC base "BlockOnFence: console fence protocol" |
| 8212EA18 | segment allocator | critical section, ring fields +14900..14920; called by BeginVertices, the draws |
| 82137E00 | DrawIndexedVertices | no direct caller (through a table), index buffer +12428; PC base StateNoteDraw mode 0 |
| 82137A18 | DrawVertices | no direct caller; PC base StateNoteDraw mode 1 |
| 821375A0 | BeginVertices (LTCG-specialised) | PC base comment; calls EA18 |
| 821384F0 | (Swap / Resolve helper: fence insert?) | called by Swap and 5 others; calls F608, F7E0 |
| 821280B0 | (render target / viewport commit) | called by Swap, Resolve, 8213AC80, CreateDevice; PC base: serializes through 82128270 |
| 82128270 | window scissor / viewport writer | PC base: SetRenderTarget, SetDepthStencilSurface, SetViewport serialize only through it |
| 82131018 | D3DDevice_ClearF | PC base; calls 82130988 |
| 8213A7E0 | D3DDevice_Resolve | 1 caller; packets 0x2000 (+10368); calls ClearF |
| 821398C8, 8213AC80 | tiling (begin / end) | PC base `d3d/pass.cpp`: per-tile clears |
| 8212D750 | D3DResource_Destroy | PC base "Resource destruction (from D3DResource_Release at refcount zero)" |
| 8212F950 | graphics interrupt callback | MMIO, spin lock; `SetInterruptCallback(8212F950, ...)` in the PC log |
| 82138258, 82138358 | interrupt-time flip / vblank | write D1GRPH surface address (0x7FC86110) |
| 8212B3E0 | SetGammaRamp | PC base |
| 8213B570, 8213B7F8 | D3DQuery_Issue / GetData | PC base `d3d/query.cpp` |

Still to find: InsertCallback, SynchronizeToPresentationInterval, KickOffSegment, the inline (UP) allocator,
DrawVerticesUP, XGRegisterVertexShader / PixelShader (Naruto loads its shaders from xeshader.sdb: PC base
`shaders/shaders.cpp` hooks 820F5150 / 820F5348), CreateVertexDeclaration, IsFencePending, CBlocker::Check.
