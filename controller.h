#pragma once

struct RuntimeNode;
using Runtime = std::shared_ptr<RuntimeNode>;
struct ControllerNode : std::enable_shared_from_this<ControllerNode> {
protected:
  // this look like weak_ptr, but the content should always be here:
  // whenever a runtimenode gone out of life it will notify the controller, and get it removed.5
  std::set<std::weak_ptr<RuntimeNode>, std::owner_less<std::weak_ptr<RuntimeNode>>> runtimes_;
  size_t max_memory_ = 0;
public:
  virtual ~ControllerNode() = default;
  virtual bool request(const Runtime& r, size_t extra) = 0;
  virtual void optimize() = 0;
  // the name of the controller, for debugging and reporting purpose.
  virtual std::string name() = 0;
  void add_runtime(const Runtime& r);
  void remove_runtime(const Runtime& r);
  std::vector<Runtime> runtimes();
  void set_max_memory(size_t max_memory_) {
    this->max_memory_ = max_memory_;
    set_max_memory_aux(max_memory_);
  }
  size_t max_memory() {
    return max_memory_;
  }
  virtual void set_max_memory_aux(size_t max_memory_) { }
  virtual void add_runtime_aux(const Runtime& r) { }
  virtual void remove_runtime_aux(const Runtime& r) { }
};
using Controller = std::shared_ptr<ControllerNode>;
