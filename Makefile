.PHONY: build/MemoryBalancer all compile v8 run nightly

all: compile

v8:
	(cd ../v8/src && ninja -C out.gn/x64.release.sample v8_monolith)

build/MemoryBalancer:
	mkdir -p build
	(cd build && cmake .. && make)

compile: build/MemoryBalancer

run: build/MemoryBalancer
	(cd build && ./MemoryBalancer)

debug: build/MemoryBalancer
	(cd build && gdb ./MemoryBalancer)

clean:
	./clean_log
	rm -rf build/*

nightly:
	git submodule init
	git submodule update
	git submodule sync
	make run
	sh python/upload.sh logs
