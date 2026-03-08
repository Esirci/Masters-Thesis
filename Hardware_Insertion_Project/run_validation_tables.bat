@echo off
REM Compile Tables Validation Tool
g++ -std=c++17 -I./src validate_tables.cpp src/Netlist.cpp src/Simulator.cpp src/PODEM.cpp src/CompatibilityGraph.cpp src/TrojanGenerator.cpp -o validate_tables.exe

REM Run it
validate_tables.exe
