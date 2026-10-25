// naruto-nx: uam (app/thirdparty/uam, the console's patched deko3d shader compiler) for the installer page, as a
// WebAssembly module: compile(stage, in, out) reads GLSL from Emscripten's file system and writes the DKSH, through
// uam_api (the in-process API the console's renderer uses: the same bytes, Mesa's frontend kept between compiles,
// banjo-nx's codegen flags at their defaults). Returns 0, or 1 with the log in /uam.log.
#include <cstdio>
#include <string>
#include <vector>

#include <emscripten/emscripten.h>

#include "uam_api.h"

extern "C" EMSCRIPTEN_KEEPALIVE int uam_compile(int vertex, const char* in_path, const char* out_path) {
  static bool ready = false;
  if (!ready) {
    uam::init(true);
    ready = true;
  }
  std::string glsl;
  if (FILE* f = std::fopen(in_path, "rb")) {
    char buf[65536];
    for (size_t n; (n = std::fread(buf, 1, sizeof(buf), f)) > 0;) glsl.append(buf, n);
    std::fclose(f);
  } else {
    return 2;
  }
  const uam::Result r = uam::compile(vertex ? uam::Stage::Vertex : uam::Stage::Fragment, glsl.c_str());
  if (FILE* f = std::fopen("/uam.log", "wb")) {
    std::fwrite(r.log.data(), 1, r.log.size(), f);
    std::fclose(f);
  }
  if (!r.ok) return 1;
  FILE* f = std::fopen(out_path, "wb");
  if (!f) return 3;
  std::fwrite(r.dksh.data(), 1, r.dksh.size(), f);
  std::fclose(f);
  return 0;
}
