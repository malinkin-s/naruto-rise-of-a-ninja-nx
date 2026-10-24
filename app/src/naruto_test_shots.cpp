// Test runs: frames of the game sent over the network with the log (tools/switch/nxtest.sh, PC runs too).
// test_shots = "20,40,60": at those seconds from the title's launch the renderer's frame (Renut's CaptureFrame: the
// image it presents, on deko3d too) is halved and sent over its own TCP connection to log_network's host:port as
// "NXSHOT <second> <width> <height> <bytes>\n" + R8G8B8X8 rows. The PC's listener writes out/runs/<name>/shot_<s>.png.
// Nothing touches the screen of the PC (frame grabs there crashed the desktop's compositor).

#include "naruto_test_shots.h"

#include <arpa/inet.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <unistd.h>

#include <chrono>
#include <cstdlib>
#include <string>
#include <thread>
#include <vector>

#include <fmt/format.h>
#include <rex/cvar.h>
#include <rex/logging.h>
#include <rex/ui/presenter.h>

#if SA2_RENUT_RENDERER
#include "renut_engine/gpu/banjo_renut_capture.h"
#include "renut_engine/gpu/banjo_renut_select.h"
#endif

REXCVAR_DEFINE_STRING(test_shots, "", "Test",
                      "Test automation: seconds from the title's launch (comma separated) at which a frame is sent to "
                      "log_network's listener (tools/switch/nxtest.sh writes them as PNG)");

namespace naruto {
namespace {

bool SendAll(int fd, const void* data, size_t size) {
  const auto* p = static_cast<const uint8_t*>(data);
  while (size) {
    const ssize_t n = send(fd, p, size, 0);
    if (n <= 0) return false;
    p += n;
    size -= size_t(n);
  }
  return true;
}

bool SendShot(const std::string& target, int second, const rex::ui::RawImage& image) {
  const size_t colon = target.rfind(':');
  if (colon == std::string::npos) return false;
  // Halved by 2x2 averaging: a quarter of the bytes over the console's Wi-Fi.
  const uint32_t w = image.width / 2, h = image.height / 2;
  std::vector<uint8_t> half(size_t(w) * h * 4);
  for (uint32_t y = 0; y < h; ++y)
    for (uint32_t x = 0; x < w; ++x)
      for (int c = 0; c < 4; ++c) {
        const uint8_t* r0 = image.data.data() + size_t(2 * y) * image.stride + size_t(2 * x) * 4 + c;
        const uint8_t* r1 = r0 + image.stride;
        half[(size_t(y) * w + x) * 4 + c] = uint8_t((r0[0] + r0[4] + r1[0] + r1[4] + 2) / 4);
      }
  sockaddr_in addr{};
  addr.sin_family = AF_INET;
  addr.sin_port = htons(uint16_t(std::atoi(target.c_str() + colon + 1)));
  if (inet_pton(AF_INET, target.substr(0, colon).c_str(), &addr.sin_addr) != 1) return false;
  const int fd = socket(AF_INET, SOCK_STREAM, 0);
  if (fd < 0) return false;
  bool ok = connect(fd, reinterpret_cast<sockaddr*>(&addr), sizeof(addr)) == 0;
  const std::string header = fmt::format("NXSHOT {} {} {} {}\n", second, w, h, half.size());
  ok = ok && SendAll(fd, header.data(), header.size()) && SendAll(fd, half.data(), half.size());
  close(fd);
  return ok;
}

}  // namespace

void StartTestShots() {
  const std::string list = REXCVAR_GET(test_shots);
  const std::string target = rex::cvar::GetFlagByName("log_network");
  if (list.empty()) return;
  if (target.empty()) {
    REXLOG_WARN("test_shots: no log_network listener to send the frames to");
    return;
  }
  std::vector<int> seconds;
  for (size_t at = 0; at < list.size();) {
    const size_t end = std::min(list.find(',', at), list.size());
    if (const int s = std::atoi(list.substr(at, end - at).c_str()); s > 0) seconds.push_back(s);
    at = end + 1;
  }
  REXLOG_INFO("test_shots: {} frames to {}", seconds.size(), target);
  // Never destroyed: std::thread::detach() throws on Horizon (traps.md); the process ends with it.
  new std::thread([seconds, target] {
    const auto start = std::chrono::steady_clock::now();
    for (const int s : seconds) {
      std::this_thread::sleep_until(start + std::chrono::seconds(s));
      rex::ui::RawImage image;
      bool captured = false;
#if SA2_RENUT_RENDERER
      captured = banjo::renut_gpu::Active() && renut::gpu::CaptureFrame(image, 2000);
#endif
      if (!captured || image.width < 2 || image.height < 2) {
        REXLOG_WARN("test_shots: no frame at {} s", s);
        continue;
      }
      const bool sent = SendShot(target, s, image);
      REXLOG_INFO("test_shots: frame at {} s ({}x{}) {}", s, image.width, image.height, sent ? "sent" : "NOT sent");
    }
  });
}

}  // namespace naruto
