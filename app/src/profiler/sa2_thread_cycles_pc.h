// naruto-nx: sa2-nx's per-thread cycle snapshot (Windows only there) as used by src/sa2_capture.cpp; empty here.
#pragma once

#include <cstdint>
#include <string>
#include <vector>

namespace sa2::profile {
struct ThreadCycles {
  unsigned long id = 0;
  std::string name;
  uint64_t cycles = 0;
};
inline std::vector<ThreadCycles> SnapshotThreadCycles() { return {}; }
}  // namespace sa2::profile
