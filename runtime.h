#pragma once

double memory_score(size_t working_memory, size_t max_memory, double garbage_rate, size_t gc_time) {
  assert(garbage_rate != 0);
  assert(gc_time != 0);
  size_t extra_memory = max_memory - working_memory;
  double ret = extra_memory / garbage_rate * extra_memory / gc_time;
  return ret;
}

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
void RuntimeNode::done() {
  if (!done_) {
    done_ = true;
    if (controller) {
      controller->remove_runtime(shared_from_this());
    }
  }
}
using Runtime = std::shared_ptr<RuntimeNode>;
