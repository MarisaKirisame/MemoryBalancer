#pragma once
#include <v8.h>
#include <v8-json.h>

#ifdef USE_V8
#include "v8_util.hpp"
#endif

std::string get_time();

double mean(const std::vector<double>& v);

double sd(const std::vector<double>& v);

double normality(const std::vector<double>& v);

constexpr size_t min_heap_size = 2359296;
constexpr size_t max_heap_size = 4e9; // Beyond 4gb ConfigureDefaults start acting funny.

size_t random_heap_size();

double median(const std::vector<double>& vec);

std::pair<std::vector<std::string>, std::string> split_string(const std::string& str);
