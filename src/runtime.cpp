#include "runtime.hpp"
#include "controller.hpp"

double memory_score(size_t working_memory, size_t max_memory, double garbage_rate, size_t gc_time, size_t work_left, const HeuristicConfig& hc) {
  if (garbage_rate <= 0 || gc_time == 0) {
    return std::numeric_limits<double>::max();
  }
  size_t extra_memory = max_memory - working_memory;
  double gc_tick_per_tick = garbage_rate * gc_time;
  //std::cout << extra_memory << ", " << gc_tick_per_tick << std::endl;
  double ret;
  if (hc.opt == OptimizeFor::throughput) {
    double tmp = extra_memory + gc_tick_per_tick;
    ret = (tmp * tmp) / gc_tick_per_tick;
  } else {
    assert(hc.opt == OptimizeFor::time);
    ret = extra_memory * extra_memory / gc_tick_per_tick;
  }
  if (hc.weight_work_left) {
    ret *= work_left;
  }
  return ret;
}

void RuntimeNode::done() {
  if (!done_) {
    done_ = true;
    if (controller) {
      controller->remove_runtime(*this, lock());
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

ptrdiff_t SimulatedRuntimeNode::current_memory_delta() {
  return ptrdiff_t(next_current_memory()) - ptrdiff_t(current_memory());
}

size_t SimulatedRuntimeNode::needed_memory() {
  if (need_gc()) {
    auto delta = current_memory_delta();
    assert(delta > 0);
    return delta;
  }
  return 0;
}

void SimulatedRuntimeNode::tick() {
  assert(controller);
  check_invariant();
  assert(!done_);
  if (mutator_time == work_amount) {
    done();
  } else if (in_gc) {
    auto gcd = gc_duration();
    assert(gcd > 0);
    if (time_in_gc == gcd) {
      in_gc = false;
      current_memory_ = working_memory();
      if (shrink_memory_pending) {
        shrink_memory_pending = false;
        size_t old_max_memory = max_memory_;
        max_memory_ = current_memory_;
        controller->free_max_memory(old_max_memory - max_memory_, lock());
      }
      tick();
    } else {
      ++time_in_gc;
    }
  } else if (need_gc()) {
    auto nm = needed_memory();
    if (controller->request(shared_from_this(), nm, lock())) {
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

void SimulatedRuntimeNode::mutator_tick() {
  check_invariant();
  controller->change_working_memory(-working_memory(), lock());
  current_memory_ = next_current_memory();
  ++mutator_time;
  controller->change_working_memory(working_memory(), lock());
  check_invariant();
}

// todo: move lock here
// todo: skip minor gc?
void RemoteRuntimeNode::update(const v8::GCRecord& rec) {
  if (rec.is_major_gc) {
    if (has_one_record_) {
      garbage_rate = static_cast<double>(rec.before_memory - working_memory) / static_cast<double>(rec.before_time - last_gc_time);
      ready_ = true;
    } else {
      has_one_record_ = true;
    }
    working_memory = rec.after_memory;
    last_gc_time = rec.after_time;
    max_memory = rec.max_memory;
    gc_duration = rec.after_time - rec.before_time;
  }
}

double RemoteRuntimeNode::memory_score() {
  assert(gc_duration > 0);
  assert(garbage_rate >= 0);
  double extra_memory = static_cast<double>(max_memory - working_memory);
  return extra_memory * extra_memory / (gc_duration * garbage_rate);
}
