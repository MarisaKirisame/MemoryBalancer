// Copyright 2015 the V8 project authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// todo: deal with copyright

#include "util.hpp"
#include "controller.hpp"
#include "runtime.hpp"
#include "boost/filesystem.hpp"

#include <iostream>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <iostream>
#include <chrono>
#include <future>
#include <thread>
#include <set>
#include <unistd.h>

#ifdef USE_V8
#include "v8_util.hpp"
#endif

namespace nlohmann {

	template <class T>
	void to_json(nlohmann::json& j, const std::optional<T>& v)
	{
		if (v.has_value()) {
			j["tag"] = "Some";
      j["value"] = *v;
    }
		else {
      j["tag"] = "None";
    }
	}

	template <class T>
	void from_json(const nlohmann::json& j, std::optional<T>& v)
	{
		if (j["tag"] == "Some") {
      j.at("value").get_to(*v);
    } else {
      v = std::nullopt;
    }
	}
} // namespace nlohmann

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

void log_json(const json& j, const std::string& type) {
  std::ofstream f("../logs/" + get_time());
  json output;
  output["version"] = "2020-4-23";
  output["type"] = type;
  output["data"] = j;
  f << output;
}

#ifdef USE_V8

size_t run(const Input& i, std::mutex* m) {
  std::cout << "running " << i.code_path << std::endl;
  // Create a new Isolate and make it the current one.
  v8::Isolate::CreateParams create_params;
  //create_params.constraints.ConfigureDefaults(heap_size, 0);
  create_params.constraints.ConfigureDefaultsFromHeapSize(i.heap_size, i.heap_size);
  size_t old = create_params.constraints.max_old_generation_size_in_bytes();
  size_t young = create_params.constraints.max_young_generation_size_in_bytes();
  //std::cout << old << " " << young << " " << old + young << std::endl;
  create_params.array_buffer_allocator =
      v8::ArrayBuffer::Allocator::NewDefaultAllocator();
  size_t run_time_taken;
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
      run_time_taken = duration_cast<milliseconds>(end - begin).count();
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
  return run_time_taken;
}

void read_write() {
  std::mutex m;
  m.lock();

  std::ifstream t("balancer-config");
  json j;
  t >> j;

  Input i = read_from_json(j);
  std::future<size_t> o = std::async(std::launch::async, run, i, &m);

  m.unlock();
  j["time_taken"] = o.get();

  log_json(j, "v8-experiment");
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

  std::vector<std::future<size_t>> futures;
  for (const Input& input : inputs) {
    futures.push_back(std::async(std::launch::async, run, input, &m));
  }

  m.unlock();

  size_t total_time = 0;
  for (std::future<size_t>& future : futures) {
    total_time += future.get();
  }

  std::cout << "total_time = " << total_time << std::endl;
}
#endif

struct RuntimeStat {
  size_t max_memory;
  size_t current_memory;
};

NLOHMANN_DEFINE_TYPE_NON_INTRUSIVE(RuntimeStat, max_memory, current_memory)

struct RuntimeTrace {
  size_t start;
  std::vector<RuntimeStat> stats;
  RuntimeTrace(size_t start) : start(start) { }
};

NLOHMANN_DEFINE_TYPE_NON_INTRUSIVE(RuntimeTrace, start, stats)

// todo: make this a member of Result
using SimulatedExperimentResult = std::vector<RuntimeTrace>;

using SimulatedRuntime = std::shared_ptr<SimulatedRuntimeNode>;
using SimulatedRuntimes = std::vector<SimulatedRuntime>;

using proportion = double;
struct SimulatedExperimentConfig {
  // none for no print
  std::optional<size_t> print_frequency;
  // none for no log
  std::optional<size_t> log_frequency;
  // none for no restriction
  std::optional<size_t> num_of_cores;
  proportion timeout_gc_proportion = 0.5;
};

struct SimulatedExperimentOKReport {
  size_t time_taken;
  size_t ticks_taken;
  size_t ticks_in_gc;
};
NLOHMANN_DEFINE_TYPE_NON_INTRUSIVE(SimulatedExperimentOKReport, time_taken, ticks_taken, ticks_in_gc)

using SimulatedExperimentReport = std::optional<SimulatedExperimentOKReport>;
void report(const SimulatedExperimentReport& r) {
  if (r) {
    std::cout <<
      "time_taken: " << r->time_taken <<
      ", total ticks taken: " << r->ticks_taken <<
      ", total ticks spent gcing: " << r->ticks_in_gc <<
      ", gc rate: " << 100 * r->ticks_in_gc / r->ticks_taken << "%" << std::endl;
  } else {
    std::cout << "timeout!" << std::endl;
  }
}

