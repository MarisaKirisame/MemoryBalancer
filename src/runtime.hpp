#pragma once
#include <atomic>
#include <cstddef>
#include <memory>
#include <cassert>
#include <map>
#include <any>
#include <functional>
#include <v8.h>

#include "controller.hpp"

// higher score mean need less memory
double memory_score(size_t working_memory, size_t max_memory, double garbage_rate, size_t gc_duration, size_t work_left, const HeuristicConfig& hc);

struct RemoteRuntimeNode {
  int sockfd;
  std::mutex m; // there will be concurrent write to remoteruntimenode.
  RemoteRuntimeNode(int sockfd) : sockfd(sockfd) { }
  void update(const v8::GCRecord& rec);
  size_t working_memory;
  size_t max_memory;
  double garbage_rate;
  size_t gc_duration;
  bool ready = false;
};

// In order to avoid cycle, Runtime has strong pointer to controller and Controller has weak pointer to runtime.
struct RuntimeNode : std::enable_shared_from_this<RuntimeNode> {
  friend ControllerNode;
  std::map<std::string, std::any> metadata;
protected:
  Controller controller;
  bool done_ = false;
  ControllerNode::Lock lock() {
    assert(controller);
    return controller->lock();
  }
public:
  void done();
  virtual void done_aux() { }
  bool is_done() {
    return done_;
  }
  virtual ~RuntimeNode() {
    assert(is_done());
  }
  virtual size_t working_memory() = 0;
  virtual size_t current_memory() = 0;
  virtual size_t max_memory() = 0;
  virtual double garbage_rate() = 0;
  virtual size_t gc_duration() = 0;
  virtual size_t work_left() = 0;
  virtual void allow_more_memory(size_t extra) = 0;
  virtual void shrink_max_memory() = 0;

  double memory_score(const HeuristicConfig& hc) {
    auto ret = ::memory_score(working_memory(), max_memory(), garbage_rate(), gc_duration(), work_left(), hc);
    assert(!std::isinf(ret));
    return ret;
  }
};

// Note: we will increase allocation to make current_memory > working_memory.
// there should be two place where we need this hotfix.
// 0: at the beginning of the code, the current_memory is 0 while working_memory is not. lets do a bump.
// 1: the code do rounding and interpolation. we may have to bump by 1 sometimes to avoid rounding error.
struct SimulatedRuntimeNode : RuntimeNode {
  using mutator_clock = size_t;
  mutator_clock mutator_time = 0, work_amount;
  // note: the current logged simulated runtime report working memory in interval, while the simulator may run in finer grain mode.
  // this mean that the simulated runime will have working memory 'jump', and it is possible that a jump get working memory > current memory.
  // to combat this we take the min of input working memory and current memory as the working memory.
  // there will also be warning whenever this happend.
  void tick();
  std::function<size_t(mutator_clock)> working_memory_;
  size_t working_memory() override {
    auto wm = working_memory_(mutator_time);
    return std::min(current_memory_, wm);
  }
  void check_invariant() {
    assert(current_memory_ <= max_memory_);
    if (mutator_time > 0) {
      assert(working_memory_(mutator_time) <= current_memory_);
    }
  }
  size_t current_memory_ = 0;
  size_t current_memory() override {
    return current_memory_;
  }
  size_t next_current_memory() {
    return std::max<ptrdiff_t>(working_memory_(mutator_time+1), ptrdiff_t(current_memory_) + garbage_rate_(mutator_time));
  }
  ptrdiff_t current_memory_delta();
  void set_current_memory(size_t val) {
    current_memory_ = val;
    check_invariant();
  }
  size_t max_memory_ = 0;
  size_t max_memory() override {
    return max_memory_;
  }
  void set_max_memory(size_t val) {
    max_memory_ = val;
    check_invariant();
  }
  void done_aux() {
    current_memory_ = 0;
    max_memory_ = 0;
  }
  std::function<ptrdiff_t(mutator_clock)> garbage_rate_;
  std::function<size_t(mutator_clock)> gc_duration_;
  double garbage_rate() override {
    return garbage_rate_(mutator_time);
  }
  size_t gc_duration() override {
    return gc_duration_(mutator_time);
  }
  size_t work_left() override {
    return work_amount - mutator_time;
  }
  void allow_more_memory(size_t extra) override {
    max_memory_ += extra;
    check_invariant();
  }
  void shrink_max_memory() override;
  bool in_gc = false;
  bool shrink_memory_pending = false;
  size_t time_in_gc = 0;
  bool need_gc() {
    assert(current_memory() <= max_memory_);
    if (next_current_memory() > max_memory_) {
      assert(next_current_memory() > current_memory());
      assert(current_memory_delta() > 0);
      return true;
    } else {
      return false;
    }
  }
  size_t needed_memory();
  void gc() {
    in_gc = true;
    time_in_gc = 0;
  }
  void mutator_tick();

  SimulatedRuntimeNode(mutator_clock work_amount,
                       const std::function<size_t(mutator_clock)> &working_memory_,
                       const std::function<ptrdiff_t(mutator_clock)> &garbage_rate_,
                       const std::function<size_t(mutator_clock)> &gc_duration_) :
    work_amount(work_amount),
    working_memory_(working_memory_),
    garbage_rate_(garbage_rate_),
    gc_duration_(gc_duration_) { }
  ~SimulatedRuntimeNode() {
    done();
  }
};
