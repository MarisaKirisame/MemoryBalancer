#include "v8_eval.hpp"
#include "util.hpp"

#include <iostream>
#include <future>
#include <vector>
#include <chrono>
#include <cxxopts.hpp>

// todo: use the generic json-serializer/deserializerinstead
// I'd love to use the name from_json and to_json, but unfortunately it seems like the two name is used.
Input read_from_json(const json& j) {
  assert(j.count("heap_size") == 1);
  assert(j.count("code_path") == 1);
  size_t heap_size = j.value("heap_size", 0);
  std::string code_path = j.value("code_path", "");
  return Input {heap_size, code_path};
}

struct V8_Result {
  size_t major_gc_time;
  size_t time;
};

V8_Result run_v8(v8::Platform* platform, const std::vector<std::pair<size_t, std::string>>& input, const std::string& name, size_t heap_size, Signal* s) {
  v8::Isolate::CreateParams create_params;
  create_params.constraints.ConfigureDefaultsFromHeapSize(0, heap_size);
  create_params.constraints.set_code_range_size_in_bytes(10 * 1048576);
  create_params.array_buffer_allocator =
    v8::ArrayBuffer::Allocator::NewDefaultAllocator();
  v8::Isolate* isolate = v8::Isolate::New(create_params);
  isolate->SetName(name);
  size_t time;
  {
    v8::Isolate::Scope isolate_scope(isolate);
    v8::HandleScope handle_scope(isolate);
    v8::Local<v8::Context> context = v8::Context::New(isolate);
    v8::Context::Scope context_scope(context);
    {
      std::string src;
      for (const auto& p: input) {
        assert(p.first == 1);
        src += p.second;
      }
      v8::Local<v8::String> source = fromString(isolate, src);
      v8::Local<v8::Script> script =
        v8::Script::Compile(context, source).ToLocalChecked();
      s->wait();
      time_point begin = steady_clock::now();
      script->Run(context);
      time_point end = steady_clock::now();
      time = duration_cast<milliseconds>(end - begin).count();
    }
  }
  auto major_gc_time = isolate->GetTotalMajorGCTime();
  isolate->StopMB();
  isolate->Dispose();
  return {major_gc_time, time};
}

struct Benchmark {
  std::string directory;
  std::string name;
  size_t repeat_time;
};

void v8_experiment(v8::Platform* platform, const std::vector<char*>& args) {
  cxxopts::Options options("V8 Experiment", "run some experiment from jetstream");
  options.add_options()
    ("heap-size", "Heap size in bytes.", cxxopts::value<int>());
  options.add_options()
    ("log-path", "path of log", cxxopts::value<std::string>());
  auto result = options.parse(args.size(), args.data());
  assert(result.count("heap-size"));
  int heap_size = result["heap-size"].as<int>();
  assert(heap_size > 0);
  assert(result.count("log-path"));
  std::ofstream logger(result["log-path"].as<std::string>());
  std::string browserbench_path = "../WebKit/Websites/browserbench.org/";
  std::string jetstream1_path = browserbench_path + "JetStream1.1/";
  std::string jetstream2_path = browserbench_path + "JetStream2.0/";
  std::string octane_path = jetstream2_path + "Octane/";
  std::string sunspider_path = jetstream1_path + "sunspider/";
  std::vector<Benchmark> jetstream2_js_paths;
  std::vector<Benchmark> js_paths;
  jetstream2_js_paths.push_back({octane_path, "splay.js", 1500});
  jetstream2_js_paths.push_back({octane_path, "pdfjs.js", 1000});
  Signal s;
  std::vector<std::thread> threads;
  std::vector<std::future<V8_Result>> futures;
  {
    std::string header = "let performance = {now() { return 0; }};";
    for (const Benchmark&b : jetstream2_js_paths) {
      std::string js_path = b.directory + b.name;
      std::string footer = "for(i = 0; i < " + std::to_string(b.repeat_time) + "; i++) {new Benchmark().runIteration();}";
      Signal* ps = &s;
      std::vector<std::pair<size_t, std::string>> input = {{1, header}, {1, read_file(js_path)}, {1, footer}};
      futures.push_back(std::async(std::launch::async, run_v8, platform, input, b.name, heap_size, &s));
    }
  }

  {
    std::string header = "let performance = {now() { return 0; }};";
    std::string footer = "for(i = 0; i < 100; i++) {new Benchmark().runIteration();}";
    Signal* ps = &s;
    std::vector<std::pair<size_t, std::string>> input =
      {{1, header},
       {1, read_file(octane_path + "typescript-compiler.js")},
       {1, read_file(octane_path + "typescript-input.js")},
       {1, read_file(octane_path + "typescript.js")},
       {1, footer}};
    futures.push_back(std::async(std::launch::async, run_v8, platform, input, "typescript.js", heap_size, &s));
  }

  for (const Benchmark& b : js_paths) {
    std::string js_path = b.directory + b.name;
    Signal* ps = &s;
    std::vector<std::pair<size_t, std::string>> input = {{1, std::string("for(i = 0; i < " + std::to_string(b.repeat_time) + "; i++) {") + read_file(js_path) + "}"}};
    futures.push_back(std::async(std::launch::async, run_v8, platform, input, b.name, heap_size, &s));
  }

  s.signal();

  size_t total_major_gc_time = 0;
  size_t total_time = 0;
  for (auto& future : futures) {
    auto ret = future.get();
    total_major_gc_time += ret.major_gc_time;
    total_time += ret.time;
  }

  logger << tagged_json("peak_memory", v8::PeakMemory()) << std::endl;
  logger << tagged_json("total_major_gc_time", total_major_gc_time) << std::endl;
  logger << tagged_json("total_time", total_time) << std::endl;
}
