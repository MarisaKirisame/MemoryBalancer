// Copyright 2015 the V8 project authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include "util.hpp"
#include "controller.hpp"
#include "runtime.hpp"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <iostream>
#include <nlohmann/json.hpp>
#include <chrono>
#include <future>
#include <thread>
#include <set>
#include <unistd.h>

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

struct RuntimeStat {
  size_t max_memory;
  size_t current_memory;
};

NLOHMANN_DEFINE_TYPE_NON_INTRUSIVE(RuntimeStat, max_memory, current_memory)

using SimulatedExperimentResult = std::vector<std::vector<RuntimeStat>>;
// todo: noise (have number fluctuate)
// todo: regime change (a program is a sequence of program)
// see how close stuff get to optimal split
void run_simulated_experiment(const Controller& c) {
  SimulatedExperimentResult ret;
  c->set_max_memory(20, c->lock());
  std::vector<std::shared_ptr<SimulatedRuntimeNode>> runtimes;
  runtimes.push_back(std::make_shared<SimpleSimulatedRuntimeNode>(/*max_working_memory_=*/0, /*garbage_rate_=*/1, /*gc_time_=*/5, /*work_=*/100));
  runtimes.push_back(std::make_shared<SimpleSimulatedRuntimeNode>(/*max_working_memory_=*/0, /*garbage_rate_=*/1, /*gc_time_=*/3, /*work_=*/100));
  runtimes.push_back(std::make_shared<SimpleSimulatedRuntimeNode>(/*max_working_memory_=*/0, /*garbage_rate_=*/1, /*gc_time_=*/2, /*work_=*/100));
  for (const auto& r: runtimes) {
    c->add_runtime(r, c->lock());
  }
  size_t i = 0;
  for (bool has_work=true; has_work; ++i) {
    std::vector<RuntimeStat> slice;
    has_work=false;
    for (const auto&r : runtimes) {
      std::cout << r->max_memory() << " " << r->current_memory() << std::endl;
      slice.push_back({/*max_memory=*/r->max_memory(), /*current_memory=*/r->current_memory()});
    }
    ret.push_back(slice);
    for (const auto&r : runtimes) {
      if (!r->is_done()) {
        r->tick();
        has_work=true;
      }
    }
  }
  std::cout << "time_taken: " << i << std::endl;
  log_json(ret);
}

void run_logged_experiment() {
  return;
  struct Segment {
    clock_t start_time;
    double gc_velocity;
  };
  using SimulationData = std::vector<Segment>;
  std::vector<SimulationData> data;
  size_t time_step = 1000;
  // a time step is how often we simulate a step.
  // the smaller it is the more fine grained the simulation become,
  // so it is more accurate
  // but the simulation cost(cpu cycles) will become higher.
  std::make_shared<LoggedRuntimeNode>(logs[0], time_step);
}
void simulated_experiment() {
  //run_simulated_experiment(std::make_shared<BalanceControllerNode>());
  //run_simulated_experiment(std::make_shared<FirstComeFirstServeControllerNode>());
  //run_simulated_experiment(std::make_shared<FixedControllerNode>());
}

int main(int argc, char* argv[]) {
  // Initialize V8.
  v8::V8::InitializeICUDefaultLocation(argv[0]);
  v8::V8::InitializeExternalStartupData(argv[0]);
  std::unique_ptr<v8::Platform> platform = std::make_unique<RestrictedPlatform>(v8::platform::NewDefaultPlatform());
  v8::V8::InitializePlatform(platform.get());
  v8::V8::Initialize();

  run_logged_experiment();

  // Dispose the isolate and tear down V8.
  v8::V8::Dispose();
  v8::V8::ShutdownPlatform();
  return 0;
}