SimulatedExperimentReport run_simulated_experiment(const Controller& c, const SimulatedRuntimes& runtimes, const SimulatedExperimentConfig& cfg) {
  struct Process {
    SimulatedRuntime r;
    RuntimeTrace t;
  };

  auto l = c->lock();
  SimulatedRuntimes unstarted_runtimes;
  std::vector<RuntimeTrace> finished_traces;
  std::vector<Process> running_processes;

  size_t total_work = 0;
  for (const auto& r: runtimes) {
    unstarted_runtimes.push_back(r);
    total_work += r->work_amount;
  }

  size_t i = 0;

  size_t tick = 0;
  size_t tick_in_gc = 0;
  size_t tick_since_print = 0;
  size_t tick_in_gc_since_print = 0;

  while((!cfg.num_of_cores || running_processes.size() < *cfg.num_of_cores) && !unstarted_runtimes.empty()) {
    SimulatedRuntime r = unstarted_runtimes.back();
    unstarted_runtimes.pop_back();
    assert(!r->is_done());
    c->add_runtime(r, l);
    running_processes.push_back({r, RuntimeTrace(0)});
  }
  assert(!cfg.num_of_cores || *cfg.num_of_cores > 0);
  for (bool has_work=true; has_work; ++i) {
    has_work=false;
    size_t total_memory = 0, total_live_memory = 0;
    for (auto& p : running_processes) {
      auto& r = p.r;
      if (cfg.log_frequency && i % *cfg.log_frequency == 0) {
        p.t.stats.push_back({r->max_memory(), r->current_memory()});
      }
      total_memory += r->max_memory();
      total_live_memory += r->current_memory();
    }
    assert(total_memory == c->used_memory(l));
    size_t remaining_processes = running_processes.size() + unstarted_runtimes.size();
    for (size_t j = 0; j < running_processes.size();) {
      auto& p = running_processes[j];
      auto& r = p.r;
      if (!r->is_done()) {
        has_work=true;
        r->tick();
        tick++;
        tick_since_print++;
        if (r->in_gc) {
          tick_in_gc++;
          tick_in_gc_since_print++;
        }
        ++j;
      } else {
        std::swap(p, running_processes.back());
        finished_traces.push_back(running_processes.back().t);
        running_processes.pop_back();
        if (!unstarted_runtimes.empty()) {
          SimulatedRuntime r = unstarted_runtimes.back();
          unstarted_runtimes.pop_back();
          assert(!r->is_done());
          c->add_runtime(r, l);
          running_processes.push_back({r, RuntimeTrace(cfg.log_frequency ? i / *cfg.log_frequency : 0)});
        }
      }
    }
    if (cfg.print_frequency && i % *cfg.print_frequency == 0) {
      size_t max_memory = c->max_memory(l);
      std::cout <<
        "iteration:" << i <<
        ", total work done: " << (tick - tick_in_gc) <<
        ", work done:" << (tick - tick_in_gc) * 100 / total_work << "%" <<
        ", live memory utilization:" << 100 * total_live_memory / max_memory << "%"
        ", memory utilization:" << 100 * total_memory / max_memory << "%" <<
        ", gc rate:" << 100 * tick_in_gc_since_print / tick_since_print << "%" <<
        ", remaining process:" << remaining_processes << std::endl;
      tick_since_print = 0;
      tick_in_gc_since_print = 0;
    }
    if (tick * cfg.timeout_gc_proportion <= tick_in_gc) {
      return SimulatedExperimentReport();
    }
  }
  if (cfg.log_frequency) {
    log_json(finished_traces, "simulated experiment(single run)");
  }
  return SimulatedExperimentOKReport({i, tick, tick_in_gc});
}

