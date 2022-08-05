#include <boost/filesystem.hpp>
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
#include <random>
#include <unordered_map>
#include <shared_mutex>
#include <poll.h>
#include <TextTable.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <queue>

#include "util.hpp"
#include "v8_util.hpp"
#include "hyperparam.hpp"

#include <cxxopts.hpp>

struct Dual {
  double v;
  double d;
  Dual(double v, double d) : v(v), d(d) {
    assert(!std::isnan(d));
  }
  Dual(const double& v) : v(v), d(0) { }
  Dual operator+(const Dual& rhs) const {
    return Dual(v + rhs.v, d + rhs.d);
  }
  Dual operator*(const Dual& rhs) const {
    return Dual(v * rhs.v, d * rhs.v + rhs.d * v);
  }
  Dual operator/(const Dual& rhs) const {
    return Dual(v / rhs.v, (rhs.v * d - v * rhs.d)/(rhs.v * rhs.v));
  }
  bool operator>=(const Dual& rhs) const {
    return v >= rhs.v;
  }
  friend std::ostream& operator<<(std::ostream& os, const Dual& d);
};

std::ostream& operator<<(std::ostream& os, const Dual& d) {
  return os << "Dual(" << d.v << ", " << d.d << ")";
}

#define ERROR_STREAM std::cout << __LINE__ << " "

enum class Ord { LT, EQ, GT };

double binary_search_aux(double low, double high, const std::function<Ord(double)>& searcher) {
  double mid = (low + high) / 2;
  if (mid <= 1) {
    return 1.0;
  }
  assert(mid < 1e20);
  Ord ord = searcher(mid);
  if (ord == Ord::EQ) {
    return mid;
  } else if (ord == Ord::GT) {
    return binary_search_aux(0, mid, searcher);
  } else {
    assert(ord == Ord::LT);
    return binary_search_aux(mid, high, searcher);
  }
}

double binary_search(double low, double high, const std::function<Ord(double)>& searcher) {
  if (searcher(low) == Ord::GT) {
    std::cout << "binary search low assertion failed: " << low << std::endl;
  }
  assert(searcher(low) != Ord::GT);
  assert(searcher(high) != Ord::LT);
  return binary_search_aux(low, high, searcher);
}

// binary search, but we only know the lower bound (0), and not the upper bound.
// try to deduct it by repeat doubling of initial_guess.
double positive_binary_search_unbounded(double initial_guess, const std::function<Ord(double)>& searcher) {
  assert(initial_guess > 0);
  assert(!std::isinf(initial_guess));
  Ord ord = searcher(initial_guess);
  if (ord == Ord::EQ) {
    return initial_guess;
  } else if (ord == Ord::GT) {
    return binary_search(0, initial_guess, searcher);
  } else {
    assert(ord == Ord::LT);
    return positive_binary_search_unbounded(initial_guess * 2, searcher);
  }
}

std::string socket_path = "/tmp/membalancer_socket";

int get_listener() {
  sockaddr_un local = { .sun_family = AF_UNIX };
  int s = socket(AF_UNIX, SOCK_STREAM, 0);
  assert(s != -1);
  strcpy(local.sun_path, socket_path.c_str());
  unlink(local.sun_path);
  if (bind(s, reinterpret_cast<sockaddr*>(&local), strlen(local.sun_path) + sizeof(local.sun_family)) == -1) {
    ERROR_STREAM << strerror(errno) << std::endl;
    throw;
  }
  if (listen(s, 100) == -1) {
    ERROR_STREAM << strerror(errno) << std::endl;
    throw;
  }
  return s;
}

using socket_t = int;

bool send_string(socket_t s, const std::string& msg) {
  if (::send(s, msg.c_str(), msg.size(), MSG_NOSIGNAL) != msg.size()) {
    ERROR_STREAM << strerror(errno) << std::endl;
    return false;
  }
  return true;
}

// channel over idempotent message.
// without this, the balancer only change behavior based on message recieved back.
// so, the more frequent balancer act, the more message it will send - including lots of identical one.
// this stop all identical message from sending.
// note: this is incomplete. with some timed base algorithm (e.g. a PD controller),
// lots of similar message will still be sent.
struct IdChannel {
  socket_t s;
  bool has_last_message = false;
  std::string last_message;
  IdChannel(socket_t s) : s(s) { }
  void send(const std::string& msg) {
    if (!(has_last_message && last_message == msg)) {
      send_string(s, msg);
      has_last_message = true;
      last_message = msg;
    }
  }
};

