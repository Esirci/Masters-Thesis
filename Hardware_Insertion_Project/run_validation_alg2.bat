@echo off
REM Compile Algorithm 2 validation tool (Windows)
g++ -std=c++17 -I./src validate_alg2.cpp src/Netlist.cpp src/Simulator.cpp src/PODEM.cpp src/CompatibilityGraph.cpp -o validate_alg2.exe

REM Run validation
validate_alg2.exe

echo "Algorithm 2 validation complete. Check validation_alg2_cliques.csv"
