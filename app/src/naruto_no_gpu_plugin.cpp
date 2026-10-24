// Nintendo Switch, stage 6 first boot: no GPU plugin is linked (the renderer, Renut on deko3d, comes next). The SDK's
// static plugin loader (sdk/src/system/gpu_plugin_loader.cpp) references the xenos plugin's two entry points; these
// answer "no plugin", so a gpu_plugin setting fails with a log line instead of the link failing.

#include <cstdint>

#include <rex/system/gpu_plugin.h>

extern "C" uint32_t rex_gpu_abi_version(void) { return 0; }
extern "C" rex::system::IGraphicsSystem* rex_gpu_create(uint32_t, const rex::system::GpuCreateInfo*) {
  return nullptr;
}
