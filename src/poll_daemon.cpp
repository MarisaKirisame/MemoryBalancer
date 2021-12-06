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

#include <cxxopts.hpp>

#define ERROR_STREAM std::cout << __LINE__ << " "

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

inline nlohmann::json tagged_json(const std::string& type, const nlohmann::json& data) {
  nlohmann::json ret;
  ret["type"] = type;
  ret["data"] = data;
  return ret;
}

std::string to_string(const nlohmann::json& j) {
  std::stringstream ssr;
  ssr << j << std::endl;
  return ssr.str();
};

template<typename T>
struct Filter {
  // a possibly stateful function. transform the input.
  const std::function<double(double)> func;
  bool recieved_signal = false;
  double output;
  void in(const T& t) {
    recieved_signal = true;
    output = func(static_cast<double>(t));
  }
  T out() {
    assert(recieved_signal);
    return static_cast<T>(output);
  }
  T io(const T& t) {
    in(t);
    return out();
  }
  Filter(const std::function<double(double)>& func) : func(func) { }
  Filter() = delete;
  // we intentionally do not provide the more natural = overloading and implicit cast.
  // it is because a filter *is not* the thing it is filtering.
  // suppose we have Filter a, Filter b,
  // a = b can mean both things, which is useful under different circumstances:
  // 0: assign the state of filter a to that of filter b
  // 1: feed 1 value from b into a
  // by not providing the short cut, the distinction is made explicit, and the ambiguity is resolved.
};

using filter_factory_t = std::function<std::function<double(double)>()>;
filter_factory_t id_ff =
                    [](){
                      return [](double d){return d;};
                    };

filter_factory_t smooth_approximate(size_t item_count_max) {
  assert(item_count_max > 0);
  struct SA {
    size_t item_count_max;
    size_t item_count = 0;
    double sum = 0;
    SA(size_t item_count_max) : item_count_max(item_count_max) { }
    double operator()(double d) {
      ++item_count;
      sum += d;
      if (item_count > item_count_max) {
        assert(item_count == item_count_max + 1);
        sum -= sum / item_count;
        --item_count;
      }
      return sum / item_count;
    }
  };
  return [=](){ return SA(item_count_max); };
}

filter_factory_t smooth_exact(size_t item_count_max) {
  assert(item_count_max > 0);
  struct SE {
    size_t item_count_max;
    std::queue<double> items;
    double sum = 0;
    SE(size_t item_count_max) : item_count_max(item_count_max) { }
    double operator()(double d) {
      items.push(d);
      sum += d;
      if (items.size() > item_count_max) {
        assert(items.size() == item_count_max + 1);
        sum -= items.front();
        items.pop();
      }
      return sum / items.size();
    }
  };
  return [=](){ return SE(item_count_max); };
}

filter_factory_t smooth_window_approximate(size_t duration_in_milliseconds) {
  assert(duration_in_milliseconds > 0);
  struct SWA {
    size_t duration_in_milliseconds;
    SWA(size_t duration_in_milliseconds) : duration_in_milliseconds(duration_in_milliseconds) { }
    std::queue<time_point> items;
    double sum = 0;
    double operator()(double d) {
      time_point t = steady_clock::now();
      items.push(t);
      sum += d;
      while ((t - items.front()).count() > duration_in_milliseconds) {
        sum -= sum / items.size();
        items.pop();
        assert(!items.empty());
      }
      return sum / items.size();
    }
  };
  return [=](){ return SWA(duration_in_milliseconds); };
}

filter_factory_t smooth_tucker(double param) {
  assert(param > 0);
  struct ST {
    double param;
    ST(double param) : param(param) { }
    double sum = 0;
    time_point last_time_point;
    bool has_element = false;
    double operator()(double d) {
      time_point t = steady_clock::now();
      if (has_element) {
        double weight = exp(-param * (t - last_time_point).count());
        sum = d * (1 - weight) + sum * weight;
      } else {
        sum += d;
      }
      has_element = true;
      last_time_point = t;
      return sum;
    }
  };
  return [=](){ return ST(param); };
}

