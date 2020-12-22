namespace tag = boost::accumulators::tag;
using boost::accumulators::accumulator_set;
using boost::accumulators::stats;

std::string get_time() {
  std::time_t t = std::time(nullptr);
  std::tm* tm = std::localtime(&t);
  return
    std::to_string(1900+tm->tm_year) + "-" +
    std::to_string(1+tm->tm_mon) + "-" +
    std::to_string(tm->tm_mday) + "-" +
    std::to_string(tm->tm_hour) + "-" +
    std::to_string(tm->tm_min) + "-" +
    std::to_string(tm->tm_sec);
}

double mean(const std::vector<double>& v) {
  accumulator_set<double, stats<tag::variance>> acc;
  for (double d: v) {
    acc(d);
  }
  return boost::accumulators::extract::mean(acc);
}

double sd(const std::vector<double>& v) {
  accumulator_set<double, stats<tag::variance>> acc;
  for (double d: v) {
    acc(d);
  }
  return sqrt(boost::accumulators::extract::variance(acc));
}

double normality(const std::vector<double>& v) {
  return boost::math::statistics::anderson_darling_normality_statistic(v);
}

v8::Local<v8::String> fromFile(v8::Isolate* isolate, const std::string& path) {
  std::ifstream t(path);
  std::string str((std::istreambuf_iterator<char>(t)),
                  std::istreambuf_iterator<char>());
  return v8::String::NewFromUtf8(isolate, str.data()).ToLocalChecked();
}

constexpr size_t min_heap_size = 2359296;
constexpr size_t max_heap_size = 4e9; // Beyond 4gb ConfigureDefaults start acting funny.

size_t random_heap_size() {
  static std::random_device rd;
  static std::mt19937 gen(rd());
  static std::uniform_real_distribution<> dist(log(min_heap_size), log(max_heap_size));
  return exp(dist(rd));
}
