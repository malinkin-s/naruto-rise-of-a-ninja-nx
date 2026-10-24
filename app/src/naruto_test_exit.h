// Test runs (tools/switch/nxtest.sh, tools/pc): test_exit_after_s ends the run by itself after that many seconds from
// the title's launch, the way closing the window does, so an automated console run returns to hbmenu on its own.
#pragma once

#include <functional>

namespace rex::ui {
class WindowedAppContext;
}

namespace naruto {
// Starts the timer if test_exit_after_s > 0 (call once, after the title launched). close_window runs on the UI thread
// and should request the window's close (ReXApp::OnClosing then terminates the title, flushes the log and exits).
void StartTestExitTimer(rex::ui::WindowedAppContext& context, std::function<void()> close_window);
}  // namespace naruto
