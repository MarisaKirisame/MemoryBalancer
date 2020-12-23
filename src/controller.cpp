#include "controller.hpp"
#include "runtime.hpp"
#include "util.hpp"
#include <vector>
#include <algorithm>

bool ControllerNode::request(const Runtime& r, size_t request) {
  if (request_impl(r, request)) {
    used_memory_ += request;
    r->allow_more_memory(request);
    return true;
  } else {
    return false;
  }
}

void ControllerNode::remove_runtime(const Runtime& r) {
  assert(runtimes_.count(r) == 1);
  runtimes_.erase(r);
  remove_runtime_aux(r);
}

void ControllerNode::add_runtime(const Runtime& r) {
  assert(runtimes_.count(r) == 0);
  assert(!r->controller);
  r->controller = shared_from_this();
  runtimes_.insert(r);
  add_runtime_aux(r);
}

std::vector<Runtime> ControllerNode::runtimes() {
  std::vector<Runtime> ret;
  for (const auto& r: runtimes_) {
    auto sp = r.lock();
    assert(sp);
    ret.push_back(sp);
  }
  return ret;
}

bool BalanceControllerNode::request_balance(const Runtime& r, size_t extra) {
  double current_score = score();
  RuntimeStatus status = judge(current_score, r->memory_score());
  if (status == RuntimeStatus::Stay) {
    return false;
  } else if (status == RuntimeStatus::ShouldFree) {
    std::cout << "shrinking" << std::endl;
    r->shrink_max_memory();
    return false;
  } else {
    assert(status == RuntimeStatus::CanAllocate);
    if (enough_memory(extra)) {
      return true;
    } else {
      optimize();
      return enough_memory(extra);
    }
  }
}

bool FirstComeFirstServeControllerNode::request_impl(const Runtime& r, size_t extra) {
  return used_memory_ + extra <= max_memory_;
}

void BalanceControllerNode::optimize() {
  std::cout << "optimizing" << std::endl;
  double current_score = score();
  for (const Runtime& runtime: runtimes()) {
    RuntimeStatus status = judge(current_score, runtime->memory_score());
    if (status == RuntimeStatus::ShouldFree) {
      std::cout << "memory shrinked" << std::endl;
      runtime->shrink_max_memory();
    }
  }
}

double BalanceControllerNode::aggregate_score(const std::vector<double>& score) {
  return median(score);
}

double BalanceControllerNode::score() {
  std::vector<double> score;
  for (const Runtime& runtime: runtimes()) {
    score.push_back(runtime->memory_score());
  }
  std::sort(score.begin(), score.end());
  if (score.empty()) {
    return 0; // score doesnt matter without runtime anymore.
  }
  return aggregate_score(score);
}
