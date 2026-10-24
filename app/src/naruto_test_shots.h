// Test runs: frames sent over the network with the log (src/naruto_test_shots.cpp, test_shots).
#pragma once

namespace naruto {
// Starts the sender if test_shots is set (call once, after the title launched).
void StartTestShots();
// Sends the console's profile report (logs/rex/rex_profile.log) to log_network's listener; Switch only.
void SendTestFiles();
}  // namespace naruto
