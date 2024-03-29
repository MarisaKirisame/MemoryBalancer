#include <v8.h>
#include <iostream>

#include "macro.hpp"
#include "hyperparam.hpp"
#include "nlohmann/json.hpp"

size_t bytes_to_mb(size_t b) {
  assert(b % bytes_in_mb == 0);
  return b / bytes_in_mb;
}

void macro() {
  nlohmann::json j;
  j["BiasInWorkingMemoryInMB"] = bytes_to_mb(bias_in_working_memory);
  // B->MB = /1e6, NS->S=*1e9
  j["InitialGCSpeedInMBPerSec"] = initial_garbage_bytes / initial_garbage_duration * 1000;
  j["GarbageRateDecayPerSec"] = garbage_rate_decay_per_sec;
  j["GCSpeedSmoothingPerSample"] = gc_speed_smoothing_per_sample;
  j["TotalMemoryFloorInMB"] = bytes_to_mb(total_memory_floor);
  j["ExtraFloorInMB"] = bytes_to_mb(extra_memory_floor);
  std::cout << j << std::endl;
}
