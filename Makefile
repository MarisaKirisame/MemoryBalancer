.PHONY: compile v8 run nightly

v8:
	(cd ../v8/src && ninja -C out.gn/x64.release.sample v8_monolith)

compile:
	(cd build && cmake .. && make)

run: compile
	(cd build && ./MemoryBalancer ../gc_log)

nightly:
	make run
	sh python/upload.sh
