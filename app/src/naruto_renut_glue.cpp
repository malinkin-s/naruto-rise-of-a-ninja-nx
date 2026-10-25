// naruto-nx: the symbols Renut's vendored code (app/src/renut_engine, from sa2-nx) takes from sa2-nx's application,
// defined for Naruto. Each names where sa2-nx defines it.

#include <rex/cvar.h>

#include "cpu/sa2_enhancements.h"

// sa2-nx me/me_native_system.cpp: relaxed vsync (a late frame goes at once, SOL-REND-5), read by the pacing.
SA2_ENHANCEMENT(g_vsync_relaxed, sa2_vsync_relaxed, sa2::enh::kNonCpu, true,
                "Relaxed vsync: a frame that misses its vertical blank is shown at once instead of waiting for the next");

// sa2-nx cpu/sa2_hot_guest.cpp: whether the generated code marks store cards (tools/store_cards.py). Weak false here;
// tools/post_codegen.sh appends the strong `true` to the generated code when it marks them, so a build of code without
// the cards (NARUTO_CLASSIC) can never trust them (Renut would keep stale vertex and index copies).
extern "C" __attribute__((weak)) const bool g_banjo_store_cards = false;

// sa2-nx me/me_pc_stubs.cpp: the Switch profiler's counters, no-ops on the PC.
#if !REX_PLATFORM_SWITCH
extern "C" void RexSwitchPerfCount(unsigned) {}
#endif

// sa2-nx cpu/sa2_codegen_checks.cpp and sa2_forms_selfcheck.cpp: checks of SA2's codegen flavour; none for Naruto yet.
namespace sa2::enh {
void CodegenChecksInit() {}
void CodegenChecksReport(int) {}
void FormsSelfCheck() {}
}  // namespace sa2::enh
