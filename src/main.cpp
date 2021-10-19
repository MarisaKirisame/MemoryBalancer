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

#include <sys/types.h>
#include <sys/socket.h>
#include <sys/un.h>

#ifdef USE_V8
#include "v8_util.hpp"
#endif

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
  std::string unprocessed;
  void accept(const std::string& str) {
    unprocessed += str;
    auto p = split_string(unprocessed);
    for (const auto& str: p.first) {
      //std::cout << str << std::endl;
      //std::istringstream iss(str);
      //json j;
      //iss >> j;
      //v8::GCRecord rec = j.get<v8::GCRecord>();
      //++update_count;
    }
    unprocessed = p.second;
  }
};

constexpr auto balance_frequency = milliseconds(10000);
void poll_daemon() {
  size_t update_count = 0;
  socket_t s = get_listener();
  std::vector<pollfd> pfds;
  std::unordered_map<socket_t, ConnectionState> map;
  auto last_balance = steady_clock::now();
  pfds.push_back({s, POLLIN});
  while (true) {
    int num_events = poll(pfds.data(), pfds.size(), 1000 /*miliseconds*/);
    if (num_events != 0) {
      std::cout << pfds.size() << " " << map.size() << std::endl;
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
            map.insert({newsocket, ConnectionState()});
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
              std::cout << "get message!" << std::endl;
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
      //last_balance = steady_clock::now();
      //std::vector<RemoteRuntime> vec;
      //for (const auto& p : map) {
      //  vec.push_back(p.second);
      //}
      //balance(vec);
    }
  }
}

int main(int argc, char* argv[]) {
  if (false) {
    pareto_curve("../gc_log");
  }
  assert(argc == 1);
  V8RAII v8(argv[0]);
  v8_experiment();
  //poll_daemon();
  return 0;
  /*#if USE_V8
  ipc_experiment();
#else
  pareto_curve("../gc_log");
#endif
return 0;*/
}
