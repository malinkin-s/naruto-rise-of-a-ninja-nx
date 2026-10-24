#include "naruto_test_exit.h"
#include "naruto_test_shots.h"

#include <chrono>
#include <cstdlib>
#include <thread>

#include <rex/cvar.h>
#include <rex/logging.h>
#include <rex/logging/api.h>
#include <rex/ui/windowed_app_context.h>

REXCVAR_DEFINE_INT32(test_exit_after_s, 0, "Test",
                     "Test automation: quit after this many seconds from the title's launch, as closing the window "
                     "does (0 = never)");

namespace naruto {

void StartTestExitTimer(rex::ui::WindowedAppContext& context, std::function<void()> close_window) {
  const int32_t seconds = REXCVAR_GET(test_exit_after_s);
  if (seconds <= 0) return;
  REXLOG_INFO("test_exit_after_s: quitting in {} s", seconds);
  // Never destroyed: std::thread::detach() throws on Horizon (traps.md), and the process ends with it anyway.
  new std::thread([&context, close_window = std::move(close_window), seconds] {
    std::this_thread::sleep_for(std::chrono::seconds(seconds));
    REXLOG_INFO("test_exit_after_s: {} s reached, quitting", seconds);
    SendTestFiles();
    // Closing the window runs ReXApp::OnClosing (terminate the title, flush the log, exit), on the UI thread.
    context.CallInUIThreadDeferred(close_window);
    // If the UI thread does not get to it (a hung title), end the process anyway.
    std::this_thread::sleep_for(std::chrono::seconds(15));
    REXLOG_WARN("test_exit_after_s: no quit 15 s after the request, exiting");
    rex::FlushLogging();
    std::_Exit(0);
  });
}

}  // namespace naruto
