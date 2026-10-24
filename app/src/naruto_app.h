// naruto - Naruto: Rise of a Ninja, ReXGlue recompiled project
//
// Stage 3: the SDK's defaults (emulated Xenos GPU). Game hooks come later.

#pragma once

#include <filesystem>

#include <rex/filesystem.h>
#include <rex/rex_app.h>
#include <rex/ui/window.h>

#include "naruto_test_exit.h"

#if defined(NARUTO_BUILTIN_CONFIG)
#include "naruto_builtin_config.h"  // generated from app/naruto_switch_defaults.toml (CMake)
#endif

class NarutoApp : public rex::ReXApp {
 public:
  using rex::ReXApp::ReXApp;

  static std::unique_ptr<rex::ui::WindowedApp> Create(rex::ui::WindowedAppContext& ctx) {
    return std::unique_ptr<NarutoApp>(new NarutoApp(ctx, "naruto", PPCImageConfig));
  }

  // Without --game_data_root, use a game/ folder next to the executable (on the Switch: sdmc:/switch/naruto-nx/game) or
  // in a parent folder (a PC build tree: the repository's game/). An explicit path always wins. From sa2-nx
  // (src/sa2_app.h): the built-in config is read after the paths are set, so it cannot carry game_data_root.
  void OnConfigurePaths(rex::PathConfig& paths) override {
    if (!paths.game_data_root.empty()) return;
    std::error_code ec;
    for (auto dir = rex::filesystem::GetExecutableFolder(); !dir.empty(); dir = dir.parent_path()) {
      if (std::filesystem::is_regular_file(dir / "game" / "default.xex", ec)) {
        paths.game_data_root = dir / "game";
        return;
      }
      if (dir == dir.parent_path()) break;
    }
  }

  void OnPostLaunchModule(rex::system::XThread* thread) override {
    (void)thread;
    naruto::StartTestExitTimer(app_context(), [this] {
      if (window()) window()->RequestClose();
    });
  }

  // The Switch build's fixed settings (app/naruto_switch_defaults.toml, compiled in), applied before naruto.toml.
  std::string_view BuiltInConfig() const override {
#if defined(NARUTO_BUILTIN_CONFIG)
    return kNarutoBuiltInConfig;
#else
    return {};
#endif
  }
};
