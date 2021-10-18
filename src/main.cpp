// Copyright 2015 the V8 project authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// todo: deal with copyright

#include "util.hpp"
#include "controller.hpp"
#include "runtime.hpp"
#include "simulator.hpp"
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

using time_point = std::chrono::steady_clock::time_point;
using std::chrono::steady_clock;
using std::chrono::duration_cast;
using milliseconds = std::chrono::milliseconds;

struct Input {
  size_t heap_size;
  std::string code_path;
};

// todo: use the generic json-serializer/deserializerinstead
// I'd love to use the name from_json and to_json, but unfortunately it seems like the two name is used.
Input read_from_json(const json& j) {
  assert(j.count("heap_size") == 1);
  assert(j.count("code_path") == 1);
  size_t heap_size = j.value("heap_size", 0);
  std::string code_path = j.value("code_path", "");
  return Input {heap_size, code_path};
}

size_t run(const Input& i, std::mutex* m) {
#ifdef USE_V8
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
#else
  return 0;
#endif
}

void read_write() {
#ifdef USE_V8
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
#endif
}

void parallel_experiment() {
#ifdef USE_V8
  std::mutex m;
  m.lock();

  std::string octane_path = "../js/";
  Input splay_input;
  splay_input.heap_size = 0;//300*1e6;
  splay_input.code_path = octane_path + "splay.js";

  Input pdfjs_input;
  pdfjs_input.heap_size = 0;//700*1e6;
  pdfjs_input.code_path = "pdfjs.js";

  std::vector<Input> inputs;
  for (int i = 0; i < 2; ++i) {
    inputs.push_back(splay_input);
    //inputs.push_back(pdfjs_input);
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
#endif
}

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
  poll_daemon();
  return 0;
  /*#if USE_V8
  ipc_experiment();
#else
  pareto_curve("../gc_log");
#endif
return 0;*/
}