double big_change(double old_value, double new_value) {
  return abs((new_value - old_value) / old_value) > 0.1;
}

// avoid sending multiple similar message
struct Snapper {
  bool has_last_value = false;
  size_t last_value;
  bool operator()(size_t value) {
    if ((!has_last_value) || big_change(last_value, value)) {
      has_last_value = true;
      last_value = value;
      return true;
    } else {
      return false;
    }
  }
};

time_point program_begin = steady_clock::now();

std::string gen_name() {
  static size_t i = 0;
  return "x_" + std::to_string(i++);
}

using ByteDiffsAndDuration = std::pair<int64_t, double>;

size_t get_starting_index(size_t len) {
  return 0;
}

template<typename T>
T nneg(const T& t) {
  assert(t >= 0);
  return t;
}

// all duration is in milliseconds, and all speed is in bytes per milliseconds.
struct ConnectionState {
  size_t wait_ack_count = 0;
  socket_t fd;
  IdChannel force_gc_chan;
  Snapper heap_resize_snap;
  std::string unprocessed;
  size_t working_memory = 0;
  size_t current_memory; // this is for logging plotting only, it does not change any action we do.
  // real max memory is for efficiency calculation purpose only
  size_t max_memory;
  size_t size_of_objects;
  std::vector<ByteDiffsAndDuration> gc_bad, allocation_bad;
  std::vector<json> memory_log;
  std::vector<ByteDiffsAndDuration> adjusted_allocation_bad() {
    std::vector<ByteDiffsAndDuration> ret = allocation_bad;
    size_t i = 0;
    for (size_t j = 1; j < memory_log.size(); ++j) {
      auto i_log = memory_log[i];
      int64_t i_size = i_log["SizeOfObjects"];
      int64_t i_time = i_log["time"];
      auto j_log = memory_log[j];
      int64_t j_size = j_log["SizeOfObjects"];
      int64_t j_time = j_log["time"];
      assert(j_time > i_time);
      if (j_size >= i_size) {
        ret.push_back({j_size - i_size, j_time - i_time});
        i = j;
      }
    }
    return ret;
    if (memory_log.empty()) {
      return allocation_bad;
    } else {
      auto ret = allocation_bad;
      assert(!allocation_bad.empty());
      ret.back().first += static_cast<int64_t>(memory_log.back()["SizeOfObjects"]) - static_cast<int64_t>(memory_log.front()["SizeOfObjects"]);
      ret.back().second += static_cast<int64_t>(memory_log.back()["time"]) - static_cast<int64_t>(memory_log.front()["time"]);
      return ret;
    }
  }
  double garbage_rate() {
    auto aabad = adjusted_allocation_bad();
    double garbage_bytes = initial_garbage_bytes;
    double garbage_duration = initial_garbage_duration;
    for (size_t i = get_starting_index(aabad.size()); i < aabad.size(); ++i) {
      const auto& bad = aabad[i];
      double decay = pow(garbage_rate_decay_per_sec, bad.second / 1000000000);
      garbage_bytes += bad.first;
      garbage_bytes *= decay;
      garbage_duration += bad.second;
      garbage_duration *= decay;
    }
    auto ret = garbage_bytes / garbage_duration;
    assert(ret <= 100);
    return ret;
  }
  double gc_speed() {
    return gc_bytes() / gc_duration();
  }
  double gc_duration() {
    double ret = 0;
    for (size_t i = get_starting_index(gc_bad.size()); i < gc_bad.size(); ++i) {
      const auto& bad = gc_bad[i];
      ret += bad.second;
      ret *= gc_speed_smoothing_per_sample;
    }
    return ret;
  }
  double average_gc_duration() {
    return gc_duration() / (gc_bad.size() - get_starting_index(gc_bad.size()));
  }
  double gc_bytes() {
    double ret = 0;
    for (size_t i = get_starting_index(gc_bad.size()); i < gc_bad.size(); ++i) {
      const auto& bad = gc_bad[i];
      ret += bad.first;
      ret *= gc_speed_smoothing_per_sample;
      // we should not add bias_in_working_memory here
      // - this is only used in calculating gc_speed, and we should only change how size is measured.
    }
    return ret;
  }
  size_t last_major_gc_epoch;
  size_t begin_time, current_time;
  time_point last_major_gc;
  std::string name;
  std::string guid;
  ConnectionState(socket_t fd) :
    fd(fd),
    force_gc_chan(fd) { }
  void accept(const std::string& str, size_t epoch) {
    unprocessed += str;
    auto p = split_string(unprocessed);
    for (const auto& str: p.first) {
      std::istringstream iss(str);
      json j;
      iss >> j;
      json type = j["type"];
      json data = j["data"];
      if (type == "gc") {
        if (name == "") {
          name = data["name"];
          if (name == "") {
            name = gen_name();
          }
        } else {
          assert(name == data["name"] || data["name"] == "");
        }
        if (wait_ack_count == 0) {
          if (this->gc_bad.size() == 0) {
            begin_time = static_cast<size_t>(data["before_time"]);
          }
          current_time = static_cast<size_t>(data["after_time"]);
          last_major_gc = steady_clock::now();
          last_major_gc_epoch = epoch;
          size_t adjusted_working_memory = static_cast<size_t>(data["after_memory"]);
          working_memory = adjusted_working_memory;
          current_memory = working_memory;
          size_t adjusted_max_memory = std::max(static_cast<size_t>(data["max_memory"]), adjusted_working_memory);
          max_memory = adjusted_max_memory;
          assert(max_memory >= working_memory);
          size_of_objects = data["size_of_objects"];
          ByteDiffsAndDuration gc_bad;
          //gc_bad.first = data["before_memory"];
          gc_bad.first = data["gc_bytes"];
          gc_bad.second = data["gc_duration"];
          this->gc_bad.push_back(gc_bad);
          ByteDiffsAndDuration allocation_bad;
          allocation_bad.first = data["allocation_bytes"];
          allocation_bad.second = data["allocation_duration"];
          this->allocation_bad.push_back(allocation_bad);
          memory_log.clear();
        }
      } else if (type == "max_memory") {
        if (wait_ack_count == 0) {
          max_memory = data;
          assert(max_memory >= working_memory);
        }
      } else if (type == "ack") {
        assert(wait_ack_count > 0);
        --wait_ack_count;
      } else if (type == "memory_timer") {
        memory_log.push_back(data);
        current_memory = static_cast<int64_t>(data["SizeOfObjects"]) + static_cast<int64_t>(data["AllocatedExternalMemorySinceMarkCompact"]);
        max_memory = std::max(static_cast<size_t>(data["Limit"]), working_memory);
        assert(max_memory >= working_memory);
      }
      else {
        std::cout << "unknown type: " << type << std::endl;
        throw;
      }
    }
    unprocessed = p.second;
  }
  bool should_balance() {
    return gc_bad.size() > 0 && allocation_bad.size() > 0 &&
      wait_ack_count == 0 /*&& memory_log.size() >= 2*/;
  }
  size_t extra_memory() {
    if (!(max_memory >= working_memory)) {
      std::cout << "assertion failed: " << max_memory << " " << working_memory << std::endl;
    }
    assert(max_memory >= working_memory);
    return max_memory - working_memory;
  }
  double gt() {
    return static_cast<double>(garbage_rate()) * static_cast<double>(average_gc_duration());
  }
  double duration_score() {
    assert(should_balance());
    size_t extra_memory_ = extra_memory();
    return static_cast<double>(extra_memory_) * static_cast<double>(extra_memory_) / gt();
  }
  double duration_balance_factor() {
    return sqrt(gt());
  }
  double speed_balance_factor() {
    return sqrt(static_cast<double>(garbage_rate()) * static_cast<double>(working_memory + bias_in_working_memory) / static_cast<double>(gc_speed()));
  }

