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

bool send_string(socket_t s, const std::string& msg) {
  if (::send(s, msg.c_str(), msg.size(), MSG_NOSIGNAL) != msg.size()) {
    ERROR_STREAM << strerror(errno) << std::endl;
    return false;
  }
  return true;
}

time_point program_begin = steady_clock::now();

using ByteDiffsAndDuration = std::pair<int64_t, double>;

// all duration is in milliseconds, and all speed is in bytes per milliseconds.
struct ConnectionState {
  size_t wait_ack_count = 0;
  socket_t fd;
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
    for (size_t i = 0; i < aabad.size(); ++i) {
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
    for (size_t i = 0; i < gc_bad.size(); ++i) {
      const auto& bad = gc_bad[i];
      ret += bad.second;
      ret *= gc_speed_smoothing_per_sample;
    }
    return ret;
  }
  double average_gc_duration() {
    return gc_duration() / gc_bad.size();
  }
  double gc_bytes() {
    double ret = 0;
    for (size_t i = 0; i < gc_bad.size(); ++i) {
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
  ConnectionState(socket_t fd) : fd(fd) { }
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
  ResizeStrategy resize_strategy;
  double gc_rate_d;
  size_t epoch = 0;
  Balancer(const std::vector<char*>& args) {
    // note: we intentionally do not use any default option.
    // as all options is filled in by the eval program, there is no point in having default,
    // and it will hide error.
    cxxopts::Options options("Balancer", "Balance multiple v8 heap");
    options.add_options()
      ("resize-strategy", "ignore, before-balance, after-balance", cxxopts::value<std::string>());
    options.add_options()
      ("balance-frequency", "milliseconds between balance", cxxopts::value<size_t>());
    auto result = options.parse(args.size(), args.data());
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
  void balance() {
    ++epoch;
    last_balance = steady_clock::now();
    std::vector<ConnectionState*> vec = vector();
    if (resize_strategy != ResizeStrategy::ignore) {
      // send msg back to v8
      for (ConnectionState* rr: vec) {
        if (rr->should_balance()) {
          size_t extra_memory_ = rr->extra_memory();
          size_t suggested_extra_memory_ = sqrt(static_cast<double>(rr->garbage_rate()) *
                                                static_cast<double>(rr->working_memory + bias_in_working_memory) /
                                                static_cast<double>(rr->gc_speed()) /
                                                (- gc_rate_d));
          suggested_extra_memory_ = std::max<size_t>(suggested_extra_memory_, extra_memory_floor);
          size_t total_memory_ = std::max<size_t>(suggested_extra_memory_ + rr->working_memory, total_memory_floor);
          std::string str = to_string(tagged_json("heap", total_memory_));
          if (!send_string(rr->fd, str)) {
            // todo: actually close the connection. right now i am hoping the poll code will close it.
          } else {
            rr->max_memory = total_memory_;
            assert(rr->max_memory >= rr->working_memory);
          }
        }
      }
    }
  }
};

void poll_daemon(const std::vector<char*>& args) {
  Balancer(args).poll_daemon();
}
