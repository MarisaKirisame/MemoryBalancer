#pragma once

#include <string>
#include <condition_variable>
#include <iostream>

struct Input {
  size_t heap_size;
  std::string code_path;
};

/*struct Signal {
  std::mutex m;
  std::condition_variable cv;

  // this will aquire release and re-aquire the mutex.
  // maybe think of a better way to write this?
  void wait() {
  std::unique_lock<std::mutex> lk(m);
  std::cout << "waiting" << std::endl;
  cv.wait(lk);
  std::cout << "wait done" << std::endl;
  }

  void signal() {
  cv.notify_all();
  }
  };*/

struct Signal {
  std::mutex m;
  Signal() {
    m.lock();
  }

  void wait() {
    m.lock();
    m.unlock();
  }

  void signal() {
    m.unlock();
  }
};

void v8_experiment();
