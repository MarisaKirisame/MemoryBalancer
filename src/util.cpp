#include "util.hpp"

#include <boost/accumulators/accumulators.hpp>
#include <boost/accumulators/statistics/stats.hpp>
#include <boost/accumulators/statistics/mean.hpp>
#include <boost/accumulators/statistics/variance.hpp>
#include <random>
#include <fstream>
#include <ctime>

namespace tag = boost::accumulators::tag;
using boost::accumulators::accumulator_set;
using boost::accumulators::stats;

std::string pad_string(const std::string& str, char pad, size_t length) {
  assert(length >= str.length());
  return std::string(length - str.length(), pad) + str;
}

std::string get_time() {
  std::time_t t = std::time(nullptr);
  std::tm* tm = std::localtime(&t);
  return
    pad_string(std::to_string(1900+tm->tm_year), '0', 4) + "-" +
    pad_string(std::to_string(1+tm->tm_mon), '0', 2) + "-" +
    pad_string(std::to_string(tm->tm_mday), '0', 2) + "-" +
    pad_string(std::to_string(tm->tm_hour), '0', 2) + "-" +
    pad_string(std::to_string(tm->tm_min), '0', 2) + "-" +
    pad_string(std::to_string(tm->tm_sec), '0', 2);
}

double mean(const std::vector<double>& v) {
  accumulator_set<double, stats<tag::variance>> acc;
  for (double d: v) {
    acc(d);
  }
  return boost::accumulators::extract::mean(acc);
}

double sd(const std::vector<double>& v) {
  accumulator_set<double, stats<tag::variance>> acc;
  for (double d: v) {
    acc(d);
  }
  return sqrt(boost::accumulators::extract::variance(acc));
}

size_t random_heap_size() {
  static std::random_device rd;
  static std::mt19937 gen(rd());
  static std::uniform_real_distribution<> dist(log(min_heap_size), log(max_heap_size));
  return exp(dist(rd));
}

double median(const std::vector<double>& vec) {
  assert(vec.size() > 0);
  return (vec[(vec.size() - 1) / 2] + vec[vec.size() / 2]) / 2;
}

std::pair<std::vector<std::string>, std::string> split_string(const std::string& str) {
  std::vector<std::string> strings;
  std::string::size_type pos = 0;
  std::string::size_type prev = 0;
  while ((pos = str.find('\n', prev)) != std::string::npos) {
    std::string substr = str.substr(prev, pos - prev);
    strings.push_back(substr);
    prev = pos + 1;
  }
  return {strings, str.substr(prev)};
}

void log_json(const json& j, const std::string& type) {
  std::ofstream f("../logs/" + get_time());
  json output;
  output["version"] = "2020-4-23";
  output["type"] = type;
  output["data"] = j;
  f << output;
}
