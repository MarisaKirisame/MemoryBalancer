.PHONY: all compile v8 run nightly

FORCE: ;

all: compile

v8:
	(cd ../v8/src && ninja -C out.gn/x64.release.sample v8_monolith)

build/MemoryBalancer: FORCE
	mkdir -p build
	(cd build && cmake .. && make)

compile: build/MemoryBalancer

run: build/MemoryBalancer
	(cd build && ./MemoryBalancer)

nightly:
	git submodule init
	git submodule update
	git submodule sync
	make run
	sh python/upload.sh logs
