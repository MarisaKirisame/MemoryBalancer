.PHONY: compile run nightly

compile:
	(cd build && cmake .. && make)

run: compile
	build/MemoryBalancer gc_log

nightly: run
