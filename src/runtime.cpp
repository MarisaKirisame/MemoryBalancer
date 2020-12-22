#include "runtime.h"
#include "controller.h"
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
      controller->remove_runtime(shared_from_this());
    }
  }
}
