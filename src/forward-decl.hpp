#pragma once

#include <memory>
#include <iostream>
#include <cmath>
#include <iostream>
#include <sstream>

struct RuntimeNode;
using Runtime = std::shared_ptr<RuntimeNode>;

struct ControllerNode;
using Controller = std::shared_ptr<ControllerNode>;

enum class OptimizeFor { time, throughput };

struct HeuristicConfig {
  bool weight_work_left;
  OptimizeFor opt; // if optimizing for throughput, weight_work_left must = false. doesnt make sense to weight work.
};

