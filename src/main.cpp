// Copyright 2015 the V8 project authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// todo: deal with copyright

#include "util.hpp"
#include "controller.hpp"
#include "runtime.hpp"
#include "v8_eval.hpp"
#include "v8_util.hpp"
#include "macro.hpp"
#include "acdc.hpp"

#include <cxxopts.hpp>

int main(int argc, char* argv[]) {
  assert(argc >= 2);
  V8RAII v8(argv[0]);
  std::string command(argv[1]);
  std::vector<char*> command_args{argv[0]};
  std::cout<<argc<<std::endl;

  for (size_t i = 2; i < argc; ++i) {
    std::cout<<argv[i]<<std::endl;
    command_args.push_back(argv[i]);
  }
  if (command == "v8_experiment") {
    v8_experiment(v8.platform.get(), command_args);
  } else if (command == "macro") {
    macro();
  } else if (command == "acdc") {
    acdc(v8.platform.get(), command_args);
  } else {
    std::cout << "unknown command: " << command << std::endl;
  }
  return 0;
}
