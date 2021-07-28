#pragma once
#include <v8.h>
#include <v8-json.h>
#include <libplatform/libplatform.h>
#include <filesystem>

// does this do anything? not really. should ask v8 ppl about OnCriticalMemoryPressure usage.
struct RestrictedPlatform : v8::Platform {
  RestrictedPlatform(std::unique_ptr<v8::Platform> &&platform_) : platform_(std::move(platform_)) { }
  std::unique_ptr<v8::Platform> platform_;
  v8::PageAllocator* GetPageAllocator() override {
    return platform_->GetPageAllocator();
  }

  void OnCriticalMemoryPressure() override {
    return platform_->OnCriticalMemoryPressure();
  }

  // todo: restrict memory here
  bool OnCriticalMemoryPressure(size_t length) override {
    return platform_->OnCriticalMemoryPressure(length);
  }

  int NumberOfWorkerThreads() override {
    return platform_->NumberOfWorkerThreads();
  }

  std::shared_ptr<v8::TaskRunner> GetForegroundTaskRunner(v8::Isolate* isolate) override {
    return platform_->GetForegroundTaskRunner(isolate);
  }

  void CallOnWorkerThread(std::unique_ptr<v8::Task> task) override {
    return platform_->CallOnWorkerThread(std::move(task));
  }

  void CallBlockingTaskOnWorkerThread(std::unique_ptr<v8::Task> task) override {
    return platform_->CallBlockingTaskOnWorkerThread(std::move(task));
  }

  void CallLowPriorityTaskOnWorkerThread(std::unique_ptr<v8::Task> task) override {
    return platform_->CallLowPriorityTaskOnWorkerThread(std::move(task));
  }

  void CallDelayedOnWorkerThread(std::unique_ptr<v8::Task> task, double delay_in_seconds) override {
    return platform_->CallDelayedOnWorkerThread(std::move(task), delay_in_seconds);
  }

  bool IdleTasksEnabled(v8::Isolate* isolate) override {
    return platform_->IdleTasksEnabled(isolate);
  }

  std::unique_ptr<v8::JobHandle> PostJob(v8::TaskPriority priority, std::unique_ptr<v8::JobTask> job_task) override {
    return platform_->PostJob(priority, std::move(job_task));
  }

  double MonotonicallyIncreasingTime() override {
    return platform_->MonotonicallyIncreasingTime();
  }

  double CurrentClockTimeMillis() override {
    return platform_->CurrentClockTimeMillis();
  }

  StackTracePrinter GetStackTracePrinter() override {
    return platform_->GetStackTracePrinter();
  }

  v8::TracingController* GetTracingController() override {
    return platform_->GetTracingController();
  }

  void DumpWithoutCrashing() override {
    return platform_->DumpWithoutCrashing();
  }
};

inline v8::Local<v8::String> fromFile(v8::Isolate* isolate, const std::string& path) {
  assert(std::filesystem::exists(path));
  std::ifstream t(path);
  std::string str((std::istreambuf_iterator<char>(t)),
                  std::istreambuf_iterator<char>());
  return v8::String::NewFromUtf8(isolate, str.data()).ToLocalChecked();
}

#ifdef USE_V8
struct V8RAII {
  std::unique_ptr<v8::Platform> platform;
  V8RAII(const std::string& exec_location) {
    v8::V8::InitializeICUDefaultLocation(exec_location.c_str());
    v8::V8::InitializeExternalStartupData(exec_location.c_str());
    platform = std::make_unique<RestrictedPlatform>(v8::platform::NewDefaultPlatform());
    v8::V8::InitializePlatform(platform.get());
    v8::V8::Initialize();
    // todo: weird, errno is nonzero when executed to here.
    errno = 0;
  }
  ~V8RAII() {
    v8::V8::Dispose();
    v8::V8::ShutdownPlatform();
  }
};
#else
struct V8RAII { V8RAII(const std::string&) { } };
#endif