  nlohmann::json report(TextTable& t, size_t epoch) {
    assert(should_balance());
    t.add(name);
    t.add(std::to_string(extra_memory()));
    t.add(std::to_string(max_memory));
    t.add(std::to_string(garbage_rate()));
    t.add(std::to_string(gc_speed()));

    nlohmann::json data;
    data["name"] = name;
    data["extra_mem"] = extra_memory()/1e6;
    data["max_mem"] = max_memory/1e6;
    data["gc_rate"] = garbage_rate()*1e3;
    data["gc_speed"] = gc_speed()*1e3;
    data["mem_diff"] = (max_memory - extra_memory())/1e6;
    return data;
  }
  double duration_utilization_rate(size_t extra_memory) {
    double mutator_duration = extra_memory / garbage_rate();
    assert(mutator_duration >= 0);
    return mutator_duration / (average_gc_duration() + mutator_duration);
  }
  double duration_utilization_rate() {
    return duration_utilization_rate(extra_memory());
  }
  double measured_duration_utilization_rate() {
    return 1 - static_cast<double>(gc_duration()) / (current_time - begin_time);
  }
  template<typename T>
  T speed_utilization_rate_generic(const T& extra_memory) {
    assert(garbage_rate() > 0);
    auto mutator_duration = extra_memory / garbage_rate();
    if (!(mutator_duration >= 0)) {
      std::cout << extra_memory << " " << garbage_rate() << " " << mutator_duration << std::endl;
    }
    assert(mutator_duration >= 0);
    auto useful_gc_duration = extra_memory / gc_speed();
    auto wasteful_gc_duration = (working_memory + bias_in_working_memory) / gc_speed();
    auto ret = (mutator_duration + useful_gc_duration) / (mutator_duration + useful_gc_duration + wasteful_gc_duration);
    if(!(ret >= 0)) {
      std::cout << mutator_duration << " " << useful_gc_duration << " " << wasteful_gc_duration << std::endl;
    }
    assert(ret >= 0);
    return ret;
  }
  double speed_utilization_rate(size_t extra_memory) {
    return speed_utilization_rate_generic<double>(extra_memory);
  }
  double speed_utilization_rate() {
    return speed_utilization_rate(std::max<size_t>(1, extra_memory()));
  }
  double speed_utilization_rate_d(size_t extra_memory) {
    Dual d = Dual(1) / speed_utilization_rate_generic<Dual>(Dual(extra_memory, 1));
    return d.d;
  }
  double speed_utilization_rate_d() {
    return speed_utilization_rate_d(std::max<size_t>(1, extra_memory()));
  }
};

