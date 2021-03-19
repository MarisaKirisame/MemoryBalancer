#pragma once

#include <memory>
#include <iostream>

#include <boost/thread/synchronized_value.hpp>

struct RuntimeNode;
using Runtime = std::shared_ptr<RuntimeNode>;

struct ControllerNode;
using Controller = std::shared_ptr<ControllerNode>;

