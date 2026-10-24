// naruto - Naruto: Rise of a Ninja, ReXGlue recompiled project
//
// Stage 3: the SDK's defaults (emulated Xenos GPU). Game hooks come later.

#pragma once

#include <rex/rex_app.h>

#if defined(NARUTO_BUILTIN_CONFIG)
#include "naruto_builtin_config.h"  // generated from app/naruto_switch_defaults.toml (CMake)
#endif

class NarutoApp : public rex::ReXApp {
 public:
  using rex::ReXApp::ReXApp;

  static std::unique_ptr<rex::ui::WindowedApp> Create(rex::ui::WindowedAppContext& ctx) {
    return std::unique_ptr<NarutoApp>(new NarutoApp(ctx, "naruto", PPCImageConfig));
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
