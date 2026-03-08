# Complete Code Walkthrough

This document explains the entire execution flow of the **Compatibility Graph Assisted Hardware Trojan Insertion Framework**, starting from `main.cpp` and tracing the logic through all modules.

---

## 1. Entry Point: `src/main.cpp`
The execution begins in the `main()` function.

### A. Batch Directory Setup (Lines 118-120)
The program automatically detects and iterates through two directories: `inputs/combinational` and `inputs/sequential`. This allows batch processing of multiple benchmark files.

### B. `processFile(...)` (Line 13)
This function manages the lifecycle of a single `.bench` file processing.

#### Step 1: Parsing the Netlist (Line 18)
It creates a `Netlist` object and calls `netlist.parse(inputPath)`.
> **Jump to `src/Netlist.cpp` -> `Netlist::parse()`**:
> *   **Line 65**: Opens and reads the file line-by-line.
> *   **Line 91**: Recognizes `INPUT(x)` and creates corresponding nodes.
> *   **Line 102**: Parses gate definitions (e.g., `g = NAND(a, b)`).
> *   **Sequential Support (Line 117)**: The parser implements the **Full Scan Assumption**:
>     *   **DFF Outputs (Q)** are treated as **Pseudo-Primary Inputs (PPI)**.
>     *   **DFF Inputs (D)** are treated as **Pseudo-Primary Outputs (PPO)**.
>     *   This transforms cyclic sequential circuits into acyclic combinational logic for ATPG analysis.

#### Step 2: Rare Node Identification (Line 26)
`main` creates a `Simulator` and calls `sim.findRareNodes(10000, 0.2)`.
> **Jump to `src/Simulator.cpp` -> `Simulator::findRareNodes()`**:
> *   **Line 71**: Executes a Monte Carlo simulation loop (10,000 iterations).
> *   **Line 75**: Randomly assigns logic `0` or `1` to all Inputs (including PPIs).
> *   **Line 81**: Recursively evaluates the circuit logic using `evaluate()`.
> *   **Line 104**: Flags nodes as **Rare-1** or **Rare-0** if their transition probability is below the threshold (0.2).

#### Step 3: Compatibility Analysis (Line 40)
`main` initializes construction of the Compatibility Graph.

**1. Test Vector Generation** (`cg.generateTestVectors`)
> **Jump to `src/CompatibilityGraph.cpp`**:
> *   Iterates through verified Rare Nodes.
> *   Calls `podem.generateTest(node, rare_value)` to find an input pattern that triggers the node.
>     > **Jump to `src/PODEM.cpp`**:
>     > *   **5-Valued Logic**: Implements `0`, `1`, `X`, `D`, `D_BAR` algebra to handle fault sensitization.
>     > *   **Recursion (Line 268)**: Uses `getObjective()` to find necessary input assignments and `backtrace()` to satisfy them.
>     > *   Returns a valid input vector if the rare value is controllable and observable.

**2. Graph Construction** (`cg.buildGraph`)
> **Jump to `src/CompatibilityGraph.cpp`**:
> *   **Line 45**: Compares Test Vectors for every pair of Rare Nodes.
> *   **Line 54**: Checks for logical conflicts (e.g., Node A needs Input=0, Node B needs Input=1).
> *   **Edge Creation**: Adds an edge if vectors are compatible, meaning both nodes can be triggered simultaneously.

#### Step 4: Clique Finding (Line 55)
`main` prompts the user for a **Trigger Size** (k) and calls `cg.findCliques(k)`.
> **Jump to `src/CompatibilityGraph.cpp` -> `findCliques()`**:
> *   **Algorithm**: Uses **Bron-Kerbosch** with pivoting to find fully connected subgraphs (Cliques).
> *   **Optimization (Line 73)**: Implements a recursion limit (50,000 steps) to ensure termination on dense graphs (like `s499`).
> *   **Result**: A Clique represents a set of Rare Nodes that can form a valid Trojan Trigger.

#### Step 5: Trojan Generation (Line 96)
`main` prompts for **Payload Type** and calls `TrojanGenerator`.

**1. Trigger Logic** (`tg.generateTrigger`)
> **Jump to `src/TrojanGenerator.cpp`**:
> *   **Line 28**: Analyzes the size of the clique.
> *   **Tree Optimization (Line 32)**: For large triggers (>8 inputs), generates a multi-level tree of gates to reduce electrical fan-in load.
> *   **Standard Logic**: Uses AND gates (for Rare-1) and NOR gates (for Rare-0) to create a trigger signal that activates ONLY when the rare condition is met.

**2. Payload Insertion** (`tg.insertPayload`)
> **Jump to `src/TrojanGenerator.cpp`**:
> *   **Line 138 (Victim Selection)**: Traces downstream to find an observable victim net.
> *   **Line 231 (ID Shifting)**: Shifts node IDs to assume a stealthy numeric range, creating a "gap" for Trojan gates.
> *   **TrustHub Payloads**:
>     1.  **Bit Flip (XOR)**: Inverts the victim's logic value.
>     2.  **Delay (Performance)**: Inserts a chain of buffers to degrade path timing.
>     3.  **DoS (Stuck-At)**: Forces the line to `0` or `1`, disabling the circuit segment.
>     4.  **Info Leak**: Inserts a MUX to leak a secret internal node value to the output.

#### Step 6: Saving the Netlist (Line 106)
`main` calls `netlist.write(outputPath)`.
> **Jump to `src/Netlist.cpp` -> `Netlist::write()`**:
> *   **Formatting**: Reconstructs the `.bench` file format.
> *   **Cycle Breaking (Line 203)**: During topological sort, DFF loops are explicitly managed to prevent infinite recursion, ensuring correct writing of sequential circuits.

---

## 2. Validation Suite
Separate from the main interactive tool, the project includes standalone validators to reproduce paper results.

### A. Rare Node Validation (`validate_alg1.cpp`)
*   **Purpose**: Bulk simulation to plot Rare Nodes vs. Threshold for all inputs.
*   **Key Logic**:
    *   Iterates thresholds $\theta \in [0.0, ..., 0.3]$.
    *   Runs Monte Carlo (10k vectors) for every benchmark.
    *   Exports `validation_fig2.csv` for plotting.

### B. Compatibility Validation (`validate_alg2.cpp`)
*   **Purpose**: Metrics for Graph Density and Clique Finding performance.
*   **Key Logic**:
    *   Builds Compatibility Graph.
    *   Measures `std::chrono` duration for graph build vs. clique find.
    *   Outputs `validation_alg2_cliques.csv` containing Node Count, Edge Count, Density, and execution times.

### C. Trojan Stealth Validation (`validate_tables.cpp`)
*   **Purpose**: Generates Table II (Detection) and Table V (Area).
*   **Key Logic**:
    *   Inserts the Trojan (Alg 3).
    *   **Area**: Calculates `(TrojanGates - OriginalGates) / OriginalGates`.
    *   **Stealth**: Runs 100,000 random vectors. Checks if the Trojan Trigger activates accidentally.
    *   Exports `validation_tables.csv`.