// todo: noise (have number fluctuate)
// todo: regime change (a program is a sequence of program)
// see how close stuff get to optimal split
void run_simulated_experiment_prepare(const Controller& c) {
  c->set_max_memory(20, c->lock());
  SimulatedRuntimes runtimes;
  auto make_const = [](size_t i){ return std::function<size_t(size_t)>([=](size_t){ return i; }); };
  runtimes.push_back(std::make_shared<SimulatedRuntimeNode>(/*work_=*/100, /*max_working_memory_=*/make_const(0), /*garbage_rate_=*/make_const(1), /*gc_duration_=*/make_const(5)));
  runtimes.push_back(std::make_shared<SimulatedRuntimeNode>(/*work_=*/100, /*max_working_memory_=*/make_const(0), /*garbage_rate_=*/make_const(1), /*gc_duration_=*/make_const(3)));
  runtimes.push_back(std::make_shared<SimulatedRuntimeNode>(/*work_=*/100, /*max_working_memory_=*/make_const(0), /*garbage_rate_=*/make_const(1), /*gc_duration_=*/make_const(2)));
  SimulatedExperimentConfig cfg;
  cfg.print_frequency = 1;
  cfg.log_frequency = 1;
  report(run_simulated_experiment(c, runtimes, cfg));
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
    s.garbage_rate = (static_cast<double>(log_major_gc[i].before_memory) - static_cast<double>(log_major_gc[i-1].after_memory)) / static_cast<double>(s.duration);
    s.gc_duration = log_major_gc[i-1].after_time - log_major_gc[i-1].before_time;
    s.working_memory = log_major_gc[i-1].after_memory;
    data.push_back(s);
  }
  // a time step is how often we simulate a step.
  // the smaller it is the more fine grained the simulation become,
  // so it is more accurate
  // but the simulation cost(cpu cycles) will become higher.
  clock_t time_step = 1000;
  auto f = std::make_shared<Finder>(data);
  return std::make_shared<SimulatedRuntimeNode>(
    /*work_=*/mutator_time / time_step,
    /*max_working_memory_=*/[=](size_t i) { return f->get_segment(i * time_step).working_memory; },
    /*garbage_rate_=*/[=](size_t i) { return time_step * f->get_segment(i * time_step).garbage_rate; },
    /*gc_duration_=*/[=](size_t i) {
                       auto gcd = f->get_segment(i * time_step).gc_duration;
                       assert(gcd >= time_step);
                       return gcd / time_step;
                     });
}

SimulatedExperimentReport run_logged_experiment(Controller &c, const char *where) {
  SimulatedRuntimes rt;
  for (boost::filesystem::recursive_directory_iterator end, dir(where);
       dir != end; ++dir) {
    if (boost::filesystem::is_regular_file(dir->path())) {
      rt.push_back(from_log(parse_log(boost::filesystem::canonical(dir->path()).string())));
    }
  }
  SimulatedExperimentConfig cfg;
  cfg.num_of_cores = 100;
  auto ret = run_simulated_experiment(c, rt, cfg);
  report(ret);
  return ret;
}

struct ParetoCurvePoint {
  size_t memory;
  SimulatedExperimentReport balance_controller, fcfs_controller;
};

NLOHMANN_DEFINE_TYPE_NON_INTRUSIVE(ParetoCurvePoint, memory, balance_controller, fcfs_controller)

struct ParetoCurveResult {
  std::vector<ParetoCurvePoint> points;
};

NLOHMANN_DEFINE_TYPE_NON_INTRUSIVE(ParetoCurveResult, points)

void pareto_curve(const char *where) {
  size_t start = 1e8;
  size_t end = 1e9;
  size_t sample = 100;
  assert(sample >= 2);
  ParetoCurveResult pcr;
  for (size_t i = 0; i < sample; ++i) {
    size_t point = start + (end - start) * i / (sample - 1);
    std::cout << "running balance controller on memory " << point << std::endl;
    Controller bc = std::make_shared<BalanceControllerNode>();
    bc->set_max_memory(point, bc->lock());
    auto bc_ser = run_logged_experiment(bc, where);
    std::cout << "running fcfs controller on memory " << point << std::endl;
    Controller fc = std::make_shared<FirstComeFirstServeControllerNode>();
    fc->set_max_memory(point, fc->lock());
    auto fc_ser = run_logged_experiment(fc, where);
    pcr.points.push_back({point, bc_ser, fc_ser});
  }
  log_json(pcr, "simulated experiment(pareto curve)");
}

void simulated_experiment() {
  //run_simulated_experiment(std::make_shared<BalanceControllerNode>());
  //run_simulated_experiment(std::make_shared<FirstComeFirstServeControllerNode>());
  //run_simulated_experiment(std::make_shared<FixedControllerNode>());
}

#ifdef USE_V8
struct V8RAII {
  std::unique_ptr<v8::Platform> platform;
  V8RAII(const std::string& exec_location) {
    // Initialize V8.
    v8::V8::InitializeICUDefaultLocation(exec_location.c_str());
    v8::V8::InitializeExternalStartupData(exec_location.c_str());
    platform = std::make_unique<RestrictedPlatform>(v8::platform::NewDefaultPlatform());
    v8::V8::InitializePlatform(platform.get());
    v8::V8::Initialize();
  }
  ~V8RAII() {
    // Dispose the isolate and tear down V8.
    v8::V8::Dispose();
    v8::V8::ShutdownPlatform();
  }
};
#endif

int main(int argc, char* argv[]) {
#ifdef USE_V8
  V8RAII v8(argv[0]);
#endif
  pareto_curve(argc > 1 ? argv[1] : "../gc_log");
  return 0;
}
