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

