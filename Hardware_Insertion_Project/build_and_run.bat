@echo off
echo Compiling...
g++ -std=c++17 src/Netlist.cpp src/Simulator.cpp src/PODEM.cpp src/CompatibilityGraph.cpp src/TrojanGenerator.cpp src/main.cpp -o trojan_framework.exe -I src
if %errorlevel% neq 0 (
    echo Compilation Failed!
    exit /b %errorlevel%
)
echo Compilation Successful.
echo Running Batch Framework...
trojan_framework.exe
