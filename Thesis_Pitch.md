# Thesis Defense Pitch / Abstract

**Title:** Adversarial Generation and Robust Evaluation of Feature-Evasive Hardware Trojans

### 1. The Core Motivation
While recent hardware security frameworks achieve >97% detection accuracies on standard datasets (e.g., TrustHub), they suffer from a critical blind spot: they have never been evaluated against an adaptive attacker. Modern state-of-the-art insertions (TrojanForge, ATTRITION) use black-box RL or arbitrary modification, but no existing work has explicitly coupled deterministic, graph-constrained candidate enumeration with a fixed feature-space minimization objective. 

As a result, the hardware security community does not know if robust detectors (like Deep Q-Networks) actually detect anomalous topological signatures, or if they simply memorize "easy" structural artifacts in non-evasive datasets.

### 2. The Core Scientific Contribution (The Attacker)
This thesis explicitly resolves that literature gap by introducing the **Adversarial Co-Evaluation Framework**, built upon our novel **Minimum Feature Perturbation (MFP)** heuristic.

By physically integrating a C++ Compatibility Graph generator directly with the 605-dimensional HTPred feature extractor, our framework iteratively enumerates every legally valid rare-node graph insertion. Rather than inserting random cliques, the orchestrator algorithm extracts the feature vector of every theoretical candidate and selects the exact topology that provably minimizes the spatial Mahalanobis Distance to the clean distribution. 

### 3. Rigorous Methodology (Fixing Systemic Data Leakage)
To prove the mathematical validity of our attack, we had to eliminate systemic flaws in standard hardware ML pipelines. 
1. **Unrolling Data Leakage:** Subgraph-isomorphism requires sequential circuit unrolling, naturally destroying Flip-Flop geometry. We wrote novel mitigation scripts to aggressively unroll the clean distribution, destroying the "missing DFF" artifact that artificially inflated previous baseline DNN accuracies to 100%.
2. **Strict Circuit-Disjointing:** We enforced Zero-Shot topological testing, ensuring models could not memorize base-graph topologies.
3. **5-Fold CV GAN Redundancy:** By mathematically proving (via 5-Fold Stratification) that highly asymmetric `-20.0 False Positive` reward shaping intrinsically solves minority-class imbalance, we established that Reinforcement Learning agents can be natively retrained without synthesized GAN topologies.

### 4. The Final Empirical Proof
We forced both standard classifiers and a highly robust DQN agent to defend against our MFP Attacker under "Zero-Day" starved conditions. 

The results were mathematically definitive:
* On identical, data-leakage-free unrolled topologies, the Deep Reinforcement Learning agent established a 61.11% baseline detection against standard Random insertions.
* However, when faced with our Loss-Guided and MFP algorithms, the DQN agent was mathematically blinded, experiencing a **catastrophic evasion collapse down to 21.05% and 27.78% TPR** respectively.

**Conclusion:** We successfully proved that deterministic, constraint-graph spatial-minimization Trojans are a highly viable, measurable, and deadly threat against even state-of-the-art robust detectors.