// balance memory given a limit
enum class BalanceStrategy {
  // do nothing
  ignore,
  // use the sqrt forumla
  classic,
};

// change the sum of memory across all process
enum class ResizeStrategy {
  // do nothing
  ignore,
  gradient
};

std::ostream& operator<<(std::ostream& os, ResizeStrategy rs) {
  if (rs == ResizeStrategy::ignore) {
    return os << "ignore";
  } else if (rs == ResizeStrategy::gradient) {
    return os << "gradient";
  } else {
    std::cout << "unknown ResizeStrategy" << std::endl;
    throw;
  }
}

struct Balancer {
  milliseconds balance_frequency;
  size_t update_count = 0;
  socket_t s = get_listener();
  std::vector<pollfd> pfds {{s, POLLIN}};
  std::unordered_map<socket_t, ConnectionState> map;
  std::vector<ConnectionState*> vector() {
    std::vector<ConnectionState*> vec;
    for (auto& p : map) {
      vec.push_back(&p.second);
    }
    return vec;
  }
  time_point last_balance = steady_clock::now();
  double tolerance = 0.1;
  BalanceStrategy balance_strategy;
  ResizeStrategy resize_strategy;
  size_t resize_amount; // only when resize_strategy == constant
  double gc_rate; // only when resize_strategy == after-balance or before-balance
  double gc_rate_d;
  size_t epoch = 0;
  std::string log_path;
  std::string tex_path;
  nlohmann::json tex_data;
  Balancer(const std::vector<char*>& args) {
    // note: we intentionally do not use any default option.
    // as all options is filled in by the eval program, there is no point in having default,
    // and it will hide error.
    cxxopts::Options options("Balancer", "Balance multiple v8 heap");
    options.add_options()
      ("balance-strategy", "ignore, classic, extra-memory", cxxopts::value<std::string>());
    options.add_options()
      ("resize-strategy", "ignore, before-balance, after-balance", cxxopts::value<std::string>());
    options.add_options()
      ("resize-amount", "a number denoting how much to resize", cxxopts::value<size_t>());
    options.add_options()
      ("gc-rate", "trying to spend this much time in gc", cxxopts::value<double>());
    options.add_options()
      ("gc-rate-d", "gc-rate in derivative", cxxopts::value<double>());
    options.add_options()
      ("balance-frequency", "milliseconds between balance", cxxopts::value<size_t>());
    auto result = options.parse(args.size(), args.data());
    assert(result.count("balance-strategy"));
    auto balance_strategy_str = result["balance-strategy"].as<std::string>();
    if (balance_strategy_str == "ignore") {
      balance_strategy = BalanceStrategy::ignore;
    } else if (balance_strategy_str == "classic") {
      balance_strategy = BalanceStrategy::classic;
    } else {
      std::cout << "UNKNOWN BALANCER TYPE: " << balance_strategy_str << std::endl;
    }
    assert(result.count("resize-strategy"));
    std::string resize_strategy_str = result["resize-strategy"].as<std::string>();
    if (resize_strategy_str == "ignore") {
      resize_strategy = ResizeStrategy::ignore;
    } else if (resize_strategy_str == "gradient") {
      resize_strategy = ResizeStrategy::gradient;
      assert(result.count("gc-rate-d"));
      gc_rate_d = result["gc-rate-d"].as<double>();
    } else {
      std::cout << "unknown resize-strategy: " << resize_strategy_str << std::endl;
      throw;
    }
    balance_frequency = milliseconds(result["balance-frequency"].as<size_t>());
  }
  void poll_daemon() {
    while (true) {
      int num_events = poll(pfds.data(), pfds.size(), -1);
      if (num_events != 0) {
        auto connection_closed = [&](size_t i) {
                                   map.at(pfds[i].fd).max_memory = 0;
                                   map.at(pfds[i].fd).current_memory = 0;
                                   map.at(pfds[i].fd).working_memory = 0;
                                   map.erase(pfds[i].fd);
                                   pfds[i] = pfds.back();
                                   pfds.pop_back();
                                 };
        auto close_connection = [&](size_t i) {
                                  close(pfds[i].fd);
                                  connection_closed(i);
                                };
        for (size_t i = 0; i < pfds.size();) {
          auto fd = pfds[i].fd;
          auto revents = pfds[i].revents;
          if (revents != 0) {
            if (fd == s) {
              assert(revents & POLLIN);
              sockaddr_un remote;
              socklen_t addrlen = sizeof remote;
              int newsocket = accept(s,
                                     (struct sockaddr *)&remote,
                                     &addrlen);
              if (newsocket == -1) {
                ERROR_STREAM << strerror(errno) << std::endl;
                throw;
              }
              pfds.push_back({newsocket, POLLIN});
              map.insert({newsocket, ConnectionState(newsocket)});
              ++i;
            } else if (revents & POLLIN) {
              char buf[1000];
              int n = recv(fd, buf, sizeof buf, 0);
              if (n == 0) {
                close_connection(i);
              } else if (n < 0) {
                if (errno = ECONNRESET) {
                  std::cout << "warning: membalancer close connection" << std::endl;
                  close_connection(i);
                } else {
                  ERROR_STREAM << strerror(errno) << std::endl;
                  throw;
                }
              } else {
                map.at(pfds[i].fd).accept(std::string(buf, n), epoch);;
                ++i;
              }
            } else {
              assert(revents & POLLHUP);
              close_connection(i);
            }
          } else {
            ++i;
          }
        }
      } else {
        assert(num_events == 0);
      }
      if (steady_clock::now() - last_balance > balance_frequency) {
        balance();
      }
    }
  }
  struct Stat {
    size_t instance_count = 0;
    double mse = 0;
    size_t m = 0;
    size_t e = 0;
    double gt_e = 0;
    double balance_factor = 0;
  };
  TextTable make_table() {
    TextTable t( '-', '|', '+' );
    t.add("name");
    t.add("extra_memory");
    t.add("total_memory");
    t.add("garbage_rate");
    t.add("gc_speed");
    t.add("suggested_extra_memory");
    t.add("suggested_total_memory");
    t.add("gc_rate");
    t.add("suggested_gc_rate");
    t.add("gc_rate_d");
    t.add("suggested_gc_rate_d");
    t.endOfRow();
    return t;
  }
  Stat get_stat(const std::vector<double>& scores) {
    double median_score = median(scores);
    Stat st;
    for (ConnectionState* rr: vector()) {
      if (rr->should_balance()) {
        ++st.instance_count;
        double diff = (rr->duration_score() - median_score) / median_score;
        st.mse += diff * diff;
        st.m += rr->max_memory;
        st.e += rr->extra_memory();
        st.gt_e += rr->gt() / rr->extra_memory();
        st.balance_factor += rr->speed_balance_factor();
      }
    }
    st.mse /= scores.size();
    return st;
  }
  size_t suggested_extra_memory(ConnectionState* rr, size_t total_extra_memory, const Stat& st) {
    assert(balance_strategy == BalanceStrategy::classic || balance_strategy == BalanceStrategy::ignore);
    if (st.balance_factor == 0) {
      return 0;
    } else {
      return total_extra_memory / st.balance_factor * rr->speed_balance_factor();
    }
  }
  Ord compare(double lhs, double rhs) {
    if (lhs < 0.9 * rhs) {
      return Ord::LT;
    } else if (lhs > 1.1 * rhs) {
      return Ord::GT;
    } else {
      return Ord::EQ;
    }
  }
  Ord compare_mu(double mu) {
    assert(0 <= mu);
    assert(mu <= 1);
    return compare(gc_rate, 1 - mu);
  }
  using memory_suggestion_t = std::unordered_map<ConnectionState*, size_t>;
  memory_suggestion_t calculate_suggestion(size_t total_extra_memory, const Stat& st) {
    memory_suggestion_t memory_suggestion;
    for (ConnectionState* rr: vector()) {
      if (rr->should_balance()) {
        memory_suggestion.insert({rr, suggested_extra_memory(rr, total_extra_memory, st)});
      }
    }
    return memory_suggestion;
  }
  double utilization(const memory_suggestion_t& memory_suggestion) {
    double u = 0;
    for (const auto& p : memory_suggestion) {
      u += p.first->speed_utilization_rate(p.second);
    }
    return u / memory_suggestion.size();
  }
  double utilization_d(const memory_suggestion_t& memory_suggestion) {
    double u = 0;
    for (const auto& p : memory_suggestion) {
      u += p.first->speed_utilization_rate_d(p.second);
    }
    return u / memory_suggestion.size();
  }
  size_t get_total_extra_memory(const Stat& st) {
    size_t total_extra_memory;
    if (resize_strategy == ResizeStrategy::ignore) {
      total_extra_memory = st.e;
    } else if (resize_strategy == ResizeStrategy::gradient) {
      total_extra_memory =
        positive_binary_search_unbounded(std::max<size_t>(st.e, 1),
                                         [&](double extra_memory) {
                                           double mu = utilization_d(calculate_suggestion(extra_memory, st));
                                           return compare(-gc_rate_d, -mu);
                                         });
    }
    else {
      std::cout << "resize_strategy " << resize_strategy << " not implemented!" << std::endl;
      throw;
    }
    assert(total_extra_memory <= 1e30);
    return total_extra_memory;
  }
  // pavel: check if this fp is safe?
  void balance() {
    ++epoch;
    last_balance = steady_clock::now();
    std::vector<double> scores;
    std::vector<ConnectionState*> vec = vector();
    for (ConnectionState* rr: vec) {
      if (rr->should_balance()) {
        scores.push_back(rr->duration_score());
      }
    }
    std::sort(scores.begin(), scores.end());
    if (!scores.empty()) {
      Stat st = get_stat(scores);
      size_t total_extra_memory = get_total_extra_memory(st);
      auto suggested_extra_memory_aux =
        [&](ConnectionState* rr) -> size_t {
          return suggested_extra_memory(rr, total_extra_memory, st);
        };

      if (balance_strategy != BalanceStrategy::ignore) {
        // send msg back to v8
        for (ConnectionState* rr: vec) {
          if (rr->should_balance()) {
            size_t extra_memory_ = rr->extra_memory();
            size_t suggested_extra_memory_ = suggested_extra_memory_aux(rr);
            suggested_extra_memory_ = std::max<size_t>(suggested_extra_memory_, extra_memory_floor);
            size_t total_memory_ = std::max<size_t>(suggested_extra_memory_ + rr->working_memory, total_memory_floor);
            std::string str = to_string(tagged_json("heap", total_memory_));
            if (!send_string(rr->fd, str)) {
              // todo: actually close the connection. right now i am hoping the poll code will close it.
            } else {
              rr->max_memory = total_memory_;
              assert(rr->max_memory >= rr->working_memory);
              nlohmann::json j;
              j["name"] = rr->name;
              j["working-memory"] = rr->working_memory;
              j["max-memory"] = total_memory_;
              j["time"] = (steady_clock::now() - program_begin).count();
            }
          }
        }
      }
    }
  }
};

void poll_daemon(const std::vector<char*>& args) {
  Balancer(args).poll_daemon();
}
