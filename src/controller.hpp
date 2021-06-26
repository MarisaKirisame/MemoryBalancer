#pragma once
#include <memory>
#include <set>
#include <assert.h>
#include <vector>
#include <iostream>
#include <mutex>
#include "forward-decl.hpp"

// Since the controller is to be used by multiple runtime,
// there are basically three flavor of methods on this class:
// 0: the unsync_xxx function that does not lock. this is the implementation of the code.
// 1: the Guard
struct ControllerNode : std::enable_shared_from_this<ControllerNode> {
  struct LockNode {
    std::shared_ptr<ControllerNode> controller;
    LockNode() = delete;
    LockNode(const LockNode&) = delete;
    LockNode(const std::shared_ptr<ControllerNode>& controller) : controller(controller) {
      controller->m.lock();
    }
    ~LockNode() {
      controller->m.unlock();
    }
  };
  using Lock = std::shared_ptr<LockNode>;
protected:
  // this look like weak_ptr, but the content should always be here:
  // whenever a runtimenode gone out of life it will notify the controller, and get it removed.5
  std::set<std::weak_ptr<RuntimeNode>, std::owner_less<std::weak_ptr<RuntimeNode>>> runtimes_;
  size_t max_memory_ = 0;
  size_t used_memory_ = 0;
  size_t working_memory_ = 0;
  std::recursive_mutex m;
  virtual void free_max_memory_aux(size_t memory_freed, const Lock&) { }
  virtual void set_max_memory_aux(size_t max_memory_, const Lock&) { }
  virtual void add_runtime_aux(const Runtime& r, const Lock&) { }
  virtual void remove_runtime_aux(RuntimeNode& r, const Lock&) { }
  virtual void change_working_memory_aux(ptrdiff_t working_memory_delta, const Lock&) { }
  virtual bool request_impl(const Runtime& r, size_t request, const Lock&) = 0;
public:
  virtual ~ControllerNode() = default;
  // whether you can request memory. request_impl can also call r->allow_more_memory() to give additional unrequested memory.
  // the name of the controller, for debugging and reporting purpose.
  virtual std::string name() = 0;
  bool request(const Runtime& r, size_t request, const Lock&);
  virtual void optimize(const Lock&) { }
  void add_runtime(const Runtime& r, const Lock&);
  void remove_runtime(RuntimeNode& r, const Lock&);
  std::vector<Runtime> runtimes(const Lock&);
  void set_max_memory(size_t max_memory_, const Lock& l) {
    this->max_memory_ = max_memory_;
    set_max_memory_aux(max_memory_, l);
  }
  void change_working_memory(ptrdiff_t working_memory_delta, const Lock& l) {
    working_memory_ += working_memory_delta;
    change_working_memory_aux(working_memory_delta, l);
  }
  size_t max_memory(const Lock&) {
    return max_memory_;
  }
  void free_max_memory(size_t memory_freed, const Lock& l) {
    used_memory_ -= memory_freed;
    free_max_memory_aux(memory_freed, l);
  }
  size_t used_memory(const Lock&) {
    return used_memory_;
  }
  Lock lock() {
    return std::make_shared<LockNode>(shared_from_this());
  }
  size_t working_memory(const Lock& l);
};

enum class RuntimeStatus {
  CanAllocate, Stay, ShouldFree
};

// The controller has two stage: the memory rich mode and the memory hungry mode.
// In the memory rich mode, all memory allocation is permitted, and the Controller does nothing.
// Only when we used up all memory (the applications is memory constrained) do we need to save memory.
// Once we enter the memory-hungry mode (by using up all physical memory) we stay there.
// Maybe we should add some way to get back to memory-rich mode?
struct BalanceControllerNode : ControllerNode {
  // a positive number.
  double tolerance = 0.5;
  static constexpr bool balance_allocation = false;
  HeuristicConfig hc;
  BalanceControllerNode(const HeuristicConfig& hc) : hc(hc) { }
  RuntimeStatus judge(double judged_score, double runtime_score, const Lock& l);
  // Score is sorted in ascending order.-
  // We are using median for now.
  // The other obvious choice is mean, and it may have a problem when data is imbalance:
  // only too few runtime will be freeing or allocating memory.
  double aggregate_score(const std::vector<double>& score);
  double score(const Lock& l);
  bool enough_memory(size_t extra) {
    return used_memory_ + extra <= max_memory_;
  }
  bool request_impl(const Runtime& r, size_t extra, const Lock& l) override;
  void optimize(const Lock& l) override;
  std::string name() override {
    return "BalanceController";
  }
};

// a first-come first-serve strategy.
// useful as a baseline in simulation.
struct FirstComeFirstServeControllerNode : ControllerNode {
  void optimize(const Lock& l) override { }
  bool request_impl(const Runtime& r, size_t request, const Lock& l) override;
  std::string name() {
    return "FirstComeFirstServeController";
  }
};

// allow everyone to allocate, then release all memory at once.
struct BingBangControllerNode : ControllerNode {
  void optimize(const Lock& l) override { }
  bool request_impl(const Runtime& r, size_t request, const Lock& l) override;
  std::string name() {
    return "BingBangController";
  }
};

static std::string requirement = "requirement";
// Give each runtime a fixed amount of memory.
// The runtime can either specify that amount itself,
// and the leftover memory will be splitted evenly between
// runtime that do not specify.
// if the specification cannot be reached, specified memory amount will be scaled down proportionally.
// if all runtime specify memory requirement, memory requirement will be scaled up proportionally.
// the leftover caused by integer being not divisible will go on a first-come-first serve basis.
// Note: you can use it as a proportional controller if you specify memory requirement for all runtime.
struct FixedControllerNode : ControllerNode {
  std::string name() override {
    return "FixedController";
  }
  void optimize(const Lock& l) override {
    
  }
  bool request_impl(const Runtime& r, size_t extra, const Lock& l) override {
    throw;
    return true;
  }
};
