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

size_t run_v8_cleanroom(v8::Platform* platform, const std::vector<std::pair<size_t, std::string>>& input, const std::string& name, size_t heap_size, Signal* s) {
  v8::Isolate::CreateParams create_params;
  create_params.constraints.ConfigureDefaultsFromHeapSize(0, heap_size);
  create_params.constraints.set_code_range_size_in_bytes(10 * 1048576);
  create_params.array_buffer_allocator =
    v8::ArrayBuffer::Allocator::NewDefaultAllocator();
  v8::Isolate* isolate = v8::Isolate::New(create_params);
  isolate->SetName(name);
  size_t result;
  {
    v8::Isolate::Scope isolate_scope(isolate);
    v8::HandleScope handle_scope(isolate);
    v8::Local<v8::Context> context = v8::Context::New(isolate);
    v8::Context::Scope context_scope(context);
    {
      s->wait();
      time_point begin = steady_clock::now();
      for (const auto& p: input) {
        v8::Local<v8::String> source = fromString(isolate, p.second);
        v8::Local<v8::Script> script =
          v8::Script::Compile(context, source).ToLocalChecked();
        for (size_t i = 0; i < p.first; ++i) {
          script->Run(context);
          while (v8::platform::PumpMessageLoop(platform, isolate)) {
            //std::cout << "message pumped!" << std::endl;
          }
        }
      }
      time_point end = steady_clock::now();
      result = duration_cast<milliseconds>(end - begin).count();
    }
  }
  isolate->Dispose();
  return result;
}

size_t run_v8(const Input& i, std::mutex* m) {
  std::cout << "running " << i.code_path << std::endl;
  // Create a new Isolate and make it the current one.
  v8::Isolate::CreateParams create_params;
  //create_params.constraints.ConfigureDefaults(heap_size, 0);
  create_params.constraints.ConfigureDefaultsFromHeapSize(i.heap_size, i.heap_size);
  size_t old = create_params.constraints.max_old_generation_size_in_bytes();
  size_t young = create_params.constraints.max_young_generation_size_in_bytes();
  //std::cout << old << " " << young << " " << old + young << std::endl;
  create_params.array_buffer_allocator =
      v8::ArrayBuffer::Allocator::NewDefaultAllocator();
  size_t run_time_taken;
  v8::Isolate* isolate = v8::Isolate::New(create_params);
  isolate->SetMaxPhysicalMemoryOfDevice(0.9e9);
  {
    v8::Isolate::Scope isolate_scope(isolate);
    // Create a stack-allocated handle scope.
    v8::HandleScope handle_scope(isolate);
    // Create a new context.
    v8::Local<v8::Context> context = v8::Context::New(isolate);
    // Enter the context for compiling and running the hello world script.
    v8::Context::Scope context_scope(context);

    {
      // Create a string containing the JavaScript source code.
      v8::Local<v8::String> source = fromString(isolate, read_file(i.code_path));

      // Compile the source code.
      v8::Local<v8::Script> script =
        v8::Script::Compile(context, source).ToLocalChecked();

      m->lock();
      m->unlock(); // abusing mutex as signal - once the mutex is unlocked everyone get access.
      time_point begin = steady_clock::now();
      v8::Local<v8::Value> result;
      result = script->Run(context).ToLocalChecked();
      time_point end = steady_clock::now();
      run_time_taken = duration_cast<milliseconds>(end - begin).count();
      // Convert the result to an UTF8 string and print it.
      v8::String::Utf8Value utf8(isolate, result);
      printf("%s\n", *utf8);
    }
    v8::GCHistory history = isolate->GetGCHistory();
    for (const v8::GCRecord& r: history.records) {
      if (false && r.is_major_gc) {
        std::cout << "gc decrease memory by: " << long(r.before_memory) - long(r.after_memory) <<
          " in: " << r.after_time - r.before_time <<
          " rate: " << (long(r.before_memory) - long(r.after_memory)) / (r.after_time - r.before_time) <<
          " (is " << (r.is_major_gc ? std::string("major ") : std::string("minor ")) << "GC)" << std::endl;
      }
    }
    long total_garbage_collected = 0;
    long total_time_taken = 0;
    std::vector<double> garbage_collected, time_taken;
    for (const v8::GCRecord& r: history.records) {
      if (r.is_major_gc) {
        total_garbage_collected += long(r.before_memory) - long(r.after_memory);
        garbage_collected.push_back(long(r.before_memory) - long(r.after_memory));
        total_time_taken += r.after_time - r.before_time;
        time_taken.push_back(r.after_time - r.before_time);
      }
    }
    std::sort(garbage_collected.begin(), garbage_collected.end());
    std::sort(time_taken.begin(), time_taken.end());
    //std::cout << "total garbage collected: " << total_garbage_collected << std::endl;
    //double mean_garbage_collected = mean(garbage_collected);
    //double sd_garbage_collected = sd(garbage_collected);
    //double normality_garbage_collected = normality(garbage_collected);
    //std::cout << "mean, sd, normality of garbage collected: " << mean_garbage_collected << ", " << sd_garbage_collected << ", " << normality_garbage_collected << std::endl;
    //std::cout << "total time taken: " << total_time_taken << std::endl;
    //double mean_time_taken = mean(time_taken);
    //double sd_time_taken = sd(time_taken);
    //double normality_time_taken = normality(time_taken);
    //std::cout << "mean, sd, normality of time taken: " << mean_time_taken << ", " << sd_time_taken << ", " << normality_time_taken << std::endl;
    //std::cout << "garbage collection rate: " << double(total_garbage_collected) / double(total_time_taken) << std::endl;
  }
  isolate->Dispose();
  delete create_params.array_buffer_allocator;
  return run_time_taken;
}

