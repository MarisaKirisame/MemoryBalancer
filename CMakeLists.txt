cmake_minimum_required(VERSION 3.10)

# set the project name
project(MemoryBalancer)

# add the executable
add_executable(MemoryBalancer main.cpp)

set(CMAKE_CXX_STANDARD_REQUIRED True)
set(CMAKE_CXX_STANDARD 17)
# somehow this does not work. add flag manually
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -std=c++17")

target_link_libraries(MemoryBalancer PRIVATE v8_monolith)
target_link_directories(MemoryBalancer PRIVATE ../v8/out.gn/x64.release.sample/obj/)

set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -pthread -DV8_COMPRESS_POINTERS")

set(JSON_BuildTests OFF CACHE INTERNAL "")
add_subdirectory(third_party/json)
target_link_libraries(MemoryBalancer PRIVATE nlohmann_json::nlohmann_json)

include_directories(../v8/include)
