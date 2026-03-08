# HTPred-Reproduction: Hardware Trojan Detection Feature Extraction

This directory contains the core Python scripts, datasets, and benchmark files used for extracting features from hardware netlists to detect Hardware Trojans. The process involves parsing `.bench` or `.txt` files, simulating structural and functional properties, extracting detailed topological and statistical features, and aggregating them into a consolidated dataset for machine learning models.

## 📂 Directory Structure

### Benchmark & Hardware Files
*   **`Non Trojan Files/`**: Contains the clean, Trojan-free benchmark netlists (e.g., ISCAS85, ISCAS89, ITC99, AES) in `.bench` or `.txt` format.
*   **`Trojan Files/`**: Contains the corresponding infected netlists infused with hardware Trojans (e.g., Trust-HUB benchmarks).
*   **`Verilogs Non Trojan/`**: Contains the original hardware designs in Verilog format for the clean circuits.
*   **`Verilogs Trojan/`**: Contains the original hardware designs in Verilog format for the Trojan-infected circuits.

### Technology Libraries
*   **`synopsis_cells/`**: Synopsys standard cell library definitions used to map logical cells during parsing.
*   **`tsmc_cells/`**: TSMC standard cell library definitions used to map physical and logical gates.

### System Directories
*   **`__pycache__/`**: Standard Python cache directory for compiled bytecode.

---

## 📄 Core Python Scripts

### 1. Main Orchestration
*   **`main.py`**: The primary entry point of the project. It orchestrates the entire workflow by iterating through `Non Trojan Files/` and `Trojan Files/`, performing functional and structural feature extraction, and finally appending the standardized feature vectors into the output CSV.

### 2. Functional & Probability Features
*   **`ControlObserveProbabCalculator.py`**: Calculates the Controllability (CC0, CC1), Observability (CO), and Probabilities (Prob0, Prob1) for all nodes within the circuit. This serves as the foundation for the functional features.
*   **`getfunctionalfeatures.py`**: Wrapper script that initializes `COPCalculator` and dictates how the functional features are evaluated and stored.
*   **`COFormula.py`**: Contains the specific boolean logic implementations to compute the Controllability and Observability equations.
*   **`ProbFormula.py`**: Contains the boolean logic formulas to calculate signal probabilities across different gate types.

### 3. Structural & Topological Features
*   **`structural_features_extractor.py`**: Extracts structural characteristics of the netlist (e.g., gate types, fan-ins, fan-outs) after parsing.
*   **`BenchToFeatureExtractor.py`**: Evaluates the circuit topography to extract distance-based features (like minimum distance to a Flip-Flop, loops, or Input/Output nodes).
*   **`module_feature_extractor.py`**: Extracts advanced topological features for modules such as structural distances, flip-flop reachability, and multiplexer layouts.
*   **`lfeaturesextractor.py`**: Extracts L-features based on the propagation of observability values throughout the circuit depth.
*   **`HTPredBenchCreator.py`**: Acts as a bridge to instantiate `BenchToFeatureExtractor` and aggregate structural properties into a dictionary.

### 4. Circuit Representation & Parsing
*   **`string_processing.py`**: The initial parser that loads a benchmark file as strings and tokenizes inputs, outputs, and internal gates.
*   **`Module.py`**: An object-oriented representation of a hardware module. Stores input/output pins, internal wires, and lists of gates.
*   **`Gates.py`**: Contains class definitions for basic logic gates (`AND`, `OR`, `NOT`, `XOR`, `DFF`, etc.), allowing simulating their logic limits.
*   **`module_description.py`**: Defines the physical representation of instantiated technology cells.
*   **`module_supplier.py`**: Acts as an interface to load standard cell definitions (TSMC/Synopsys) and supply them to the module parser.

### 5. Utilities & Data Management
*   **`features_extractor.py`**: Consolidates raw structural and functional metrics into their final feature representations before they are added to the dataset.
*   **`bench_session.py`**: A helper class managing the current session, wire definitions, and mapping standard bench formats during processing.
*   **`convert_verilog.py`**: Utility script to handle the conversion of `.v` Verilog files to `.bench` formats.
*   **`module_cleaner.py`**: A helper module used internally to prune unconnected branches or clean the data structure of a module representation.
*   **`headers_list.py`**: Returns the massive list of precise string names used as feature headers for the final CSV dataset.
*   **`csv_append.py`**: A simple utility used to correctly format and append a new row of extracted features to the `.csv` file without breaking existing format.
*   **`csv_shortener.py`**: A script that filters the massive `data.csv` file to extract a subset of the most relevant features or clean empty columns, producing `short_csv.csv`.

---

## 📊 Output Datasets

*   **`data.csv`**: The massive target dataset generated by running `main.py`. This contains all features extracted from both the clean and Trojan-infected circuit node by node.
*   **`short_csv.csv`**: A minimized version of the dataset, generated via `csv_shortener.py`, containing only the most pertinent feature columns or pruned instances, making algorithm training much faster.
