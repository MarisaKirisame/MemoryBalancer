#include "acdc.hpp"
#include <future>

void Print(const v8::FunctionCallbackInfo<v8::Value>& args) {
  // print only work when there is a single isolate running. should find a way to bind isolate.
  // but we also can just not care about printing. the code doesnt print anything important.
  // the below code is kept for debugging purpose.
  // v8::String::Utf8Value str(isolate, args[0]);
  // fwrite(*str, sizeof(**str), str.length(), stdout);
  // fprintf(stdout, "\n");
  // fflush(stdout);
}

// todo: use size_t and convert to std::string
struct Input {
  std::string size;
  std::string liveness;
  std::string duration;
};

void run_acdc(v8::Platform* platform, const Input& input, Signal* s) {
  v8::Isolate::CreateParams create_params;
  create_params.array_buffer_allocator =
    v8::ArrayBuffer::Allocator::NewDefaultAllocator();
  v8::Isolate* isolate = v8::Isolate::New(create_params);
  isolate->SetName("acdc_" + input.size + "_" + input.liveness);
  {
    v8::Isolate::Scope isolate_scope(isolate);
    v8::HandleScope handle_scope(isolate);
    v8::Local<v8::Context> context = v8::Context::New(isolate);
    v8::Context::Scope context_scope(context);
    {
      v8::Local<v8::String> source = fromString(isolate, read_file("js/acdc.js"));
      v8::Local<v8::Script> script =
        v8::Script::Compile(context, source).ToLocalChecked();
      {
        std::vector<std::string> args = {"minSize", input.size, "maxSize", input.size, "benchmarkDuration", input.duration, "minLiveness", input.liveness, "maxLiveness", input.liveness};
        v8::Local<v8::Array> array = v8::Array::New(isolate, static_cast<int>(args.size()));
        for (int i = 0; i < args.size(); i++) {
          v8::Local<v8::String> arg =
            v8::String::NewFromUtf8(isolate, args[i].c_str()).ToLocalChecked();
          v8::Local<v8::Number> index = v8::Number::New(isolate, i);
          array->Set(context, index, arg).FromJust();
        }
        v8::Local<v8::String> name = v8::String::NewFromUtf8Literal(isolate, "arguments", v8::NewStringType::kInternalized);
        context->Global()->Set(context, name, array).FromJust();
      }
      {
        auto print_tmpl = v8::FunctionTemplate::New(isolate, Print);
        auto print_val = print_tmpl->GetFunction(context).ToLocalChecked();
        v8::Local<v8::String> name = v8::String::NewFromUtf8Literal(isolate, "print", v8::NewStringType::kInternalized);
        context->Global()->Set(context, name, print_val).FromJust();
      }
      s->wait();
      script->Run(context);
    }
  }
  std::cout << "try isolate->stopmb!" << std::endl;
  isolate->StopMB();
  std::cout << "isolate->stopmb ok!" << std::endl;
  std::this_thread::sleep_for (std::chrono::seconds(5));
  std::cout << "try isolate->dispose!" << std::endl;
  isolate->Dispose();
  std::cout << "isolate->dispose ok!" << std::endl;
}

void acdc(v8::Platform* platform, const std::vector<char*>& args) {
  //std::string size = "8";
  std::string size = "128";
  //std::string liveness = "1";
  std::string liveness = "16";
  std::string duration = "1000";
  std::vector<std::future<void>> futures;
  Signal s;
  if (false) {
    futures.push_back(std::async(std::launch::async,
                                 run_acdc,
                                 platform,
                                 Input {/*size=*/"8", /*liveness=*/"16", /*duration=*/"400"},
                                 &s));
    futures.push_back(std::async(std::launch::async,
                                 run_acdc,
                                 platform,
                                 Input {/*size=*/"128", /*liveness=*/"16", /*duration=*/"4000"},
                                 &s));
  futures.push_back(std::async(std::launch::async,
                               run_acdc,
                               platform,
                               Input {/*size=*/"8", /*liveness=*/"1", /*duration=*/"800"},
                               &s));
  futures.push_back(std::async(std::launch::async,
                               run_acdc,
                               platform,
                               Input {/*size=*/"128", /*liveness=*/"1", /*duration=*/"18000"},
                               &s));
  }
  futures.push_back(std::async(std::launch::async,
                               run_acdc,
                               platform,
                               Input {/*size=*/"8", /*liveness=*/"4", /*duration=*/"600"},
                               &s));
  futures.push_back(std::async(std::launch::async,
                               run_acdc,
                               platform,
                               Input {/*size=*/"32", /*liveness=*/"4", /*duration=*/"2500"},
                               &s));
  futures.push_back(std::async(std::launch::async,
                               run_acdc,
                               platform,
                               Input {/*size=*/"8", /*liveness=*/"1", /*duration=*/"750"},
                               &s));
  futures.push_back(std::async(std::launch::async,
                               run_acdc,
                               platform,
                               Input {/*size=*/"32", /*liveness=*/"1", /*duration=*/"4500"},
                               &s));
  s.signal();
  for (auto& f: futures) {
    f.get();
  }
}
