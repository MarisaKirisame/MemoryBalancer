#pragma once
#include <memory>
#include <set>
#include <assert.h>
#include <vector>
#include <iostream>

struct RuntimeNode;
using Runtime = std::shared_ptr<RuntimeNode>;
struct ControllerNode : std::enable_shared_from_this<ControllerNode> {
protected:
  // this look like weak_ptr, but the content should always be here:
  // whenever a runtimenode gone out of life it will notify the controller, and get it removed.5
  std::set<std::weak_ptr<RuntimeNode>, std::owner_less<std::weak_ptr<RuntimeNode>>> runtimes_;
  size_t max_memory_ = 0;
  size_t used_memory_ = 0;
public:
  virtual ~ControllerNode() = default;
  bool request(const Runtime& r, size_t request);
  // whether you can request memory. request_impl can also call r->allow_more_memory() to give additional unrequested memory.
  virtual bool request_impl(const Runtime& r, size_t request) = 0;
  virtual void optimize() { }
  // the name of the controller, for debugging and reporting purpose.
  virtual std::string name() = 0;
  void add_runtime(const Runtime& r);
  void remove_runtime(const Runtime& r);
  std::vector<Runtime> runtimes();
  void set_max_memory(size_t max_memory_) {
    this->max_memory_ = max_memory_;
    set_max_memory_aux(max_memory_);
  }
  size_t max_memory() {
    return max_memory_;
  }
  void free_max_memory(size_t memory_freed) {
    used_memory_ -= memory_freed;
    free_max_memory_aux(memory_freed);
  }
  virtual void free_max_memory_aux(size_t memory_freed) { }
  virtual void set_max_memory_aux(size_t max_memory_) { }
  virtual void add_runtime_aux(const Runtime& r) { }
  virtual void remove_runtime_aux(const Runtime& r) { }
};
using Controller = std::shared_ptr<ControllerNode>;

enum class RuntimeStatus {
  CanAllocate, Stay, ShouldFree
};

// The controller has two stage: the memory rich mode and the memory hungry mode.
// In the memory rich mode, all memory allocation is permitted, and the Controller does nothing.
// Only when we used up all memory (the applications is memory constrained) do we need to save memory.
// Once we enter the memory-hungry mode (by using up all physical memory) we stay there.
// Maybe we should add some way to get back to memory-rich mode?
struct BalanceControllerNode : ControllerNode {
  // a positive number. allow deviation of this much in balancing.
  double tolerance = 0.2;
  // a number between [0, 1]. only when that proportion of memory is used, go into pressure mode, and restrict allocation
  double pressure_threshold = 0.9;
  RuntimeStatus judge(double current_balance, double runtime_balance) {
    if (current_balance * (1 + tolerance) < runtime_balance) {
      return RuntimeStatus::ShouldFree;
    } else if (runtime_balance * (1 + tolerance) < current_balance) {
      return RuntimeStatus::CanAllocate;
    } else {
      return RuntimeStatus::Stay;
    }
  }
  // Score is sorted in ascending order.
  // We are using median for now.
  // The other obvious choice is mean, and it may have a problem when data is imbalance:
  // only too few runtime will be freeing or allocating memory.
  double aggregate_score(const std::vector<double>& score);
  double score();
  bool enough_memory(size_t extra) {
    return used_memory_ + extra <= max_memory_;
  }
  bool request_balance(const Runtime& r, size_t extra);
  bool request_impl(const Runtime& r, size_t extra) override {
    if (used_memory_ < pressure_threshold * max_memory_) {
      if (enough_memory(extra)) {
        return true;
      } else {
        return request_balance(r, extra);
      }
    } else {
      return request_balance(r, extra);
    }
  }
  void optimize() override;
  std::string name() override {
    return "BalanceController";
  }
};

// a first-come first-serve strategy.
// useful as a baseline in simulation.
struct FirstComeFirstServeControllerNode : ControllerNode {
  void optimize() override { }
  bool request_impl(const Runtime& r, size_t request) override;
  std::string name() {
    return "FirstComeFirstServeController";
  }
};

// Give each runtime a fixed amount of memory.
// The runtime can either specify that amount itself,
// and the leftover memory will be splitted evenly between
// runtime that do not specify.
// if the specification cannot be reached, specified memory amount will be scaled down proportionally.
// if all runtime specify memory requirement, memory requirement will be scaled up proportionally.
// the leftover caused by integer being not divisible will go on a first-come-first serve basis.
struct FixedControllerNode : ControllerNode {
  std::string name() override {
    return "FixedController";
  }
  void optimize() override {
    
  }
  bool request_impl(const Runtime& r, size_t extra) override {
    
  }
};
