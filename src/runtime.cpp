#include "runtime.hpp"
#include "controller.hpp"

double memory_score(size_t working_memory, size_t max_memory, double garbage_rate, size_t gc_time, size_t work_left, const HeuristicConfig& hc) {
  if (garbage_rate <= 0 || gc_time == 0) {
    return std::numeric_limits<double>::max();
  }
  size_t extra_memory = max_memory - working_memory;
  double ret;
  if (hc.opt == OptimizeFor::throughput) {
    double gc_tick_per_tick = garbage_rate * gc_time;
    double tmp = extra_memory + gc_tick_per_tick;
    std::cout << extra_memory << ", " << gc_tick_per_tick << std::endl;
    ret = (tmp * tmp) / gc_tick_per_tick;
  } else {
    assert(hc.opt == OptimizeFor::time);
    ret = extra_memory * extra_memory / (garbage_rate * gc_time);
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

size_t SimulatedRuntimeNode::needed_memory() {
  if (need_gc()) {
    auto gr = garbage_rate();
    assert(gr > 0);
    return current_memory_ + gr - max_memory_;
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
  check_invariant();
}

void SimulatedRuntimeNode::mutator_tick() {
  check_invariant();
  std::cout << working_memory() << "," << garbage_rate() << std::endl;
  controller->change_working_memory(-working_memory(), lock());
  current_memory_ = std::max(static_cast<ptrdiff_t>(0),
                             static_cast<ptrdiff_t>(current_memory_) + static_cast<ptrdiff_t>(garbage_rate()));
  ++mutator_time;
  controller->change_working_memory(working_memory(), lock());
  std::cout << working_memory() << "," << garbage_rate() << std::endl;
  check_invariant();
}