void send_string(socket_t s, const std::string& msg) {
  if (::send(s, msg.c_str(), msg.size(), 0) != msg.size()) {
    ERROR_STREAM << strerror(errno) << std::endl;
    throw;
  }
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

struct Logger {
  std::ofstream f;
  void log(const nlohmann::json& j) {
    if (f.is_open()) {
      f << j << std::endl;
    }
  }
};

struct ConnectionState {
  size_t wait_ack_count = 0;
  socket_t fd;
  IdChannel force_gc_chan;
  Snapper heap_resize_snap;
  std::string unprocessed;
  Filter<size_t> working_memory;
  // real max memory is for efficiency calculation purpose only
  Filter<size_t> max_memory, real_max_memory;
  Filter<size_t> gc_duration;
  Filter<size_t> size_of_objects;
  Filter<double> gc_speed;
  Filter<double> garbage_rate;
  size_t last_major_gc_epoch;
  time_point last_major_gc;
  std::string name;
  bool has_major_gc = false;
  bool has_allocation_rate = false;
  ConnectionState(socket_t fd, const filter_factory_t& ff) :
    fd(fd),
    force_gc_chan(fd),
    working_memory(ff()),
    max_memory(ff()),
    real_max_memory(ff()),
    gc_duration(ff()),
    size_of_objects(ff()),
    gc_speed(ff()),
    garbage_rate(ff()) { }
  void try_log(Logger& l, const std::string& msg_type) {
    if (ready()) {
      nlohmann::json j;
      j["msg-type"] = msg_type;
      j["time"] = (steady_clock::now() - program_begin).count();
      j["working-memory"] = working_memory.out();
      j["max-memory"] = max_memory.out();
      j["gc-duration"] = gc_duration.out();
      j["gc-speed"] = gc_speed.out();
      j["garbage-rate"] = garbage_rate.out();
      j["name"] = name;
      l.log(tagged_json("heap-stat", j));
    }
  }
  void accept(const std::string& str, size_t epoch, Logger& l) {
    unprocessed += str;
    auto p = split_string(unprocessed);
    for (const auto& str: p.first) {
      std::istringstream iss(str);
      json j;
      iss >> j;
      json type = j["type"];
      json data = j["data"];
      if (type == "major_gc") {
        if (wait_ack_count == 0) {
          if (!has_major_gc) {
            name = data["name"];
          } else {
            assert(name == data["name"]);
          }
          last_major_gc = steady_clock::now();
          last_major_gc_epoch = epoch;
          has_major_gc = true;
          max_memory.in(data["max_memory"]);
          real_max_memory.in(data["max_memory"]);
          gc_duration.in(static_cast<double>(data["after_time"]) - static_cast<double>(data["before_time"]));
          size_of_objects.in(data["size_of_objects"]);
          gc_speed.in(data["gc_speed"]);
          working_memory.in(data["after_memory"]);
          has_allocation_rate = true;
          garbage_rate.in(data["allocation_rate"]);
        }
      } else if (type == "allocation_rate") {
        has_allocation_rate = true;
        garbage_rate.in(data);
      } else if (type == "max_memory") {
        if (wait_ack_count == 0) {
          max_memory.in(data);
        }
      } else if (type == "ack") {
        assert(wait_ack_count > 0);
        --wait_ack_count;
      } else {
        std::cout << "unknown type: " << type << std::endl;
        throw;
      }
      try_log(l, type);
    }
    unprocessed = p.second;
  }
  bool ready() {
    return has_major_gc && has_allocation_rate;
  }
  size_t extra_memory() {
    return max_memory.out() - working_memory.out();
  }
  size_t real_extra_memory() {
    return real_max_memory.out() - working_memory.out();
  }
  double gt() {
    return static_cast<double>(garbage_rate.out()) * static_cast<double>(gc_duration.out());
  }
  double score() {
    assert(ready());
    size_t extra_memory_ = extra_memory();
    return static_cast<double>(extra_memory_) * static_cast<double>(extra_memory_) / gt();
  }
  size_t calculated_gc_duration() {
    return max_memory.out() / gc_speed.out();
  }
  void report(TextTable& t, size_t epoch) {
    assert(ready());
    t.add(name);
    t.add(std::to_string(extra_memory()));
    t.add(std::to_string(max_memory.out()));
    t.add(std::to_string(garbage_rate.out()));
    t.add(std::to_string(gc_speed.out()));
    t.add(std::to_string(gc_duration.out()));
    t.add(std::to_string(calculated_gc_duration()));
    t.add(std::to_string(size_of_objects.out()));
    t.add(std::to_string(score()));
  }
};

// throttle event so they dont fire too often.
struct Spacer {
  bool has_past_event = false;
  time_point last_event;
  milliseconds space;
  Spacer(milliseconds space) : space(space) { }
  bool operator()() {
    time_point now = steady_clock::now();
    if ((!has_past_event) || (now - last_event >= space)) {
      has_past_event = true;
      last_event = now;
      return true;
    } else {
      return false;
    }
  }
};

// balance memory given a limit
enum class BalanceStrategy {
  // do nothing
  ignore,
  // use the sqrt forumla
  classic,
  // give all process same amt of extra memory
  extra_memory
};

// change the sum of memory across all process
enum class ResizeStrategy {
  // do nothing
  ignore,
  // a constant amount for all process
  // is incompatible with BalanceStrategy::ignore as it does nothing and thus cannot balance the memory
  // one fix is to just scale each process uniformly but this will make late process starve
  // so - if it is a constant, use extra_memory as a base line
  constant,
  // 3% mutator rate after balancing
  before_balance,
  // 3% mutator rate after balacning
  // rn, after_balance only support classic
  after_balance
};

std::ostream& operator<<(std::ostream& os, ResizeStrategy rs) {
  if (rs == ResizeStrategy::ignore) {
    return os << "ignore";
  } else if (rs == ResizeStrategy::constant) {
    return os << "constant";
  } else if (rs == ResizeStrategy::before_balance) {
    return os << "before-balance";
  } else if (rs == ResizeStrategy::after_balance) {
    return os << "after-balance";
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
  time_point last_balance = steady_clock::now();
  bool report_ = true;
  Spacer report_spacer = Spacer(milliseconds(1000));
  Spacer log_spacer = Spacer(milliseconds(100));
  bool report() {
    return report_ && report_spacer();
  }
  double tolerance = 0.1;
  BalanceStrategy balance_strategy;
  ResizeStrategy resize_strategy;
  size_t resize_amount; // only when resize_strategy == constant
  size_t epoch = 0;
  filter_factory_t ff;
  std::string log_path;
  Logger l;
  void check_config_consistency() {
    assert(resize_strategy != ResizeStrategy::constant || balance_strategy != BalanceStrategy::ignore);
    assert(resize_strategy != ResizeStrategy::after_balance || balance_strategy == BalanceStrategy::classic);
  }
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
      ("smooth-type", "no-smoothing, smooth-approximate, smooth-exact", cxxopts::value<std::string>());
    options.add_options()
      ("smooth-count", "a positive number. the bigger it is, the more smoothing we do", cxxopts::value<size_t>());
    options.add_options()
      ("log-path", "where to put the log", cxxopts::value<std::string>());
    options.add_options()
      ("balance-frequency", "milliseconds between balance", cxxopts::value<size_t>());
    auto result = options.parse(args.size(), args.data());
    assert(result.count("balance-strategy"));
    auto balance_strategy_str = result["balance-strategy"].as<std::string>();
    if (balance_strategy_str == "ignore") {
      balance_strategy = BalanceStrategy::ignore;
    } else if (balance_strategy_str == "classic") {
      balance_strategy = BalanceStrategy::classic;
    } else if (balance_strategy_str == "extra-memory") {
      balance_strategy = BalanceStrategy::extra_memory;
    } else {
      std::cout << "UNKNOWN BALANCER TYPE: " << balance_strategy_str << std::endl;
    }
    assert(result.count("resize-strategy"));
    std::string resize_strategy_str = result["resize-strategy"].as<std::string>();
    if (resize_strategy_str == "ignore") {
      resize_strategy = ResizeStrategy::ignore;
    } else if (resize_strategy_str == "constant") {
      resize_strategy = ResizeStrategy::constant;
      assert(result.count("resize-amount"));
      resize_amount = result["resize-amount"].as<size_t>();
    } else if (resize_strategy_str == "before-balance") {
      resize_strategy = ResizeStrategy::before_balance;
    } else if (resize_strategy_str == "after-balance") {
      resize_strategy = ResizeStrategy::after_balance;
    } else {
      std::cout << "unknown resize-strategy: " << resize_strategy_str << std::endl;
    }
    std::string smooth_type = result["smooth-type"].as<std::string>();
    if (smooth_type == "no-smoothing") {
      ff = id_ff;
    } else if (smooth_type == "smooth-approximate") {
      assert(result.count("smooth-count"));
      ff = smooth_approximate(result["smooth-count"].as<size_t>());
    } else if (smooth_type == "smooth-exact") {
      assert(result.count("smooth-count"));
      ff = smooth_exact(result["smooth-count"].as<size_t>());
    } else if (smooth_type == "smooth-window-approximate") {
      assert(result.count("smooth-count"));
      ff = smooth_window_approximate(result["smooth-count"].as<size_t>());
    } else if (smooth_type == "smooth-tucker") {
      assert(result.count("smooth-count"));
      ff = smooth_tucker(1.0 / result["smooth-count"].as<size_t>());
    } else {
      std::cout << "unknown smooth-type: " << smooth_type << std::endl;
      throw;
    }
    if (result.count("log-path")) {
      log_path = result["log-path"].as<std::string>();
      l.f = std::ofstream(log_path);
    }
    balance_frequency = milliseconds(result["balance-frequency"].as<size_t>());
    check_config_consistency();
  }
  void poll_daemon() {
    while (true) {
      int num_events = poll(pfds.data(), pfds.size(), -1);
      if (num_events != 0) {
        auto close_connection = [&](size_t i) {
                                  std::cout << "peer closed!" << std::endl;
                                  close(pfds[i].fd);
                                  map.at(pfds[i].fd).max_memory.in(0);
                                  map.at(pfds[i].fd).try_log(l, "close");
                                  map.erase(pfds[i].fd);
                                  pfds[i] = pfds.back();
                                  pfds.pop_back();
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
              map.insert({newsocket, ConnectionState(newsocket, ff)});
              ++i;
            } else if (revents & POLLIN) {
              char buf[1000];
              int n = recv(fd, buf, sizeof buf, 0);
              if (n == 0) {
                close_connection(i);
              } else if (n < 0) {
                ERROR_STREAM << strerror(errno) << std::endl;
                throw;
              } else {
                map.at(pfds[i].fd).accept(std::string(buf, n), epoch, l);
                ++i;
              }
            } else {
              assert(revents & POLLHUP);
              std::cout << "close from epoll!" << std::endl;
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
  void balance() {
    ++epoch;
    bool report_this_epoch = report();
    last_balance = steady_clock::now();
    std::vector<ConnectionState*> vec;
    for (auto& p : map) {
      vec.push_back(&p.second);
    }
    std::vector<double> scores;
    for (ConnectionState* rr: vec) {
      if (rr->ready()) {
        scores.push_back(rr->score());
      }
    }
    if (report_this_epoch) {
      std::cout << "balancing " << scores.size() << " heap, waiting for " << vec.size() - scores.size() << " heap" << std::endl;
    }
    std::sort(scores.begin(), scores.end());
    if (!scores.empty()) {
      double median_score = median(scores);
      if (report_this_epoch) {
        std::cout << "median_score: " << median_score << std::endl;
      }
      if (!scores.empty()) {
        // stats calculation
        size_t instance_count = 0;
        double mse = 0;
        size_t m = 0;
        size_t e = 0;
        double gt_e = 0;
        double gt_root = 0;

        double real_e = 0;
        double real_gt_e = 0;
        for (ConnectionState* rr: vec) {
          if (rr->ready()) {
            ++instance_count;
            double diff = (rr->score() - median_score) / median_score;
            mse += diff * diff;
            m += rr->max_memory.out();
            e += rr->extra_memory();
            real_e += rr->real_extra_memory();
            gt_e += rr->gt() / rr->extra_memory();
            real_gt_e += rr->gt() / rr->real_extra_memory();
            gt_root += sqrt(rr->gt());
          }
        }
        mse /= scores.size();
        double efficiency = real_gt_e * real_e / gt_root / gt_root;

        size_t total_extra_memory;
        if (resize_strategy == ResizeStrategy::ignore) {
          total_extra_memory = e;
        } else if (resize_strategy == ResizeStrategy::constant) {
          size_t working_memory = m - e;
          total_extra_memory = resize_amount - working_memory;
        } else {
          std::cout << "resize_strategy " << resize_strategy << " not implemented!" << std::endl;
          throw;
        }

        // pavel: check if this fp is safe?
        auto suggested_extra_memory = [&](ConnectionState* rr) -> size_t {
                                        if (balance_strategy == BalanceStrategy::extra_memory) {
                                          return total_extra_memory / instance_count;
                                        } else {
                                          assert(balance_strategy == BalanceStrategy::classic || balance_strategy == BalanceStrategy::ignore);
                                          if (gt_root == 0) {
                                            return 0;
                                          } else {
                                            return total_extra_memory / gt_root * sqrt(rr->gt());
                                          }
                                        }
                                    };

        if (report_this_epoch) {
          TextTable t( '-', '|', '+' );
          t.add("name");
          t.add("extra_memory");
          t.add("total_memory");
          t.add("garbage_rate");
          t.add("gc_speed");
          t.add("gc_duration");
          t.add("calculated_gc_duration");
          t.add("size_of_objects");
          t.add("score");
          t.add("suggested_extra_memory");
          t.add("suggested_total_memory");
          t.endOfRow();
          for (ConnectionState* rr: vec) {
            if (rr->ready()) {
              rr->report(t, epoch);
              size_t suggested_extra_memory_ = suggested_extra_memory(rr);
              t.add(std::to_string(suggested_extra_memory_));
              t.add(std::to_string(suggested_extra_memory_ + rr->working_memory.out()));
              t.endOfRow();
            }
          }
          std::cout << t << std::endl;
          std::cout << "score mse: " << mse << std::endl;
          std::cout << "total memory: " << m << std::endl;
          std::cout << "total extra memory: " << e << std::endl;
          std::cout << "efficiency: " << gt_e << " " << gt_root << " " << efficiency << std::endl;
          std::cout << std::endl;
        }

        if (log_spacer()) {
          l.log(tagged_json("efficiency", efficiency));
        }

        if (balance_strategy != BalanceStrategy::ignore) {
          // send msg back to v8
          for (ConnectionState* rr: vec) {
            if (rr->ready() && rr->wait_ack_count == 0) {
              size_t extra_memory_ = rr->extra_memory();
              size_t suggested_extra_memory_ = suggested_extra_memory(rr);
              size_t total_memory_ = suggested_extra_memory_ + rr->working_memory.out();
              if (big_change(extra_memory_, suggested_extra_memory_) && rr->heap_resize_snap(suggested_extra_memory_)) {
                std::string str = to_string(tagged_json("heap", total_memory_));
                std::cout << "sending: " << str << "to: " << rr->name << std::endl;
                send_string(rr->fd, str);
                rr->max_memory.in(total_memory_);
                ++rr->wait_ack_count;
                nlohmann::json j;
                j["name"] = rr->name;
                j["working-memory"] = rr->working_memory.out();
                j["max-memory"] = total_memory_;
                j["time"] = (steady_clock::now() - program_begin).count();
                l.log(tagged_json("memory-msg", j));
              }
              // calculate a gc period, and if a gc hasnt happend in twice of that period, it mean the gc message is stale.
              bool unexpected_no_gc = std::max(2 * rr->extra_memory() / rr->garbage_rate.out(), 3000.0) < (steady_clock::now() - rr->last_major_gc).count();
              if (false && unexpected_no_gc) {
                rr->force_gc_chan.send(to_string(tagged_json("gc", "")));
              }
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
