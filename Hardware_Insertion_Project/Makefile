CXX      = g++
CXXFLAGS = -std=c++17 -Wall -Wextra -O2 -I.

SRC_DIR = src
OBJ_DIR = obj
BIN_DIR = bin

# ---------------------------------------------------------------------------
# Shared sources: everything except the two entry-point files
# ---------------------------------------------------------------------------
SHARED_SRCS = $(filter-out $(SRC_DIR)/main.cpp $(SRC_DIR)/generate_candidates.cpp, \
              $(wildcard $(SRC_DIR)/*.cpp))
SHARED_OBJS = $(patsubst $(SRC_DIR)/%.cpp, $(OBJ_DIR)/%.o, $(SHARED_SRCS))

# ---------------------------------------------------------------------------
# Target 1: original interactive framework
# ---------------------------------------------------------------------------
FRAMEWORK_TARGET = $(BIN_DIR)/trojan_framework.exe
FRAMEWORK_OBJS   = $(SHARED_OBJS) $(OBJ_DIR)/main.o

# ---------------------------------------------------------------------------
# Target 2: generate_candidates (Adversarial Co-Evaluation Framework Step 1)
# ---------------------------------------------------------------------------
CANDIDATES_TARGET = $(BIN_DIR)/generate_candidates.exe
CANDIDATES_OBJS   = $(SHARED_OBJS) $(OBJ_DIR)/generate_candidates.o

# ---------------------------------------------------------------------------
# Build rules
# ---------------------------------------------------------------------------
all: $(FRAMEWORK_TARGET) $(CANDIDATES_TARGET)

$(FRAMEWORK_TARGET): $(FRAMEWORK_OBJS) | $(BIN_DIR)
	$(CXX) $(CXXFLAGS) -o $@ $^

$(CANDIDATES_TARGET): $(CANDIDATES_OBJS) | $(BIN_DIR)
	$(CXX) $(CXXFLAGS) -o $@ $^

$(OBJ_DIR)/%.o: $(SRC_DIR)/%.cpp | $(OBJ_DIR)
	$(CXX) $(CXXFLAGS) -c -o $@ $<

# Windows-compatible directory creation (cmd.exe syntax for mingw32-make)
$(OBJ_DIR):
	if not exist $(OBJ_DIR) mkdir $(OBJ_DIR)

$(BIN_DIR):
	if not exist $(BIN_DIR) mkdir $(BIN_DIR)

# Windows-compatible clean
clean:
	if exist $(OBJ_DIR) rmdir /s /q $(OBJ_DIR)
	if exist $(BIN_DIR) rmdir /s /q $(BIN_DIR)

.PHONY: all clean
