#include "runtime.hpp"
#include "controller.hpp"

double memory_score(size_t working_memory, size_t max_memory, double garbage_rate, size_t gc_time) {
  assert(garbage_rate != 0);
  assert(gc_time != 0);
  size_t extra_memory = max_memory - working_memory;
  double ret = extra_memory / garbage_rate * extra_memory / gc_time;
  return ret;
}

void RuntimeNode::done() {
  if (!done_) {
    done_ = true;
    if (controller) {
      controller->remove_runtime(shared_from_this(), controller->lock());
    }
    done_aux();
  }
}

void SimulatedRuntimeNode::shrink_max_memory() {
  if (!in_gc) {
    gc();
  }
  shrink_memory_pending = true;
}

void SimulatedRuntimeNode::tick() {
  assert(current_memory_ <= max_memory_);
  assert(!done_);
  if (in_gc) {
    ++time_in_gc;
    if (time_in_gc == gc_duration()) {
      in_gc = false;
      current_memory_ = std::min(current_memory_, max_working_memory_);
      if (shrink_memory_pending) {
        shrink_memory_pending = false;
        size_t old_max_memory = max_memory_;
        max_memory_ = current_memory_;
        controller->free_max_memory(old_max_memory - max_memory_, controller->lock());
      }
    }
  } else if (need_gc()) {
    if (controller->request(shared_from_this(), needed_memory(), controller->lock())) {
      assert (! need_gc());
      mutator_tick();
    } else {
      gc();
      tick();
    }
  } else {
    mutator_tick();
  }
}
