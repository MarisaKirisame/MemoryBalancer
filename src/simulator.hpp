#pragma once

#include "controller.hpp"
#include "runtime.hpp"
#include "util.hpp"

#include "boost/filesystem.hpp"

#include <random>
#include <vector>
#include <memory>
#include <unordered_map>

struct SimulatedExperimentOKReport {
  size_t time_taken;
  size_t ticks_taken;
  size_t ticks_in_gc;
};
NLOHMANN_DEFINE_TYPE_NON_INTRUSIVE(SimulatedExperimentOKReport, time_taken, ticks_taken, ticks_in_gc)

using SimulatedExperimentReport = std::optional<SimulatedExperimentOKReport>;

struct ParetoCurvePoint {
  size_t memory;
  std::unordered_map<std::string, SimulatedExperimentReport> controllers;
};

NLOHMANN_DEFINE_TYPE_NON_INTRUSIVE(ParetoCurvePoint, memory, controllers)

struct ParetoCurveResult {
  std::vector<ParetoCurvePoint> points;
};

NLOHMANN_DEFINE_TYPE_NON_INTRUSIVE(ParetoCurveResult, points)

using Log = std::vector<v8::GCRecord>;
struct Segment {
  clock_t begin;
  size_t duration;
  double garbage_rate;
  size_t gc_duration;
  size_t start_working_memory, end_working_memory;
};

// there might be some rounding error breaking invariant in the extreme case?
template<typename T>
T interpolate(const T& a, const T& b, double a_ratio) {
  return T(a * a_ratio + b * (1 - a_ratio));
}

// interpolate(a, b, uninterpolate(a, b, c)) = c modulo floating point error
template<typename T>
double uninterpolate(const T& a, const T& b, const T& c) {
  return double(c - b) / double(a - b);
}

struct Finder {
  std::vector<Segment> data;
  size_t idx = 0;
  std::tuple<const Segment&, double/*progress*/> get_segment(clock_t time) {
    size_t seen_begin = idx, seen_end = idx;
    while (idx < data.size()) {
      assert(!(seen_begin <= idx && idx < seen_end));
      seen_begin = std::min(idx, seen_begin);
      seen_end = std::max(idx+1, seen_end);
      const Segment& g = data[idx];
      if (g.begin <= time && time < g.begin + g.duration) {
        // we are returning progress, so 1 when at the end of the segment
        return {g, uninterpolate<size_t>(g.begin + g.duration, g.begin, time)};
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
  const Segment& get_segment_data(clock_t time) {
    return std::get<0>(get_segment(time));
  }
  double get_segment_progress(clock_t time) {
    return std::get<1>(get_segment(time));
  }
  Finder(const std::vector<Segment>& data) : data(data) { }
};

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
  // do not use 0 as a seed - in glibc that's the same as seed 1. just start from 1 and go up.
  unsigned int seed = 1;
};

void pareto_curve(const std::string& where);
