#include <v8.h>
#include <v8-json.h>
#include "macro.hpp"

void macro() {
  nlohmann::json j;
  j["MinHeapExtraSizeInMB"] = v8::Isolate::MinHeapExtraSizeInMB();
}
