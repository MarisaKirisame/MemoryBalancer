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

namespace nlohmann {

	template <class T>
	void to_json(nlohmann::json& j, const std::optional<T>& v)
	{
		if (v.has_value()) {
			j["tag"] = "Some";
      j["value"] = *v;
    }
		else {
      j["tag"] = "None";
    }
	}

	template <class T>
	void from_json(const nlohmann::json& j, std::optional<T>& v)
	{
		if (j["tag"] == "Some") {
      j.at("value").get_to(*v);
    } else {
      v = std::nullopt;
    }
	}
} // namespace nlohmann

using namespace nlohmann;

void log_json(const json& j, const std::string& type);

using time_point = std::chrono::steady_clock::time_point;
using std::chrono::steady_clock;
using std::chrono::duration_cast;
using milliseconds = std::chrono::milliseconds;

inline std::string read_file(const std::string& path) {
  assert(std::filesystem::exists(path));
  std::ifstream t(path);
  return std::string((std::istreambuf_iterator<char>(t)),
                     std::istreambuf_iterator<char>());
}
