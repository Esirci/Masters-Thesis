# Compile validation tool (Windows)
g++ -std=c++17 -I./src validate_alg1.cpp src/Netlist.cpp src/Simulator.cpp -o validate_alg1.exe

# Run validation
./validate_alg1.exe

echo "Validation complete. Check validation_fig2.csv and validation_fig3.csv"
