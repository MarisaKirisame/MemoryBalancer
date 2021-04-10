#pragma once
#include <cstddef>
#include <memory>
#include <cassert>
#include <map>
#include <any>
#include <functional>

#include "controller.hpp"

// higher score mean need less memory
double memory_score(size_t working_memory, size_t max_memory, double garbage_rate, size_t gc_duration);

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
  virtual size_t working_memory() const = 0;
  virtual size_t current_memory() const = 0;
  virtual size_t max_memory() const = 0;
  virtual double garbage_rate() const = 0;
  virtual size_t gc_duration() const = 0; // we assume each gc clear all garbage: for generational gc only full gc 'count'
  virtual void allow_more_memory(size_t extra) = 0;
  virtual void shrink_max_memory() = 0;
  double memory_score() {
    auto ret = ::memory_score(working_memory(), max_memory(), garbage_rate(), gc_duration());
    assert(!std::isinf(ret));
    return ret;
  }
};

struct SimulatedRuntimeNode : RuntimeNode {
  ~SimulatedRuntimeNode() {
    done();
  }
  using mutator_clock = size_t;
  mutator_clock mutator_time = 0, work_amount;
  // note: the current logged simulated runtime report working memory in interval, while the simulator may run in finer grain mode.
  // this mean that the simulated runime will have working memory 'jump', and it is possible that a jump get working memory > current memory.
  // to combat this we take the min of input working memory and current memory as the working memory.
  // there will also be warning whenever this happend.
  void tick();
  std::function<size_t(mutator_clock)> max_working_memory_;
  size_t working_memory() const override {
    auto m = max_working_memory_(mutator_time);
    //assert(m >= current_memory_);
    return std::min(current_memory_, m);
  }
  void check_invariant() {
    assert(current_memory_ <= max_memory_);
  }
  size_t current_memory_ = 0;
  size_t current_memory() const override {
    return current_memory_;
  }
  void set_current_memory(size_t val) {
    current_memory_ = val;
    check_invariant();
  }
  size_t max_memory_ = 0;
  size_t max_memory() const override {
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
  double garbage_rate() const override {
    return garbage_rate_(mutator_time);
  }
  size_t gc_duration() const override {
    return gc_duration_(mutator_time);
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
    auto gr = garbage_rate();
    return gr > 0 && current_memory_ + gr > max_memory_;
  }
  size_t needed_memory();
  void gc() {
    in_gc = true;
    time_in_gc = 0;
  }
  void mutator_tick() {
    check_invariant();
    current_memory_ = std::max(static_cast<ptrdiff_t>(0),
                               static_cast<ptrdiff_t>(current_memory_) + static_cast<ptrdiff_t>(garbage_rate()));
    assert(mutator_time != work_amount);
    ++mutator_time;
    check_invariant();
  }

  SimulatedRuntimeNode(mutator_clock work_amount,
                       const std::function<size_t(mutator_clock)> &max_working_memory_,
                       const std::function<ptrdiff_t(mutator_clock)> &garbage_rate_,
                       const std::function<size_t(mutator_clock)> &gc_duration_) :
    work_amount(work_amount),
    max_working_memory_(max_working_memory_),
    garbage_rate_(garbage_rate_),
    gc_duration_(gc_duration_) { }
};
