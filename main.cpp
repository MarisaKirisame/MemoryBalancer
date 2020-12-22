// Copyright 2015 the V8 project authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <iostream>
#include <boost/accumulators/accumulators.hpp>
#include <boost/accumulators/statistics/stats.hpp>
#include <boost/accumulators/statistics/mean.hpp>
#include <boost/accumulators/statistics/variance.hpp>
#include <boost/math/statistics/anderson_darling.hpp>
#include <nlohmann/json.hpp>
#include <libplatform/libplatform.h>
#include <v8.h>
#include <chrono>
#include <random>
#include <future>
#include <thread>
#include <set>
#include "util.h"
#include "controller.h"
#include "runtime.h"

using namespace nlohmann;
using time_point = std::chrono::steady_clock::time_point;
using std::chrono::steady_clock;
using std::chrono::duration_cast;
using milliseconds = std::chrono::milliseconds;

struct Input {
  size_t heap_size;
  std::string code_path;
};

// I'd love to use the name from_json and to_json, but unfortunately it seems like the two name is used.
Input read_from_json(const json& j) {
  assert(j.count("heap_size") == 1);
  assert(j.count("code_path") == 1);
  size_t heap_size = j.value("heap_size", 0);
  std::string code_path = j.value("code_path", "");
  return Input {heap_size, code_path};
}

struct Output {
  std::string version;
  size_t time_taken;
};

void add_to_json(const Output& o, json& j) {
  j["version"] = o.version;
  j["time_taken"] = o.time_taken;
}

Output run(const Input& i, std::mutex* m) {
  std::cout << "running " << i.code_path << std::endl;
  Output o;
  // Create a new Isolate and make it the current one.
  v8::Isolate::CreateParams create_params;
  //create_params.constraints.ConfigureDefaults(heap_size, 0);
  create_params.constraints.ConfigureDefaultsFromHeapSize(i.heap_size, i.heap_size);
  size_t old = create_params.constraints.max_old_generation_size_in_bytes();
  size_t young = create_params.constraints.max_young_generation_size_in_bytes();
  //std::cout << old << " " << young << " " << old + young << std::endl;
  create_params.array_buffer_allocator =
      v8::ArrayBuffer::Allocator::NewDefaultAllocator();
  v8::Isolate* isolate = v8::Isolate::New(create_params);
  isolate->SetMaxPhysicalMemoryOfDevice(0.9e9);
  {
    v8::Isolate::Scope isolate_scope(isolate);
    // Create a stack-allocated handle scope.
    v8::HandleScope handle_scope(isolate);
    // Create a new context.
    v8::Local<v8::Context> context = v8::Context::New(isolate);
    // Enter the context for compiling and running the hello world script.
    v8::Context::Scope context_scope(context);

    {
      // Create a string containing the JavaScript source code.
      v8::Local<v8::String> source = fromFile(isolate, i.code_path);

      // Compile the source code.
      v8::Local<v8::Script> script =
          v8::Script::Compile(context, source).ToLocalChecked();

      m->lock();
      m->unlock(); // abusing mutex as signal - once the mutex is unlocked everyone get access.
      time_point begin = steady_clock::now();
      v8::Local<v8::Value> result;
      result = script->Run(context).ToLocalChecked();
      time_point end = steady_clock::now();
      o.time_taken = duration_cast<milliseconds>(end - begin).count();
      // Convert the result to an UTF8 string and print it.
      v8::String::Utf8Value utf8(isolate, result);
      printf("%s\n", *utf8);
    }
    v8::GCHistory history = isolate->GetGCHistory();
    for (const v8::GCRecord& r: history.records) {
      if (false && r.is_major_gc) {
        std::cout << "gc decrease memory by: " << long(r.before_memory) - long(r.after_memory) <<
          " in: " << r.after_time - r.before_time <<
          " rate: " << (long(r.before_memory) - long(r.after_memory)) / (r.after_time - r.before_time) <<
          " (is " << (r.is_major_gc ? std::string("major ") : std::string("minor ")) << "GC)" << std::endl;
      }
    }
    long total_garbage_collected = 0;
    long total_time_taken = 0;
    std::vector<double> garbage_collected, time_taken;
    for (const v8::GCRecord& r: history.records) {
      if (r.is_major_gc) {
        total_garbage_collected += long(r.before_memory) - long(r.after_memory);
        garbage_collected.push_back(long(r.before_memory) - long(r.after_memory));
        total_time_taken += r.after_time - r.before_time;
        time_taken.push_back(r.after_time - r.before_time);
      }
    }
    std::sort(garbage_collected.begin(), garbage_collected.end());
    std::sort(time_taken.begin(), time_taken.end());
    //std::cout << "total garbage collected: " << total_garbage_collected << std::endl;
    //double mean_garbage_collected = mean(garbage_collected);
    //double sd_garbage_collected = sd(garbage_collected);
    //double normality_garbage_collected = normality(garbage_collected);
    //std::cout << "mean, sd, normality of garbage collected: " << mean_garbage_collected << ", " << sd_garbage_collected << ", " << normality_garbage_collected << std::endl;
    //std::cout << "total time taken: " << total_time_taken << std::endl;
    //double mean_time_taken = mean(time_taken);
    //double sd_time_taken = sd(time_taken);
    //double normality_time_taken = normality(time_taken);
    //std::cout << "mean, sd, normality of time taken: " << mean_time_taken << ", " << sd_time_taken << ", " << normality_time_taken << std::endl;
    //std::cout << "garbage collection rate: " << double(total_garbage_collected) / double(total_time_taken) << std::endl;
  }
  isolate->Dispose();
  delete create_params.array_buffer_allocator;
  o.version = "2020-11-20";
  return o;
}