void read_write() {
  std::mutex m;
  m.lock();

  std::ifstream t("balancer-config");
  json j;
  t >> j;

  Input i = read_from_json(j);
  std::future<size_t> o = std::async(std::launch::async, run_v8, i, &m);

  m.unlock();
  j["time_taken"] = o.get();

  log_json(j, "v8-experiment");
}

void parallel_experiment() {
  std::mutex m;
  m.lock();

  std::string octane_path = "../js/";
  Input splay_input;
  splay_input.heap_size = 0;//300*1e6;
  splay_input.code_path = octane_path + "splay.js";

  Input pdfjs_input;
  pdfjs_input.heap_size = 0;//700*1e6;
  pdfjs_input.code_path = "pdfjs.js";

  std::vector<Input> inputs;
  for (int i = 0; i < 2; ++i) {
    inputs.push_back(splay_input);
    //inputs.push_back(pdfjs_input);
  }

  std::vector<std::future<size_t>> futures;
  for (const Input& input : inputs) {
    futures.push_back(std::async(std::launch::async, run_v8, input, &m));
  }

  m.unlock();

  size_t total_time = 0;
  for (std::future<size_t>& future : futures) {
    total_time += future.get();
  }

  std::cout << "total_time = " << total_time << std::endl;
}

void v8_experiment(v8::Platform* platform, const std::vector<char*>& args) {
  cxxopts::Options options("V8 Experiment", "run some experiment from jetstream");
  options.add_options()
    ("h,heap-size", "Heap size in bytes.", cxxopts::value<int>());
  auto result = options.parse(args.size(), args.data());
  assert(result.count("heap-size"));
  int heap_size = result["heap-size"].as<int>();
  assert(heap_size > 0);
  std::string browserbench_path = "../WebKit/Websites/browserbench.org/";
  std::string jetstream1_path = browserbench_path + "JetStream1.1/";
  std::string jetstream2_path = browserbench_path + "JetStream2.0/";
  std::string octane_path = jetstream2_path + "Octane/";
  std::string sunspider_path = jetstream1_path + "sunspider/";
  std::vector<std::pair<std::string, std::string>> jetstream2_js_paths;
  // js_paths.push_back(octane_path + "richards.js"); // not used because not memory heavy
  jetstream2_js_paths.push_back({octane_path, "earley-boyer.js"}); // comment out temporarily
  // js_paths.push_back(octane_path + "deltablue.js"); // not used because not memory heavy
  jetstream2_js_paths.push_back({octane_path, "pdfjs.js"}); // comment out temporarily
  jetstream2_js_paths.push_back({octane_path, "splay.js"}); // comment out temporarily
  jetstream2_js_paths.push_back({jetstream2_path, "simple/hash-map.js"}); // comment out temporarily
  // jetstream2_js_paths.push_back({octane_path, "box2d.js"}); // not used because not memory heavy
  // jetstream2_js_paths.push_back({jetstream2_path, "Seamonster/gaussian-blur.js"}); // not used because not memory heavy
  std::vector<std::pair<std::string, std::string>> js_paths;
  js_paths.push_back({sunspider_path, "tagcloud.js"}); // new benchmark; comment out temporarily

  Signal s;
  std::vector<std::thread> threads;

  {
    std::string header = "let performance = {now() { return 0; }};";
    std::string footer = "for(i = 0; i < 5; i++) {new Benchmark().runIteration();}";
    for (const std::pair<std::string, std::string>& p : jetstream2_js_paths) {
      std::string js_directory = p.first;
      std::string js_name = p.second;
      std::string js_path = js_directory + js_name;
      Signal* ps = &s;
      threads.emplace_back([=](){run_v8_cleanroom(platform, {{1, header}, {1, read_file(js_path)}, {200, footer}}, js_name, heap_size, ps);});
    }
  }

  {
    std::string header = "let performance = {now() { return 0; }};";
    std::string footer = "for(i = 0; i < 5; i++) {new Benchmark().runIteration();}";
    Signal* ps = &s;
    threads.emplace_back([=](){run_v8_cleanroom(platform, {{1, header},
                                                           {1, read_file(octane_path + "typescript-compiler.js")},
                                                           {1, read_file(octane_path + "typescript-input.js")},
                                                           {1, read_file(octane_path + "typescript.js")},
                                                           {20, footer}}, // typescript is slow. run it less.
          "typescript.js", heap_size, ps);});
  }

  for (const std::pair<std::string, std::string>& p : js_paths) {
    std::string js_directory = p.first;
    std::string js_name = p.second;
    std::string js_path = js_directory + js_name;
    Signal* ps = &s;
    threads.emplace_back([=](){run_v8_cleanroom(platform, {{1000, read_file(js_path)}}, js_name, heap_size, ps);});
  }

  s.signal();
  for (std::thread& t : threads) {
    t.join();
  }
  std::cout << "run ok!" << std::endl;
}
