#pragma once

#include <unordered_map>
#include <libsocket/unixserverstream.hpp>
#include <vector>
// RN, lets specialize everything to the unix socket stream. lets generalize later.
// accept may interchange connection from multiple socket,
// so we cannot simply take a bunch of consecutive accpet and assume they come from the same thread.
// instead, to connect to multiacceptor, you have to accept() and send a line containing your pid.
// MultiAcceptor will then group the pid and return them in batch.
struct MultiAcceptor {
  size_t num_connections;
  std::unordered_map<int, std::vector<int>> hm;
  int server;
  libsocket::unix_stream_server srv;
  std::vector<int> accept() {
    
  }
};

// A server. It manage a controller, listen to incoming new connection, wrap them as RemoteRuntime and insert them into the controller.
// Additionally, if it is a simulated environment, the Server will have to manage stepping as well.
struct Server {
};
