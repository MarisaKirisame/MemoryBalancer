// Copyright 2015 the V8 project authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// todo: deal with copyright

#include "util.hpp"
#include "controller.hpp"
#include "runtime.hpp"
#include "simulator.hpp"
#include "boost/filesystem.hpp"
#include "v8_eval.hpp"

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
#include <cxxopts.hpp>

#include <sys/types.h>
#include <sys/socket.h>
#include <sys/un.h>

#include "v8_util.hpp"

#define ERROR_STREAM std::cout << __LINE__ << " "

// todo: move to right places
using RemoteRuntime = std::shared_ptr<RemoteRuntimeNode>;

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

void balance(const std::vector<RemoteRuntime>& vec) {
  std::vector<double> scores;
  for (const RemoteRuntime& rr: vec) {
    if (rr->ready_) {
      scores.push_back(rr->memory_score());
    }
  }
  std::cout << "balancing " << scores.size() << " heap, waiting for " << vec.size() - scores.size() << " heap" << std::endl;
  if (!scores.empty()) {
    std::sort(scores.begin(), scores.end());
    double median_score = median(scores);
    for (const RemoteRuntime& rr: vec) {
      if (rr->ready_) {
        if (rr->memory_score() > median_score) {
          char buf[] = "GC";
          if (send(rr->sockfd, buf, sizeof buf, 0) != sizeof buf) {
            ERROR_STREAM << strerror(errno) << std::endl;
            throw;
          }
        }
      }
    }
  }
}

struct ConnectionState {
  socket_t fd;
  ConnectionState(socket_t fd) : fd(fd) { }
  std::string unprocessed;
  size_t working_memory;
  size_t max_memory;
  size_t gc_duration;
  double garbage_rate;
  bool has_major_gc = false;
  bool has_allocation_rate = false;
  void accept(const std::string& str) {
    unprocessed += str;
    auto p = split_string(unprocessed);
    for (const auto& str: p.first) {
      std::istringstream iss(str);
      json j;
      iss >> j;
      json type = j["type"];
      json data = j["data"];
      if (type == "major_gc") {
        has_major_gc = true;
        max_memory = data["max_memory"];
        gc_duration = static_cast<double>(data["after_time"]) - static_cast<double>(data["before_time"]);
        working_memory = data["after_memory"];
      } else if (type == "allocation_rate") {
        has_allocation_rate = true;
        garbage_rate = data;
      } else if (type == "max_memory") {
        max_memory = data;
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
    return max_memory - working_memory;
  }
  double gt() {
    return static_cast<double>(garbage_rate) * static_cast<double>(gc_duration);
  }
  double score() {
    assert(ready());
    size_t extra_memory_ = extra_memory();
    return static_cast<double>(extra_memory_) * static_cast<double>(extra_memory_) / gt();
  }
  void report() {
    assert(ready());
    std::cout
      << "extra_memory: " << extra_memory()
      << ", garbage_rate: " << garbage_rate
      << ", gc_duration: " << gc_duration
      << ", score: " << score() << std::endl;
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
              map.insert({newsocket, ConnectionState(newsocket)});
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
                map.at(pfds[i].fd).accept(std::string(buf, n));
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
        size_t e = 0;
        double gt_e = 0;
        double gt_root = 0;

        for (ConnectionState* rr: vec) {
          if (rr->ready()) {
            double diff = (rr->score() - median_score) / median_score;
            mse += diff * diff;
            e += rr->extra_memory();
            gt_e += rr->gt() / rr->extra_memory();
            gt_root += sqrt(rr->gt());
          }
        }
        mse /= scores.size();

        // pavel: check if this fp is safe?
        auto suggest_extra_memory = [&](ConnectionState* rr) -> size_t {
                                      if (gt_root == 0) {
                                        return 0;
                                      } else {
                                        return e / gt_root * sqrt(rr->gt());
                                      }
                                    };
        if (report) {
          for (ConnectionState* rr: vec) {
            if (rr->ready()) {
              rr->report();
              std::cout << "suggested memory:" << suggest_extra_memory(rr) << std::endl;
            }
          }
          std::cout << "score mse: " << mse << std::endl;
          std::cout << "total extra memory: " << e << std::endl;
          std::cout << "efficiency: " << gt_e << " " << gt_root << " " << gt_e * e / gt_root / gt_root << std::endl;
          std::cout << std::endl;
        }

        // send msg back to v8
        for (ConnectionState* rr: vec) {
          if (rr->ready()) {
            size_t suggested_extra_memory_ = suggest_extra_memory(rr);
            if (abs((suggested_extra_memory_ - rr->extra_memory()) / static_cast<double>(rr->extra_memory())) > tolerance) {
              std::string msg = std::to_string(suggested_extra_memory_ + rr->working_memory);
              if (send(rr->fd, msg.c_str(), msg.size(), 0) != msg.size()) {
                ERROR_STREAM << strerror(errno) << std::endl;
                throw;
              }
            }
          }
        }
      }
    }
  }
};

int main(int argc, char* argv[]) {
  assert(argc == 2);
  V8RAII v8(argv[0]);
  std::string command(argv[1]);
  if (command == "daemon") {
    Balancer().poll_daemon();
  } else if (command == "v8_experiment") {
    v8_experiment();
  } else if (command == "pareto_curve") {
    pareto_curve("../gc_log");
  } else {
    std::cout << "unknown command: " << command << std::endl;
  }
  return 0;
}
