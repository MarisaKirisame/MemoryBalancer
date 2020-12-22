#pragma once
#include <cstddef>
#include <memory>
#include <cassert>

double memory_score(size_t working_memory, size_t max_memory, double garbage_rate, size_t gc_time);

// In order to avoid cycle, Runtime has strong pointer to controller and Controller has weak pointer to runtime.
struct ControllerNode;
struct RuntimeNode : std::enable_shared_from_this<RuntimeNode> {
  friend ControllerNode;
protected:
  std::shared_ptr<ControllerNode> controller;
  bool done_ = false;
public:
  void done();
  bool is_done() {
    return done_;
  }
  virtual ~RuntimeNode() {
    done();
  }
  virtual size_t working_memory() = 0;
  virtual size_t current_memory() = 0;
  virtual size_t max_memory() = 0;
  virtual double garbage_rate() = 0;
  virtual size_t gc_time() = 0; // we assume each gc clear all garbage: for generational gc only full gc 'count'
  virtual void allow_more_memory(size_t extra) = 0;
  virtual void shrink_max_memory() = 0;
  double memory_score() {
    return ::memory_score(working_memory(), max_memory(), garbage_rate(), gc_time());
  }
};
using Runtime = std::shared_ptr<RuntimeNode>;

struct SimulatedRuntimeNode : RuntimeNode {
  size_t working_memory_;
  size_t working_memory() override {
    return working_memory_;
  }
  size_t current_memory_;
  size_t current_memory() override {
    return current_memory_;
  }
  size_t max_memory_ = 0;
  size_t max_memory() override {
    return max_memory_;
  }
  size_t garbage_rate_;
  double garbage_rate() override {
    return garbage_rate_;
  }
  size_t gc_time_;
  size_t work_;
  size_t gc_time() override {
    return gc_time_;
  }
  void allow_more_memory(size_t extra) override {
    max_memory_ += extra;
  }
  void shrink_max_memory() override {
    // need to do a gc to shrink memory.
    max_memory_ = std::min(working_memory_, max_memory_);
  }
  bool in_gc = false;
  size_t time_in_gc = 0;
  bool need_gc() {
    return current_memory_ + garbage_rate_ > max_memory_;
  }
  size_t needed_memory() {
    if (need_gc()) {
      return current_memory_ + garbage_rate_ - max_memory_;
    }
    return 0;
  }
  void mutator_tick() {
    --work_;
    current_memory_ += garbage_rate_;
    if (work_ == 0) {
      current_memory_ = 0;
      done();
    }
  }
  void tick();
  SimulatedRuntimeNode(size_t working_memory_, size_t garbage_rate_, size_t gc_time_, size_t work_) :
    working_memory_(working_memory_), current_memory_(working_memory_), garbage_rate_(garbage_rate_), gc_time_(gc_time_), work_(work_) {
    assert(work_ != 0);
  }
};
