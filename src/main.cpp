// Copyright 2015 the V8 project authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include "util.hpp"
#include "controller.hpp"
#include "runtime.hpp"
#include "boost/filesystem.hpp"

#include <iostream>
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
using SimulatedRuntime = std::shared_ptr<SimulatedRuntimeNode>;
using SimulatedRuntimes = std::vector<SimulatedRuntime>;

void run_simulated_experiment(const Controller& c, const SimulatedRuntimes& runtimes, size_t print_frequency, size_t log_frequency) {
  for (const auto& r: runtimes) {
    c->add_runtime(r, c->lock());
  }
  SimulatedExperimentResult ret;
  size_t i = 0;
  for (bool has_work=true; has_work; ++i) {
    std::vector<RuntimeStat> slice;
    has_work=false;
    size_t total_memory = 0, total_live_memory = 0;
    size_t total_work = 0, total_work_done = 0;
    for (const auto&r : runtimes) {
      slice.push_back({/*max_memory=*/r->max_memory(), /*current_memory=*/r->current_memory()});
      total_work += r->work_amount;
      total_work_done += r->mutator_time;
      total_memory += r->max_memory();
      total_live_memory += r->current_memory();
    }
    assert(total_memory == c->used_memory(c->lock()));
    if (i % print_frequency == 0) {
      size_t max_memory = c->max_memory(c->lock());
      std::cout <<
        "iteration:" << i <<
        ", work_done:" << total_work_done <<
        ", work:" << total_work <<
        ", %of work done:" << total_work_done * 100 / total_work <<
        ", memoy alive:" << total_live_memory <<
        ", memory used:" << total_memory <<
        ", memory avilable:" << max_memory <<
        ", live memory utilization:" << 100 * total_live_memory / max_memory << "%"
        ", memory utilization:" << 100 * total_memory / max_memory << "%" << std::endl;
    }
    if (i % log_frequency == 0) {
      ret.push_back(slice);
    }
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

// todo: noise (have number fluctuate)
// todo: regime change (a program is a sequence of program)
// see how close stuff get to optimal split
void run_simulated_experiment_prepare(const Controller& c) {
  c->set_max_memory(20, c->lock());
  SimulatedRuntimes runtimes;
  auto make_const = [](size_t i){ return std::function<size_t(size_t)>([=](size_t){ return i; }); };
  runtimes.push_back(std::make_shared<SimulatedRuntimeNode>(/*max_working_memory_=*/0, /*work_=*/100, /*garbage_rate_=*/make_const(1), /*gc_duration_=*/make_const(5)));
  runtimes.push_back(std::make_shared<SimulatedRuntimeNode>(/*max_working_memory_=*/0, /*work_=*/100, /*garbage_rate_=*/make_const(1), /*gc_duration_=*/make_const(3)));
  runtimes.push_back(std::make_shared<SimulatedRuntimeNode>(/*max_working_memory_=*/0, /*work_=*/100, /*garbage_rate_=*/make_const(1), /*gc_duration_=*/make_const(2)));
  run_simulated_experiment(c, runtimes, 1, 1);
}

using Log = std::vector<v8::GCRecord>;
struct Segment {
  clock_t begin;
  size_t duration;
  double garbage_rate;
  size_t gc_duration, working_memory;
};

struct Finder {
  std::vector<Segment> data;
  size_t idx = 0;
  const Segment& get_segment(clock_t time) {
    size_t seen_begin = idx, seen_end = idx;
    while (idx < data.size()) {
      assert(!(seen_begin <= idx && idx < seen_end));
      seen_begin = std::min(idx, seen_begin);
      seen_end = std::max(idx+1, seen_end);
      const Segment& g = data[idx];
      if (g.begin <= time && time < g.begin + g.duration) {
        return g;
      } else if (!(g.begin <= time)) {
        assert(idx > 0);
        --idx;
      } else {
        assert(!(time < g.begin + g.duration));
        ++idx;
      }
    }
    std::cout << time << " not found" << std::endl;
    assert(idx < data.size());
    throw;
  }
  Finder(const std::vector<Segment>& data) : data(data) { }
};

Log parse_log(const std::string& path) {
  Log log;
  std::ifstream f(path);
  std::string line;
  while (std::getline(f, line)) {
    std::istringstream iss(line);
    json j;
    iss >> j;
    log.push_back(j.get<v8::GCRecord>());
  }
  return log;
}
SimulatedRuntime from_log(const Log& log) {
  Log log_major_gc;
  std::vector<Segment> data;
  for (const auto& l: log) {
    if (l.is_major_gc) {
      log_major_gc.push_back(l);
    }
  }
  clock_t mutator_time = 0;
  assert(log_major_gc.size() > 0);
  for (size_t i = 1; i < log_major_gc.size(); ++i) {
    Segment s;
    s.begin = mutator_time;
    s.duration = log_major_gc[i].before_time - log_major_gc[i-1].after_time;
    mutator_time += s.duration;
    // todo: interpolate between the two gc?
    s.garbage_rate = (log_major_gc[i].before_memory - log_major_gc[i-1].after_memory) / static_cast<double>(s.duration);
    s.gc_duration = log_major_gc[i-1].after_time - log_major_gc[i-1].before_time;
    s.working_memory = log_major_gc[i-1].after_memory;
    data.push_back(s);
  }
  // a time step is how often we simulate a step.
  // the smaller it is the more fine grained the simulation become,
  // so it is more accurate
  // but the simulation cost(cpu cycles) will become higher.
  clock_t time_step = 10000;
  auto f = std::make_shared<Finder>(data);
  return std::make_shared<SimulatedRuntimeNode>(
    /*max_working_memory_=*/0,
    /*work_=*/mutator_time / time_step,
    /*garbage_rate_=*/[=](size_t i){ return time_step * f->get_segment(i * time_step).garbage_rate; },
    /*gc_duration_=*/[=](size_t i){ return f->get_segment(i * time_step).gc_duration; });
}

void run_logged_experiment() {
  Controller c = std::make_shared<BalanceControllerNode>();
  c->set_max_memory(2e9, c->lock());
  SimulatedRuntimes rt;
  for (boost::filesystem::recursive_directory_iterator end, dir(std::string(getenv("HOME")) + "/gc_log");
       dir != end; ++dir ) {
    if (boost::filesystem::is_regular_file(dir->path())) {
      rt.push_back(from_log(parse_log(boost::filesystem::canonical(dir->path()).string())));
    }
  }
  run_simulated_experiment(c, rt, 100, 1000);
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
