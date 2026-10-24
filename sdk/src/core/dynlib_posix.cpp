#include <rex/platform.h>
#include <rex/platform/dynlib.h>

static_assert(REX_PLATFORM_LINUX || REX_PLATFORM_MAC, "This file is POSIX-only");

#include <dlfcn.h>

#include <system_error>
#include <vector>

#include <rex/logging.h>

namespace rex::platform {

DynamicLibrary::~DynamicLibrary() {
  Close();
}

DynamicLibrary::DynamicLibrary(DynamicLibrary&& other) noexcept : handle_(other.handle_) {
  other.handle_ = nullptr;
}

DynamicLibrary& DynamicLibrary::operator=(DynamicLibrary&& other) noexcept {
  if (this != &other) {
    Close();
    handle_ = other.handle_;
    other.handle_ = nullptr;
  }
  return *this;
}

bool DynamicLibrary::Load(const std::filesystem::path& path, SymbolResolution mode) {
  Close();
  int flags = (mode == SymbolResolution::kImmediate) ? RTLD_NOW : RTLD_LAZY;
  // A bare module name ("naruto_AI2C", what the generated module registry passes) is what Windows' LoadLibrary
  // resolves next to the executable with ".dll" appended; dlopen takes it literally and fails. Try
  // lib<name>.so and <name>.so next to the executable, then the loader's search path (naruto-nx, 2026-10-24).
  std::vector<std::filesystem::path> candidates;
  if (!path.has_parent_path() && !path.has_extension()) {
    std::error_code ec;
    auto exe_dir = std::filesystem::read_symlink("/proc/self/exe", ec).parent_path();
    const char* ext = REX_PLATFORM_MAC ? ".dylib" : ".so";
    for (const auto& name : {"lib" + path.string() + ext, path.string() + ext}) {
      if (!ec)
        candidates.push_back(exe_dir / name);
      candidates.emplace_back(name);
    }
  }
  candidates.push_back(path);
  for (const auto& candidate : candidates) {
    handle_ = dlopen(candidate.c_str(), flags);
    if (handle_)
      return true;
  }
  REXLOG_WARN("dlopen({}) failed: {}", candidates.back().string(), dlerror());
  return false;
}

void DynamicLibrary::Close() {
  if (handle_) {
    dlclose(handle_);
    handle_ = nullptr;
  }
}

void* DynamicLibrary::GetRawSymbol(const char* name) const {
  if (!handle_)
    return nullptr;
  return dlsym(handle_, name);
}

}  // namespace rex::platform
