# wx-free command-line build.
#   make -C Astran -f cli.mk         builds build/bin/astran-cli
#   make -C Astran -f cli.mk test    builds and runs every tests/test_*.cpp
CXX      ?= g++
CXXFLAGS ?= -std=c++14 -O2 -DASTRAN_CLI -Wno-deprecated -fpermissive
OBJDIR   = build/obj-cli
BIN      = build/bin/astran-cli

SRCS   := $(filter-out src/wx%.cpp src/icpdApp.cpp src/icpdfrm.cpp src/main_cli.cpp,$(wildcard src/*.cpp))
OBJS   := $(patsubst src/%.cpp,$(OBJDIR)/%.o,$(SRCS))
TESTS  := $(wildcard tests/test_*.cpp)
TESTBINS := $(patsubst tests/%.cpp,$(OBJDIR)/%,$(TESTS))

all: $(BIN)

$(OBJDIR)/%.o: src/%.cpp $(wildcard src/*.h)
	@mkdir -p $(OBJDIR)
	$(CXX) $(CXXFLAGS) -c $< -o $@

$(BIN): $(OBJS) $(OBJDIR)/main_cli.o
	@mkdir -p $(dir $@)
	$(CXX) $^ -o $@

$(OBJDIR)/test_%: tests/test_%.cpp $(OBJS)
	@mkdir -p $(OBJDIR)
	$(CXX) $(CXXFLAGS) -Isrc $< $(OBJS) -o $@

test: $(TESTBINS)
	@fail=0; for t in $(TESTBINS); do echo "== $$t"; ./$$t || fail=1; done; exit $$fail

clean:
	rm -rf $(OBJDIR) $(BIN)

.PHONY: all test clean
