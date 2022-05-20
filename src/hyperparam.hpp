#pragma once

constexpr size_t bytes_in_mb = 1048576;

// hyperparameter used by membalancer.
// extracted into a header file, such that macro.cpp can output all the hyperparameters and generate tex file, keeping all hyperparam up to date.

// for our balancing purpose, we pretend the working memory is more then we measured.
// this is because:
// 0: the gc take some time to start up warm up, so gc time is not exactly an multiple of heap size
// 1: pretending the working set is bigger allocate more memory to the beginning of the phase, which allower a quicker working set growth (which our model do not capture).
constexpr size_t bias_in_working_memory = 5 * bytes_in_mb;

constexpr double initial_garbage_bytes = 1; // hack - start off with a small number to avoid nan and inf
constexpr double initial_garbage_duration = 10;

constexpr double garbage_rate_decay_per_sec = 0.95;

constexpr double gc_speed_smoothing_per_sample = 0.5;

constexpr size_t total_memory_floor = 10 * bytes_in_mb;
constexpr size_t extra_memory_floor = 3 * bytes_in_mb;
