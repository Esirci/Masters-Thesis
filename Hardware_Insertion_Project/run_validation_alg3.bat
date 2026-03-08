@echo off
REM Compile Algorithm 3 validation tool (Windows)
g++ -std=c++17 -I./src validate_alg3.cpp src/Netlist.cpp src/Simulator.cpp src/PODEM.cpp src/CompatibilityGraph.cpp src/TrojanGenerator.cpp -o validate_alg3.exe

REM Run validation
validate_alg3.exe
