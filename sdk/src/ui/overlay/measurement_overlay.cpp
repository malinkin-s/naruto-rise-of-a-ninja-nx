/**
 * @file        ui/overlay/measurement_overlay.cpp
 * @brief       ImGui measurement OSD dialog for benchmark recording.
 */
#include <rex/ui/overlay/measurement_overlay.h>
#include <imgui.h>
#include <algorithm>
#include <cmath>

namespace rex::ui {

MeasurementOverlayDialog::MeasurementOverlayDialog(ImGuiDrawer* imgui_drawer)
    : ImGuiDialog(imgui_drawer) {}

void MeasurementOverlayDialog::OnDraw(ImGuiIO& io) {
  MeasurementStatus status{};
  if (!RexSwitchGetMeasurementStatus(&status)) {
    Close();
    return;
  }

  const auto now = std::chrono::steady_clock::now();
  if (status.active) {
    was_active_ = true;
    finish_time_ = {};
  } else if (was_active_ && finish_time_ == std::chrono::steady_clock::time_point{}) {
    finish_time_ = now;
  }

  if (!status.active && !was_active_) {
    Close();
    return;
  }

  // Display completion banner for 3.5 seconds after finish, then close
  if (!status.active && was_active_) {
    const float age = std::chrono::duration<float>(now - finish_time_).count();
    if (age >= 3.5f) {
      Close();
      return;
    }
  }

  // Position in upper right corner, slightly below screen edge
  const float width = 320.0f;
  const float margin = 20.0f;
  ImGui::SetNextWindowPos(ImVec2(io.DisplaySize.x - width - margin, margin), ImGuiCond_Always);
  ImGui::SetNextWindowSize(ImVec2(width, 0.0f), ImGuiCond_Always);
  ImGui::SetNextWindowBgAlpha(0.80f);

  const ImGuiWindowFlags flags = ImGuiWindowFlags_NoDecoration | ImGuiWindowFlags_AlwaysAutoResize |
                                 ImGuiWindowFlags_NoSavedSettings | ImGuiWindowFlags_NoFocusOnAppearing |
                                 ImGuiWindowFlags_NoNav | ImGuiWindowFlags_NoMove;

  if (ImGui::Begin("##MeasurementOSD", nullptr, flags)) {
    if (status.active) {
      // Pulsing red REC indicator
      const float time = float(ImGui::GetTime());
      const float pulse = (std::sin(time * 6.0f) + 1.0f) * 0.5f;
      ImGui::TextColored(ImVec4(1.0f, 0.2f * pulse, 0.2f * pulse, 1.0f), "[● REC]");
      ImGui::SameLine();
      ImGui::Text("%s", status.run_id);

      const float fraction = status.total_duration_seconds > 0.0f
                                 ? std::clamp(status.elapsed_seconds / status.total_duration_seconds, 0.0f, 1.0f)
                                 : 0.0f;
      ImGui::ProgressBar(fraction, ImVec2(-1.0f, 8.0f), "");

      ImGui::Text("%.1fs / %.0fs  |  %.1f FPS (%.1f ms)",
                  status.elapsed_seconds, status.total_duration_seconds,
                  status.live_fps, status.live_ms);
      if (status.live_draws > 0) {
        ImGui::Text("Draws/frame: %u", status.live_draws);
      }
    } else {
      // Green DONE indicator
      ImGui::TextColored(ImVec4(0.2f, 1.0f, 0.2f, 1.0f), "[✓ DONE]");
      ImGui::SameLine();
      ImGui::Text("%s", status.run_id);
      ImGui::Separator();
      ImGui::Text("Benchmark saved to log.");
      ImGui::Text("Result: %.1f FPS", status.live_fps);
    }
  }
  ImGui::End();
}

}  // namespace rex::ui
