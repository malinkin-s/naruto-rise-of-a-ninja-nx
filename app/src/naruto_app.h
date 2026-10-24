// naruto - Naruto: Rise of a Ninja, ReXGlue recompiled project
//
// Stage 3: the SDK's defaults (emulated Xenos GPU). Game hooks come later.

#pragma once

#include <rex/rex_app.h>

class NarutoApp : public rex::ReXApp {
 public:
  using rex::ReXApp::ReXApp;

  static std::unique_ptr<rex::ui::WindowedApp> Create(rex::ui::WindowedAppContext& ctx) {
    return std::unique_ptr<NarutoApp>(new NarutoApp(ctx, "naruto", PPCImageConfig));
  }
};
