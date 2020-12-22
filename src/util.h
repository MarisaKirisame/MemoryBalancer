#pragma once
#include <v8.h>
#include <libplatform/libplatform.h>

std::string get_time();

double mean(const std::vector<double>& v);

double sd(const std::vector<double>& v);

double normality(const std::vector<double>& v);

v8::Local<v8::String> fromFile(v8::Isolate* isolate, const std::string& path);

constexpr size_t min_heap_size = 2359296;
constexpr size_t max_heap_size = 4e9; // Beyond 4gb ConfigureDefaults start acting funny.

size_t random_heap_size();

double median(const std::vector<double>& vec);

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
