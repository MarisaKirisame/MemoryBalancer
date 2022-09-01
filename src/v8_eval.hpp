#pragma once

#include <string>
#include <condition_variable>
#include <iostream>
#include <vector>

struct Input {
  size_t heap_size;
  std::string code_path;
};

namespace v8 {
  class Platform;
}
void v8_experiment(v8::Platform* platform, const std::vector<char*>& args);
