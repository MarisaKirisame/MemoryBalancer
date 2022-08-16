#pragma once
#include <v8.h>
#include <nlohmann/json.hpp>
#include <libplatform/libplatform.h>
#include <filesystem>

inline v8::Local<v8::String> fromString(v8::Isolate* isolate, const std::string& str) {
  return v8::String::NewFromUtf8(isolate, str.data()).ToLocalChecked();
}

struct V8RAII {
  std::unique_ptr<v8::Platform> platform;
  V8RAII(const std::string& exec_location) {
    v8::V8::InitializeICUDefaultLocation(exec_location.c_str());
    v8::V8::InitializeExternalStartupData(exec_location.c_str());
    platform = v8::platform::NewDefaultPlatform();
    v8::V8::InitializePlatform(platform.get());
    v8::V8::Initialize();
    // todo: weird, errno is nonzero when executed to here.
    errno = 0;
  }
  ~V8RAII() {
    v8::V8::Dispose();
    v8::V8::DisposePlatform();
  }
};
