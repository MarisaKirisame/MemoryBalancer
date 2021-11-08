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

void send_balancer_message(int fd, const nlohmann::json& j) {
  std::stringstream ssr;
  ssr << j << std::endl;
  std::string msg = ssr.str();
  if (send(fd, msg.c_str(), msg.size(), 0) != msg.size()) {
    ERROR_STREAM << strerror(errno) << std::endl;
    throw;
  }
}

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
        sum *= item_count_max;
        sum /= item_count;
        --item_count;
      }
      return sum / item_count;
    }
  };
  return [=](){ return SA(item_count_max); };
}

filter_factory_t smooth_exact(size_t item_count_max) {
  assert(item_count_max > 0);
  struct SA {
    size_t item_count_max;
    std::queue<double> items;
    double sum = 0;
    SA(size_t item_count_max) : item_count_max(item_count_max) { }
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
  return [=](){ return SA(item_count_max); };
}

struct ConnectionState {
  socket_t fd;
  std::string unprocessed;
  Filter<size_t> working_memory;
  Filter<size_t> max_memory;
  Filter<size_t> gc_duration;
  Filter<double> garbage_rate;
  size_t last_major_gc_epoch;
  time_point last_major_gc;
  std::string name;
  bool has_major_gc = false;
  bool has_allocation_rate = false;
  ConnectionState(socket_t fd, const filter_factory_t& ff) :
    fd(fd), working_memory(ff()), max_memory(ff()), gc_duration(ff()), garbage_rate(ff()) { }
  void accept(const std::string& str, size_t epoch) {
    unprocessed += str;
    auto p = split_string(unprocessed);
    for (const auto& str: p.first) {
      std::istringstream iss(str);
      json j;
      iss >> j;
      json type = j["type"];
      json data = j["data"];
      if (type == "major_gc") {
        if (!has_major_gc) {
          name = data["name"];
        } else {
          assert(name == data["name"]);
        }
        last_major_gc = steady_clock::now();
        last_major_gc_epoch = epoch;
        has_major_gc = true;
        max_memory.in(data["max_memory"]);
        gc_duration.in(static_cast<double>(data["after_time"]) - static_cast<double>(data["before_time"]));
        working_memory.in(data["after_memory"]);
      } else if (type == "allocation_rate") {
        has_allocation_rate = true;
        garbage_rate.in(data);
      } else if (type == "max_memory") {
        max_memory.in(data);
      } else {
        std::cout << "unknown type: " << type << std::endl;
        throw;
      }
    }
    unprocessed = p.second;
  }
  bool ready() {
    return has_major_gc && has_allocation_rate;
  }
  size_t extra_memory() {
    return max_memory.out() - working_memory.out();
  }
  double gt() {
    return static_cast<double>(garbage_rate.out()) * static_cast<double>(gc_duration.out());
  }
  double score() {
    assert(ready());
    size_t extra_memory_ = extra_memory();
    return static_cast<double>(extra_memory_) * static_cast<double>(extra_memory_) / gt();
  }
  void report(TextTable& t, size_t epoch) {
    assert(ready());
    t.add(name);
    t.add(std::to_string(extra_memory()));
    t.add(std::to_string(garbage_rate.out()));
    t.add(std::to_string(gc_duration.out()));
    t.add(std::to_string(epoch - last_major_gc_epoch));
    t.add(std::to_string(score()));
  }
};

struct Balancer {
  static constexpr auto balance_frequency = milliseconds(1000);
  size_t update_count = 0;
  socket_t s = get_listener();
  std::vector<pollfd> pfds {{s, POLLIN}};
  std::unordered_map<socket_t, ConnectionState> map;
  time_point last_balance = steady_clock::now();
  bool report = true;
  double tolerance = 0.1;
  bool send_msg;
  size_t epoch = 0;
  filter_factory_t ff;
  Balancer(const std::vector<char*>& args) {
    // note: we intentionally do not use any default option.
    // as all options is filled in by the eval program, there is no point in having default,
    // and it will hide error.
    cxxopts::Options options("Balancer", "Balance multiple v8 heap");
    options.add_options()
      ("send-msg", "Send actual balancing message", cxxopts::value<bool>());
    options.add_options()
      ("smooth-type", "no-smoothing, smooth-approximate, smooth-exact", cxxopts::value<std::string>());
    options.add_options()
      ("smooth-count", "a positive number. the bigger it is, the more smoothing we do", cxxopts::value<size_t>());
    auto result = options.parse(args.size(), args.data());
    send_msg = result["send-msg"].as<bool>();
    std::string smooth_type = result["smooth-type"].as<std::string>();
    if (smooth_type == "no-smoothing") {
      ff = id_ff;
    } else if (smooth_type == "smooth-approximate") {
      assert(result.count("smooth-count"));
      ff = smooth_approximate(result["smooth-count"].as<size_t>());
    } else if (smooth_type == "smooth-exact") {
      assert(result.count("smooth-count"));
      ff = smooth_exact(result["smooth-count"].as<size_t>());
    } else {
      std::cout << "unknown smooth-type: " << smooth_type;
      throw;
    }
  }
  void poll_daemon() {
    while (true) {
      int num_events = poll(pfds.data(), pfds.size(), 1000 /*miliseconds*/);
      if (num_events != 0) {
        auto close_connection = [&](size_t i) {
                                  std::cout << "peer closed!" << std::endl;
                                  close(pfds[i].fd);
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
                map.at(pfds[i].fd).accept(std::string(buf, n), epoch);
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
    std::cout << "balancing " << scores.size() << " heap, waiting for " << vec.size() - scores.size() << " heap" << std::endl;
    std::sort(scores.begin(), scores.end());
    if (!scores.empty()) {
      double median_score = median(scores);
      std::cout << "median_score: " << median_score << std::endl;
      if (!scores.empty()) {
        // stats calculation
        double mse = 0;
        size_t m = 0;
        size_t e = 0;
        double gt_e = 0;
        double gt_root = 0;

        for (ConnectionState* rr: vec) {
          if (rr->ready()) {
            double diff = (rr->score() - median_score) / median_score;
            mse += diff * diff;
            m += rr->max_memory.out();
            e += rr->extra_memory();
            gt_e += rr->gt() / rr->extra_memory();
            gt_root += sqrt(rr->gt());
          }
        }
        mse /= scores.size();

        // pavel: check if this fp is safe?
        auto suggested_extra_memory = [&](ConnectionState* rr) -> size_t {
                                      if (gt_root == 0) {
                                        return 0;
                                      } else {
                                        return e / gt_root * sqrt(rr->gt());
                                      }
                                    };

        if (report) {
          TextTable t( '-', '|', '+' );
          t.add("name");
          t.add("extra_memory");
          t.add("garbage_rate");
          t.add("gc_duration");
          t.add("epoch_since_gc");
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
          std::cout << "efficiency: " << gt_e << " " << gt_root << " " << gt_e * e / gt_root / gt_root << std::endl;
          std::cout << std::endl;
        }

        if (send_msg) {
          // send msg back to v8
          for (ConnectionState* rr: vec) {
            if (rr->ready()) {
              size_t suggested_extra_memory_ = suggested_extra_memory(rr);
              size_t total_memory = suggested_extra_memory_ + rr->working_memory.out();
              if (abs((suggested_extra_memory_ - rr->extra_memory()) / static_cast<double>(rr->extra_memory())) > tolerance) {
                send_balancer_message(rr->fd, tagged_json("heap", total_memory));
              }
              // calculate a gc period, and if a gc hasnt happend in twice of that period, it mean the gc message is stale.
              bool unexpected_no_gc = 2 * rr->extra_memory() / rr->garbage_rate.out() < (steady_clock::now() - rr->last_major_gc).count();
              if (unexpected_no_gc && epoch - rr->last_major_gc_epoch > 3) {
                send_balancer_message(rr->fd, tagged_json("gc", ""));
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
