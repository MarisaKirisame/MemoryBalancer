cmake_minimum_required(VERSION 3.10)

# set the project name
project(MemoryBalancer)

# add the executable
file(GLOB_RECURSE SOURCES src/*.hpp src/*.cpp)
add_executable(MemoryBalancer ${SOURCES})

set(CMAKE_CXX_STANDARD_REQUIRED True)
set(CMAKE_CXX_STANDARD 17)
# somehow this does not work. add flag manually
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -std=c++17 -L /usr/local/Cellar/boost/1.75.0_2/lib -g -DV8_COMPRESS_POINTERS")

include_directories(/usr/local/Cellar/boost/1.75.0_2/include)
include_directories(/Users/pavpan/Dropbox/Work/MemoryBalancer/third_party/json/nlohmann/include)
include_directories(third_party/cxxopts/include)
include_directories(third_party/cpp-text-table)

target_link_libraries(MemoryBalancer PRIVATE pthread)
target_link_libraries(MemoryBalancer PRIVATE boost_system)
target_link_libraries(MemoryBalancer PRIVATE boost_filesystem)
target_link_libraries(MemoryBalancer PRIVATE stdc++fs)

target_link_libraries(MemoryBalancer PRIVATE v8_monolith)
target_link_directories(MemoryBalancer PRIVATE ../v8/src/out.gn/x64.release.sample/obj/)
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -pthread -Wl,--no-as-needed -ldl")

set(JSON_BuildTests OFF CACHE INTERNAL "")
add_subdirectory(third_party/json)
target_link_libraries(MemoryBalancer PRIVATE nlohmann_json::nlohmann_json)

# the project must need v8 as header to build. we dont necessarily need to link it, unless we want simulator.
include_directories(../v8/src/include)
include_directories(/Users/pavpan/src/v8/src/include)