void log_json(const json& j) {
  std::ofstream f("logs/" + get_time());
  f << j;
}

void read_write() {
  std::mutex m;
  m.lock();

  std::ifstream t("balancer-config");
  json j;
  t >> j;

  Input i = read_from_json(j);
  std::future<Output> o = std::async(std::launch::async, run, i, &m);

  m.unlock();
  add_to_json(o.get(), j);

  log_json(j);
}

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
enum class RuntimeStatus {
  CanAllocate, Stay, ShouldFree
};

double median(const std::vector<double>& vec) {
  assert(vec.size() > 0);
  return (vec[(vec.size() - 1) / 2] + vec[vec.size() / 2]) / 2;
}
// The controller has two stage: the memory rich mode and the memory hungry mode.
// In the memory rich mode, all memory allocation is permitted, and the Controller does nothing.
// Only when we used up all memory (the applications is memory constrained) do we need to save memory.
// Once we enter the memory-hungry mode (by using up all physical memory) we stay there.
// Maybe we should add some way to get back to memory-rich mode?
struct BalanceControllerNode : ControllerNode {
  size_t used_memory = 0;
  // a positive number. allow deviation of this much in balancing.
  double tolerance = 0.2;
  // a number between [0, 1]. only when that proportion of memory is used, go into pressure mode, and restrict allocation
  double pressure_threshold = 0.9;
  RuntimeStatus judge(double current_balance, double runtime_balance) {
    std::cout << "current_balance: " << current_balance << " runtime_balance: " << runtime_balance << std::endl;
    if (current_balance * (1 + tolerance) < runtime_balance) {
      return RuntimeStatus::ShouldFree;
    } else if (runtime_balance * (1 + tolerance) < current_balance) {
      return RuntimeStatus::CanAllocate;
    } else {
      return RuntimeStatus::Stay;
    }
  }
  // Score is sorted in ascending order.
  // We are using median for now.
  // The other obvious choice is mean, and it may have a problem when data is imbalance:
  // only too few runtime will be freeing or allocating memory.
  double aggregate_score(const std::vector<double>& score) {
    return median(score);
  }
  double score() {
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
  void allow_request(const Runtime& r, size_t extra) {
    used_memory += extra;
    r->allow_more_memory(extra);
  }
  bool process_request(const Runtime& r, size_t extra) {
    if (max_memory_ - used_memory >= extra) {
      allow_request(r, extra);
      return true;
    } else {
      return false;
    }
  }
  bool request_balance(const Runtime& r, size_t extra) {
    double current_score = score();
    RuntimeStatus status = judge(current_score, r->memory_score());
    if (status == RuntimeStatus::Stay) {
      return false;
    } else if (status == RuntimeStatus::ShouldFree) {
      std::cout << "shrinking" << std::endl;
      used_memory -= r->max_memory();
      r->shrink_max_memory();
      used_memory += r->max_memory();
      return false;
    } else {
      assert(status == RuntimeStatus::CanAllocate);
      if (process_request(r, extra)) {
        return true;
      } else {
        optimize();
        if (process_request(r, extra)) {
          return true;
        } else {
          return false;
        }
      }
    }
  }
  bool request(const Runtime& r, size_t extra) override {
    if (used_memory < pressure_threshold * max_memory_) {
      if (process_request(r, extra)) {
        return true;
      } else {
        return request_balance(r, extra);
      }
    } else {
      return request_balance(r, extra);
    }
  }
  void optimize() override {
    std::cout << "optimizing" << std::endl;
    double current_score = score();
    for (const Runtime& runtime: runtimes()) {
      RuntimeStatus status = judge(current_score, runtime->memory_score());
      if (status == RuntimeStatus::ShouldFree) {
        std::cout << "memory shrinked" << std::endl;
        used_memory -= runtime->max_memory();
        runtime->shrink_max_memory();
        used_memory += runtime->max_memory();
      }
    }
  }
  std::string name() override {
    return "BalanceController";
  }
};

// a first-come first-serve strategy.
// useful as a baseline in simulation.
struct FirstComeFirstServeControllerNode : ControllerNode {
  size_t used_memory = 0;
  void optimize() override { }
  bool request(const Runtime& r, size_t extra) override {
    if (used_memory + extra <= max_memory_) {
      r->allow_more_memory(extra);
     used_memory += extra;
      return true;
    } else {
      return false;
    }
  }
  std::string name() {
    return "FirstComeFirstServeController";
  }
};

void SimulatedRuntimeNode::tick() {
  assert (!done_);
  if (in_gc) {
    std::cout << "doing gc" << std::endl;
    ++time_in_gc;
    if (time_in_gc == gc_time_) {
      in_gc = false;
      current_memory_ = working_memory_;
    }
  } else if (need_gc()) {
    if (controller->request(shared_from_this(), needed_memory())) {
      assert (! need_gc());
      mutator_tick();
    } else {
      in_gc = true;
      time_in_gc = 0;
      tick();
    }
  } else {
    mutator_tick();
  }
}

void parallel_experiment() {
  std::mutex m;
  m.lock();

  Input splay_input;
  splay_input.heap_size = 0;//300*1e6;
  splay_input.code_path = "splay.js";

  Input pdfjs_input;
  pdfjs_input.heap_size = 0;//700*1e6;
  pdfjs_input.code_path = "pdfjs.js";

  std::vector<Input> inputs;
  for (int i = 0; i < 2; ++i) {
    inputs.push_back(splay_input);
    inputs.push_back(pdfjs_input);
  }

  std::vector<std::future<Output>> futures;
  for (const Input& input : inputs) {
    futures.push_back(std::async(std::launch::async, run, input, &m));
  }

  m.unlock();

  size_t total_time = 0;
  for (std::future<Output>& future : futures) {
    total_time += future.get().time_taken;
  }

  std::cout << "total_time = " << total_time << std::endl;
}

// todo: noise (have number fluctuate)
// todo: regime change (a program is a sequence of program)
// see how close stuff get to optimal split
void run_simulated_experiment(const Controller& c) {
  c->set_max_memory(6);
  std::vector<std::shared_ptr<SimulatedRuntimeNode>> runtimes;
  runtimes.push_back(std::make_shared<SimulatedRuntimeNode>(/*working_memory_=*/0, /*garbage_rate_=*/1, /*gc_time_=*/5, /*work_=*/20));
  runtimes.push_back(std::make_shared<SimulatedRuntimeNode>(/*working_memory_=*/0, /*garbage_rate_=*/1, /*gc_time_=*/2, /*work_=*/20));
  for (const auto& r: runtimes) {
    c->add_runtime(r);
  }
  size_t i = 0;
  for (bool has_work=true; has_work; ++i) {
    has_work=false;
    for (const auto&r : runtimes) {
      std::cout << r->current_memory_ << std::endl;
    }
    for (const auto&r : runtimes) {
      if (!r->is_done()) {
        r->tick();
        has_work=true;
      }
    }
    sleep(1);
  }
  std::cout << "total time taken: " << i << std::endl;
}

// Give each runtime a fixed amount of memory.
// The runtime can either specify that amount itself,
// and the leftover memory will be splitted evenly between
// runtime that do not specify.
// if the specification cannot be reached, specified memory amount will be scaled down proportionally.
// if all runtime specify memory requirement, memory requirement will be scaled up proportionally.
// the leftover caused by integer being not divisible will go on a first-come-first serve basis.
struct FixedControllerNode : ControllerNode {
  std::string name() override {
    return "FixedController";
  }
  void optimize() override {
    
  }
  bool request(const Runtime& r, size_t extra) override {
    
  }
};

void simulated_experiment() {
  //run_simulated_experiment(std::make_shared<BalanceControllerNode>());
  run_simulated_experiment(std::make_shared<FirstComeFirstServeControllerNode>());
  //run_simulated_experiment(std::make_shared<FixedControllerNode>());
}

struct RestrictedPlatform : v8::Platform {
  RestrictedPlatform(std::unique_ptr<v8::Platform> &&platform_) : platform_(std::move(platform_)) { }
  std::unique_ptr<v8::Platform> platform_;
  v8::PageAllocator* GetPageAllocator() override {
    return platform_->GetPageAllocator();
  }

