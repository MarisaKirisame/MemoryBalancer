#pragma once

#include <string>
#include <condition_variable>
#include <iostream>
#include <vector>

namespace v8 {
  class Platform;
}

void v8_experiment(v8::Platform* platform, const std::vector<char*>& args);
