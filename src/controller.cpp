#include "controller.hpp"
#include "runtime.hpp"
#include "util.hpp"
#include <vector>
#include <algorithm>

bool ControllerNode::request(const Runtime& r, size_t request, const Lock& l) {
  if (request_impl(r, request, l)) {
    used_memory_ += request;
    r->allow_more_memory(request);
    return true;
  } else {
    return false;
  }
}

void ControllerNode::remove_runtime(RuntimeNode& r, const Lock& l) {
  auto w = r.weak_from_this();
  assert(runtimes_.count(w) == 1);
  runtimes_.erase(w);
  free_max_memory(r.max_memory(), l);
  change_working_memory(-r.working_memory(), l);
  remove_runtime_aux(r, l);
}

void ControllerNode::add_runtime(const Runtime& r, const Lock& l) {
  assert(runtimes_.count(r) == 0);
  assert(!r->controller);
  r->controller = shared_from_this();
  runtimes_.insert(r);
  add_runtime_aux(r, l);
}

std::vector<Runtime> ControllerNode::runtimes(const Lock& l) {
  std::vector<Runtime> ret;
  for (const auto& r: runtimes_) {
    auto sp = r.lock();
    assert(sp);
    ret.push_back(sp);
  }
  return ret;
}

bool BalanceControllerNode::request_impl(const Runtime& r, size_t extra, const Lock& l) {
  auto try_allocate =
    [&]() {
      if (enough_memory(extra)) {
        return true;
      } else {
        optimize(l);
        // todo: look like this always return false. is it true?
        return enough_memory(extra);
      }
    };
  if (balance_allocation) {
    double current_score = score(l);
    RuntimeStatus status = judge(r->memory_score(hc), current_score, l);
    size_t working_memory_ = working_memory(l);
    if (status == RuntimeStatus::Stay) {
      return false;
    } else if (status == RuntimeStatus::ShouldFree) {
      r->shrink_max_memory();
      return false;
    } else {
      assert(status == RuntimeStatus::CanAllocate);
      return try_allocate();
    }
  }
  else {
    return try_allocate();
  }
}

bool FirstComeFirstServeControllerNode::request_impl(const Runtime& r, size_t request, const Lock& l) {
  return used_memory_ + request <= max_memory_;
}

void BalanceControllerNode::optimize(const Lock& l) {
  double current_score = score(l);
  for (const Runtime& runtime: runtimes(l)) {
    RuntimeStatus status = judge(runtime->memory_score(hc), current_score, l);
    if (status == RuntimeStatus::ShouldFree) {
      runtime->shrink_max_memory();
    }
  }
}

double BalanceControllerNode::aggregate_score(const std::vector<double>& score) {
  return median(score);
}

double BalanceControllerNode::score(const Lock& l) {
  std::vector<double> score;
  for (const Runtime& runtime: runtimes(l)) {
    score.push_back(runtime->memory_score(hc));
  }
  std::sort(score.begin(), score.end());
  if (score.empty()) {
    return 0; // score doesnt matter without runtime anymore.
  }
  return aggregate_score(score);
}

size_t ControllerNode::working_memory(const Lock& l) {
  return working_memory_;
}

RuntimeStatus BalanceControllerNode::judge(double judged_score, double runtime_score, const Lock& l) {
  assert(0 <= runtime_score);
  size_t working_memory_ = working_memory(l);
  double portion_memory_used = double(used_memory_ - working_memory_) / double(max_memory_ - working_memory_);
  if (portion_memory_used * judged_score <= runtime_score) {
    return RuntimeStatus::CanAllocate;
  } else if (runtime_score * (1 + tolerance) <= portion_memory_used * judged_score) {
    return RuntimeStatus::ShouldFree;
  } else {
    return RuntimeStatus::Stay;
  }
}

bool BingBangControllerNode::request_impl(const Runtime& r, size_t request, const Lock& l) {
  if (used_memory_ + request <= max_memory_) {
    return true;
  } else {
    for (const Runtime& runtime: runtimes(l)) {
      runtime->shrink_max_memory();
    }
    return false;
  }
}