  void OnCriticalMemoryPressure() override {
    return platform_->OnCriticalMemoryPressure();
  }

  bool OnCriticalMemoryPressure(size_t length) override {
    return platform_->OnCriticalMemoryPressure(length);
  }

  int NumberOfWorkerThreads() override {
    return platform_->NumberOfWorkerThreads();
  }

  std::shared_ptr<v8::TaskRunner> GetForegroundTaskRunner(v8::Isolate* isolate) override {
    return platform_->GetForegroundTaskRunner(isolate);
  }

  void CallOnWorkerThread(std::unique_ptr<v8::Task> task) override {
    return platform_->CallOnWorkerThread(std::move(task));
  }

  void CallBlockingTaskOnWorkerThread(std::unique_ptr<v8::Task> task) override {
    return platform_->CallBlockingTaskOnWorkerThread(std::move(task));
  }

  void CallLowPriorityTaskOnWorkerThread(std::unique_ptr<v8::Task> task) override {
    return platform_->CallLowPriorityTaskOnWorkerThread(std::move(task));
  }

  void CallDelayedOnWorkerThread(std::unique_ptr<v8::Task> task, double delay_in_seconds) override {
    return platform_->CallDelayedOnWorkerThread(std::move(task), delay_in_seconds);
  }

  bool IdleTasksEnabled(v8::Isolate* isolate) override {
    return platform_->IdleTasksEnabled(isolate);
  }

