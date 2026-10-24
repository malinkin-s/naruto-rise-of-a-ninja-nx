// Nintendo Switch: the recompiled guest engine DLL (AI2C.dll) is linked into the NRO instead of being a shared library
// the runtime opens (an NRO cannot load libraries). CMakeLists.txt partially links its archive into one object, makes
// everything but its two entry points local and renames those two; they are registered here under the shared library
// name the generated module registry uses (module_registry.cpp: "naruto_AI2C"), which KernelState::LoadUserModule
// looks up first. From sa2-nx (src/sa2_static_modules.cpp, GPL-3.0).

#include <rex/system/static_modules.h>

extern "C" void ReXModule_Register_naruto_AI2C(rex::runtime::IModuleRegistrar* registrar);
extern "C" const rex::PPCImageInfo* ReXModule_GetImageInfo_naruto_AI2C();

namespace {

const bool g_registered = [] {
  rex::system::RegisterStaticModule("naruto_AI2C", ReXModule_Register_naruto_AI2C,
                                    ReXModule_GetImageInfo_naruto_AI2C);
  return true;
}();

}  // namespace
