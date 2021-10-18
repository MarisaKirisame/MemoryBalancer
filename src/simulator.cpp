#include "simulator.hpp"

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
  // WEIRD: I didnt record the start time of the program...
  // this mean i dont know the duration between the start of the program and the zeroth gc.
  // rn lets just start the whole thing from the zeroth gc.
  for (size_t i = 1; i < log_major_gc.size(); ++i) {
    // may be false!
    // assert(log_major_gc[i].before_memory >= log_major_gc[i].after_memory);
    Segment s;
    s.begin = mutator_time;
    s.duration = log_major_gc[i].before_time - log_major_gc[i-1].after_time;
    mutator_time += s.duration;
    // todo: interpolate between the two gc?
    s.garbage_rate = (static_cast<double>(log_major_gc[i].before_memory) - static_cast<double>(log_major_gc[i-1].after_memory)) / static_cast<double>(s.duration);
    // garbage rate may be < 0 with minor gc / external resource
    s.gc_duration = log_major_gc[i].after_time - log_major_gc[i].before_time;
    s.start_working_memory = log_major_gc[i-1].after_memory;
    s.end_working_memory = log_major_gc[i].after_memory;
    data.push_back(s);
  }
  // a time step is how often we simulate a step.
  // the smaller it is the more fine grained the simulation become,
  // so it is more accurate
  // but the simulation cost(cpu cycles) will become higher.
  clock_t time_step = 1000;
  auto f = std::make_shared<Finder>(data);
  auto ret = std::make_shared<SimulatedRuntimeNode>(
    /*work_=*/mutator_time / time_step,
    // we have to interpolate the working memory to keep invariant. or else the delta of working memory will > the delta of current memory!
    /*working_memory_=*/[=](size_t i) {
                          auto tup = f->get_segment(i * time_step);
                          auto seg = std::get<0>(tup);
                          auto progress = std::get<1>(tup);
                          return interpolate(seg.end_working_memory, seg.start_working_memory, progress);
                        },
    /*garbage_rate_=*/[=](size_t i) {
                        return time_step * f->get_segment_data(i * time_step).garbage_rate;
                      },
    /*gc_duration_=*/[=](size_t i) {
                       auto gcd = f->get_segment_data(i * time_step).gc_duration;
                       // gc should at least take 1 tick
                       assert(gcd >= time_step);
                       return gcd / time_step;
                     });
  for (size_t i = 1; i < ret->work_amount; ++i) {
    auto gr = ret->garbage_rate_(i);
    auto wmd = ptrdiff_t(ret->working_memory_(i)) - ptrdiff_t(ret->working_memory_(i-1));
    // false due to floating point inaccuracy...
    // std::cout << "garbage_rate: " << gr << " working_memory delta: " << wmd << std::endl;
    // assert(gr >= wmd);
  }
  return ret;
}

SimulatedExperimentReport run_simulated_experiment(const Controller& c, SimulatedRuntimes runtimes, const SimulatedExperimentConfig& cfg) {
  std::shuffle(runtimes.begin(), runtimes.end(), std::default_random_engine(cfg.seed));

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
  runtimes.push_back(std::make_shared<SimulatedRuntimeNode>(/*work_=*/100, /*working_memory_=*/make_const(0), /*garbage_rate_=*/make_const(1), /*gc_duration_=*/make_const(5)));
  runtimes.push_back(std::make_shared<SimulatedRuntimeNode>(/*work_=*/100, /*working_memory_=*/make_const(0), /*garbage_rate_=*/make_const(1), /*gc_duration_=*/make_const(3)));
  runtimes.push_back(std::make_shared<SimulatedRuntimeNode>(/*work_=*/100, /*working_memory_=*/make_const(0), /*garbage_rate_=*/make_const(1), /*gc_duration_=*/make_const(2)));
  SimulatedExperimentConfig cfg;
  cfg.print_frequency = 1;
  cfg.log_frequency = 1;
  report(run_simulated_experiment(c, runtimes, cfg));
}

void simulated_experiment(const Controller& c, const std::string& path) {
  c->set_max_memory(1e10, c->lock());
  SimulatedRuntimes rt;
  for (boost::filesystem::recursive_directory_iterator end, dir(path);
       dir != end; ++dir) {
    if (boost::filesystem::is_regular_file(dir->path())) {
      rt.push_back(from_log(parse_log(boost::filesystem::canonical(dir->path()).string())));
    }
  }
  SimulatedExperimentConfig cfg;
  cfg.log_frequency = 1000;
  run_simulated_experiment(c, rt, cfg);
}

// todo: modify this, and allow wrapping of from_log into remote_runtime, living on another thread.
SimulatedExperimentReport run_logged_experiment(Controller& c, const std::string& where) {
  SimulatedRuntimes rt;
  for (boost::filesystem::recursive_directory_iterator end, dir(where);
       dir != end; ++dir) {
    if (boost::filesystem::is_regular_file(dir->path())) {
      rt.push_back(from_log(parse_log(boost::filesystem::canonical(dir->path()).string())));
    }
  }
  SimulatedExperimentConfig cfg;
  cfg.num_of_cores = 8;
  cfg.seed = 1;
  auto ret = run_simulated_experiment(c, rt, cfg);
  report(ret);
  return ret;
}

void pareto_curve(const std::string& where) {
  size_t start = 3e8;
  size_t end = 5e8;
  size_t sample = 50;
  assert(sample >= 2);
  ParetoCurveResult pcr;
  for (size_t i = 0; i < sample; ++i) {
    std::unordered_map<std::string, SimulatedExperimentReport> controllers;
    size_t point = start + (end - start) * i / (sample - 1);
    auto run =
      [&](const std::string& name, Controller c) {
        c->set_max_memory(point, c->lock());
        std::cout << "running " << name << " controller on memory " << point << std::endl;
        auto ser = run_logged_experiment(c, where);
        controllers.insert({name, ser});
      };
    run("fcfs", std::make_shared<FirstComeFirstServeControllerNode>());
    run("bingbang", std::make_shared<BingBangControllerNode>());
    run("balance(no-weight)", std::make_shared<BalanceControllerNode>(HeuristicConfig {false, OptimizeFor::time}));
    run("balance(weighted)", std::make_shared<BalanceControllerNode>(HeuristicConfig {true, OptimizeFor::time}));
    run("balance(throughput)", std::make_shared<BalanceControllerNode>(HeuristicConfig {false, OptimizeFor::throughput}));
    pcr.points.push_back({point, controllers});
  }
  log_json(pcr, "simulated experiment(pareto curve)");
}

void multiple_pareto_curve() {
  //todo: implement me
  throw;
}
