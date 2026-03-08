# Compatibility Graph Assisted Hardware Trojan Insertion Framework

This project implements a C++ framework for inserting stealthy Hardware Trojans into combinational and sequential logic circuits (ISCAS-85/89 benchmarks). It uses a custom **5-valued PODEM Algorithm** and **Compatibility Graph Analysis** to identify rare, compatible trigger nodes and insert four types of Trojan payloads (TrustHub Taxonomy).

## 🚀 Features
*   **Sequential Circuit Support**: Parses and processes `DFF` gates using the Full Scan Assumption.
*   **Custom ATPG**: Implements a 5-valued logic algebra (`0`, `1`, `X`, `D`, `D'`) to solve calculating conflicts in complex gates like XOR.
*   **Batch Processing**: Automatically iterates through `inputs/combinational` and `inputs/sequential` directories.
*   **Robustness**: Handles dense graphs with Bounded Bron-Kerbosch and supports alphanumeric gate names.

## 📋 Prerequisites
To run this project, you need a C++ compiler installed on your system:
*   **Windows**: MinGW-w64 (`g++`) or MSVC.
*   **Linux/Mac**: GCC (`g++`) or Clang.
*   **Standard**: C++17 or later.

## 🛠️ How to Build and Run

### Option 1: Windows (Simplest)
1.  Open the project folder.
2.  Double-click **`build_and_run.bat`**.
    *   This script will compile the code using `g++` and immediately launch the framework in interactive, batch mode.
    *   The executable `trojan_framework.exe` will be created in the root directory.

### Option 2: Linux / macOS (Using Makefile)
1.  Open a terminal in the project directory.
2.  Run `make`.
    *   This uses the provided `Makefile` to compile source files from `src/` into `obj/` and outputs the executable to `bin/`.
3.  Run the tool:
    ```bash
    ./bin/trojan_framework.exe
    ```
4.  To clean up build artifacts:
    ```bash
    make clean
    ```

## 📂 Project Structure
*   `src/`: C++ Source Code (`Netlist`, `PODEM`, `CompatibilityGraph`, etc.).
*   `inputs/`: Place your `.bench` files here (subfolders: `combinational`, `sequential`).
*   `outputs/`: Generated Trojan-infected netlists will appear here.
*   `Final_Report.md`: Comprehensive validation report comparing results with the reference paper.

## 📊 Validation & Reporting
The project includes a full validation suite to reproduce experiments from the reference paper:

*   **Algorithm 1 Validation** (`validate_alg1.cpp`): Reproduces Rare Node identification results (Paper Fig 2 & 3).
*   **Algorithm 2 Validation** (`validate_alg2.cpp`): Generates Compatibility Graphs and finds cliques.
*   **Algorithm 3 Validation** (`validate_alg3.cpp`): Inserts and tests Trojans for functional stealth.
*   **Full Metrics** (`validate_tables.cpp`): Generates Area Overhead and Detection Probability tables.

### Running Validation
Each algorithm has a corresponding batch script:
1.  `run_validation_alg1.bat` -> Generates `validation_fig2.csv`
2.  `run_validation_alg2.bat` -> Generates `validation_alg2_cliques.csv`
3.  `run_validation_alg3.bat` -> Generates `validation_tables.csv`

### Visualization
*   `visualize_alg1.py`: Python script to generate plots (`validation_fig2_plot.png`) from the CSV data.

## 🧪 Usage Guide
1.  Upon running, the tool scans the `inputs` directory.
2.  It will perform Rare Node Analysis (Simulation) and Compatiblity Graph construction for each file.
3.  **Interactive Menu**:
    *   **Trigger Size**: Enter `4` to search for a clique of 4 rare nodes (stealthy). Enter `0` to skip the file.
    *   **Payload Type**: Select from `1` (Bit Flip), `2` (Delay), `3` (DoS), `4` (Info Leak).
4.  **Result**: The infected file is saved to `outputs/folder_name/filename_trojan.bench`.