  std::unique_ptr<v8::JobHandle> PostJob(v8::TaskPriority priority, std::unique_ptr<v8::JobTask> job_task) override {
    return platform_->PostJob(priority, std::move(job_task));
  }

  double MonotonicallyIncreasingTime() override {
    return platform_->MonotonicallyIncreasingTime();
  }

  double CurrentClockTimeMillis() override {
    return platform_->CurrentClockTimeMillis();
  }

  StackTracePrinter GetStackTracePrinter() override {
    return platform_->GetStackTracePrinter();
  }

  v8::TracingController* GetTracingController() override {
    return platform_->GetTracingController();
  }

  void DumpWithoutCrashing() override {
    return platform_->DumpWithoutCrashing();
  }
};

int main(int argc, char* argv[]) {
  // Initialize V8.
  v8::V8::InitializeICUDefaultLocation(argv[0]);
  v8::V8::InitializeExternalStartupData(argv[0]);
  std::unique_ptr<v8::Platform> platform = std::make_unique<RestrictedPlatform>(v8::platform::NewDefaultPlatform());
  v8::V8::InitializePlatform(platform.get());
  v8::V8::Initialize();

  simulated_experiment();

  // Dispose the isolate and tear down V8.
  v8::V8::Dispose();
  v8::V8::ShutdownPlatform();
  return 0;
}
