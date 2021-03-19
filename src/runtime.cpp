#include "runtime.hpp"
#include "controller.hpp"

double memory_score(size_t working_memory, size_t max_memory, double garbage_rate, size_t gc_time) {
  if (garbage_rate == 0 || gc_time == 0) {
    return std::numeric_limits<double>::max();
  }
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
  check_invariant();
  if (!in_gc) {
    gc();
  }
  shrink_memory_pending = true;
  check_invariant();
}

void SimulatedRuntimeNode::tick() {
  check_invariant();
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
    auto nm = needed_memory();
    if (controller->request(shared_from_this(), nm, controller->lock())) {
      assert (! need_gc());
      mutator_tick();
    } else {
      gc();
      tick();
    }
  } else {
    mutator_tick();
  }
  check_invariant();
}
