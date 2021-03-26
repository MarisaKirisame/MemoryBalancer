cmake_minimum_required(VERSION 3.10)

# set the project name
project(MemoryBalancer)

option(USE_V8 "Use V8" OFF)

# add the executable
file(GLOB_RECURSE SOURCES src/*.hpp src/*.cpp)
add_executable(MemoryBalancer ${SOURCES})

set(CMAKE_CXX_STANDARD_REQUIRED True)
set(CMAKE_CXX_STANDARD 17)
# somehow this does not work. add flag manually
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -std=c++17")

set(JSON_BuildTests OFF CACHE INTERNAL "")

#add_subdirectory(third_party/json)
#include_directories(third_party/json/include)
#target_link_libraries(MemoryBalancer PRIVATE nlohmann_json::nlohmann_json)

target_link_libraries(MemoryBalancer PRIVATE boost_filesystem)

# the project must need v8 as header to build. we dont necessarily need to link it, unless we want simulator.
include_directories(../v8/src/include)
if (USE_V8)
  target_link_libraries(MemoryBalancer PRIVATE v8_monolith)
  target_link_directories(MemoryBalancer PRIVATE ../v8/src/out.gn/x64.release.sample/obj/)
  set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -pthread -DV8_COMPRESS_POINTERS")
  add_custom_command(
    TARGET MemoryBalancer
    PRE_BUILD
    COMMAND sh ../scripts/compile_v8.sh
    )
  target_compile_definitions(MemoryBalancer PUBLIC USE_V8)
else()
endif ()
