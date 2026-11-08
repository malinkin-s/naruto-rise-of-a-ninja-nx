/**
 * @file        rex/ui/overlay/measurement_overlay.h
 * @brief       ImGui measurement OSD dialog for benchmark recording.
 */
#pragma once
#include <rex/ui/imgui_dialog.h>
#include <chrono>

namespace rex::ui {

struct MeasurementStatus {
  bool active = false;
  bool done = false;
  float elapsed_seconds = 0.0f;
  float total_duration_seconds = 30.0f;
  double live_fps = 0.0;
  double live_ms = 0.0;
  uint32_t live_draws = 0;
  char run_id[64] = "village-view-v1";
};

class MeasurementOverlayDialog : public ImGuiDialog {
 public:
  explicit MeasurementOverlayDialog(ImGuiDrawer* imgui_drawer);
  ~MeasurementOverlayDialog() override = default;

 protected:
  void OnDraw(ImGuiIO& io) override;

 private:
  bool was_active_ = false;
  std::chrono::steady_clock::time_point finish_time_{};
};

}  // namespace rex::ui

extern "C" {
void RexSwitchToggleMeasurement(void);
bool RexSwitchGetMeasurementStatus(rex::ui::MeasurementStatus* status);
}
