// naruto-nx: the few calls src/sa2_capture.cpp (from sa2-nx) makes into SA2's own PM4 renderer, which this port does
// not have. With Renut the capture takes its frames from the renderer (StartWithSource); these keep the other path
// compiling and inert.
#pragma once

#include <cstdint>

namespace me::native {
inline uint64_t PresentedSwaps() { return 0; }
inline void SetPresentHook(void (*)(uint64_t)) {}
}  // namespace me::native
