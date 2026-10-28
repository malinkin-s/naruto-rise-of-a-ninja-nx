// naruto - Naruto: Rise of a Ninja, ReXGlue recompiled project
//
// Stage 3: the SDK's defaults (emulated Xenos GPU). Game hooks come later.

#pragma once

#include <filesystem>

#include <rex/filesystem.h>
#include <rex/rex_app.h>
#include <rex/ui/window.h>

#include "cpu/sa2_enhancements.h"
#include "naruto_pgo.h"
#include "naruto_test_exit.h"
#include "naruto_test_shots.h"

// Renut's Direct3D-level renderer (app/src/renut_engine, from sa2-nx), chosen at boot with sa2_renderer = "renut".
#if SA2_RENUT_RENDERER
#include <optional>

#include "renut_engine/gpu/banjo_renut_capture.h"
#include "renut_engine/gpu/banjo_renut_select.h"
#include "renut_engine/gpu/overlay/app_integration.h"
#include "sa2_capture.h"
#include <atomic>
#include <chrono>
#include <thread>
extern std::atomic<uint64_t> g_sa2_game_frames;  // src/sa2_capture.cpp: the recorder's game frame clock
#endif

#if defined(NARUTO_BUILTIN_CONFIG)
#include "naruto_builtin_config.h"  // generated from app/naruto_switch_defaults.toml (CMake)
#endif

class NarutoApp : public rex::ReXApp {
 public:
  using rex::ReXApp::ReXApp;

  static std::unique_ptr<rex::ui::WindowedApp> Create(rex::ui::WindowedAppContext& ctx) {
    return std::unique_ptr<NarutoApp>(new NarutoApp(ctx, "naruto", PPCImageConfig));
  }

  // Which of sa2-nx's enhancements run (own key + group master, sa2-nx src/sa2_app.h), in one line; before any guest
  // thread exists. Without this every one of them stays off: Renut's relaxed vsync (a late frame went to the next
  // refresh: 7-11 ms of sleep a frame in fights on the console), thread_signal_skip_idle, the CAS without a barrier.
  void OnPostInitLogging() override { sa2::enh::Resolve(); }

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

#if SA2_RENUT_RENDERER
  // As sa2-nx's Sa2App: with Renut no SDK graphics system and no GPU plugin; the renderer has its own swapchain and
  // thread, draws the SDK's menus through its plume drawer, and starts once the window exists.
  void OnPreSetup(rex::RuntimeConfig& config) override {
    if (banjo::renut_gpu::Active()) {
      renut::gpu::ConfigureRuntime(config);
      REXLOG_INFO("graphics: Renut's Direct3D-level renderer (sa2_renderer = renut)");
    }
  }
  std::unique_ptr<rex::ui::ImmediateDrawer> OnCreateImmediateDrawer() override {
    if (banjo::renut_gpu::Active()) return renut::gpu::CreateOverlayDrawer();
    return rex::ReXApp::OnCreateImmediateDrawer();
  }
  void OnWindowPixelSizeChanged(uint32_t pixel_width, uint32_t pixel_height) override {
    rex::ReXApp::OnWindowPixelSizeChanged(pixel_width, pixel_height);
    if (banjo::renut_gpu::Active()) renut::gpu::OnWindowResized();
  }
  std::optional<rex::PathConfig> OnFinalizePaths(const rex::PathConfig& defaults,
                                                 std::function<void(rex::PathConfig)> resume) override {
    if (banjo::renut_gpu::Active()) renut::gpu::StartRenderer(app_context(), [this] { return imgui_drawer(); });
    return rex::ReXApp::OnFinalizePaths(defaults, std::move(resume));
  }
  void OnPostSetup() override {
    // The PGO-instrumented build (NARUTO_PGO=generate) saves its counts to pgo/ every 2 minutes (nothing otherwise).
    naruto::pgo::Start();
    if (banjo::renut_gpu::Active()) {
      sa2::capture::StartWithSource([](rex::ui::RawImage& image) { return renut::gpu::CaptureFrame(image); });
      return;
    }
    // Xenos emulation (the reference picture for Renut's): frames from the SDK's presenter, as sa2-nx does. The
    // recorder paces itself by game frames, which SA2's main-loop hooks counted; Naruto has none, so a 30 Hz clock
    // stands in (a reference picture needs the moment, not the exact frame).
    new std::thread([] {
      for (;;) {
        std::this_thread::sleep_for(std::chrono::microseconds(33333));
        g_sa2_game_frames.fetch_add(1, std::memory_order_relaxed);
      }
    });
    sa2::capture::Start([this]() -> rex::ui::Presenter* {
      const auto* rt = runtime();
      const auto* graphics = rt ? rt->graphics_system() : nullptr;
      return graphics ? graphics->presenter() : nullptr;
    });
  }
  // The PGO-instrumented build saves its counts when the game loses focus (HOME menu): it may be closed from there.
  void OnWindowFocusChanged(bool focused) override {
    if (!focused) naruto::pgo::DumpNow();
  }
  void OnShutdown() override {
    if (banjo::renut_gpu::Active()) renut::gpu::ShutdownRenderer();
    sa2::capture::Stop();
    naruto::pgo::Stop();
  }
#endif

  void OnPostLaunchModule(rex::system::XThread* thread) override {
    (void)thread;
    naruto::StartTestShots();
    naruto::StartTestExitTimer(app_context(), [this] {
      if (window()) window()->RequestClose();
    });
  }

  // Without a naruto.toml next to the NRO, the player's default one is written there (app/naruto_switch.toml).
  std::string_view DefaultConfigFile() const override {
#if defined(NARUTO_BUILTIN_CONFIG)
    return kNarutoPlayerConfig;
#else
    return {};
#endif
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
