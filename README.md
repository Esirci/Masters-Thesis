# Master's Thesis: Adversarial Co-Evaluation Framework for Feature-Evasive Hardware Trojans

This repository contains the complete source code, datasets, and experiment logs for my Master's Thesis. The thesis addresses the critical gap in Hardware Security research: Can state-of-the-art Machine Learning and Reinforcement Learning detectors identify Hardware Trojans that are mathematically engineered to minimize structural perturbations in the designated feature space?

To accomplish this, my project consists of four interconnected repositories spanning C++ insertion tools, Python feature extractors, and Deep Reinforcement Learning models.

---

## 📁 Repository Structure

### 1. `Adversarial_Co-Evaluation_Framework/` (The Core Pipeline)
This is the central orchestration repository of the thesis. It structurally ties the other three projects together to evaluate the **Minimum Feature Perturbation (MFP)** attack against state-of-the-art defenses under strict, circuit-disjoint (Zero-Shot) conditions.
* Evaluates standard ensemble detectors (DNN, RF) and natively-trained RL agents.
* Proves that the MFP mathematical evasion mathematically shatters robust Reinforcement Learning baselines (dropping true positive rates from 61% to a catastrophic 21%).

### 2. `Hardware_Insertion_Project/` (The Attacker)
A custom **C++ tool** implementing a Compatibility Graph enumerator for sequential circuits. Instead of inserting random payload cliques, this deterministic tool finds rare nodes and outputs structurally valid, subgraph-isomorphism-legal Trojan configurations. The Adversarial Orchestrator uses this to generate the thousands of possible insertion candidates required for optimization.

### 3. `HTPred-master/` (The Feature Space)
A fixed and rigorously optimized version of the famous Springer 2025 HTPred pipeline. It evaluates gate-level netlists to extract a highly specialized 605-dimensional structural and functional feature vector. My thesis optimizes this codebase to aggressively slash execution time (from days to hours) and explicitly fixes its structural data-leakage vulnerabilities (sequential DFF unrolling discrepancies).

### 4. `Hybrid_GAN_RL_Architecture/` (The Defender)
A highly robust defensive machine learning architecture operating via Reinforcement Learning (DQN) with severe False Positive (`-20.0`) asymmetric penalty rewards. 
* Extensively evaluated natively using rigorous **5-Fold Cross Validation**.
* Achieves a validated `99.22% accuracy` against standard industry benchmarks (Trusthub).
* Mathematically proves that implicit reward-shaping renders CTGAN synthesized minority-class data inherently redundant.

---

## 🚀 How to Run the Co-Evaluation Pipeline

To reproduce the core evasion collapse that defines this thesis, enter the `Adversarial_Co-Evaluation_Framework/` directory and follow the sequential pipeline detailed in its local `README.md`. 

The high-level execution flow is:
1. `extract_unrolled_clean.py` — Establishes a zero-leakage structural baseline.
2. `precompute_covariance.py` — Calculates the exact limits of the benign feature manifold (Ledoit-Wolf precision matrix).
3. `build_feht_dataset.py` — Formally synthesizes the Feature-Evasive Hardware Trojan datasets.
4. `evaluate_baseline_dnn.py` & `train_evaluate_ganrl.py` — Benchmarks the attackers against state-of-the-art model deployments.

---

## 🎓 Academic Contributions
1. First deterministic, constraint-graph candidate enumeration optimized explicitly over an external continuous feature space (MFP Algorithm). 
2. Eradication of sequential Data Leakage issues that unknowingly artificially inflate standard hardware baseline metrics natively in modern literature. 
3. Definitive mathematical breakdown proving robust Reinforcement Learning algorithms are catastrophically vulnerable to mathematical spatial-minimization Trojans.
