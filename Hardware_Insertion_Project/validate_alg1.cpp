// Experimental Validation Tool for Algorithm 1 (Rare Node Extraction)
// Reproduces Figure 2 and Figure 3 from the paper
// Usage: compile and run with --validate-alg1 flag

#include "Netlist.h"
#include "Simulator.h"
#include <iostream>
#include <fstream>
#include <vector>
#include <string>
#include <filesystem>
#include <iomanip>
#include <chrono>

namespace fs = std::filesystem;

struct BenchmarkResult {
    std::string circuit;
    int totalNodes;
    int rareNodes;
    double rarePercentage;
};

// Figure 2: Rare nodes vs. Threshold (θ_RN)
void validateFigure2() {
    std::cout << "\n=== Validating Figure 2: Rare Nodes vs. Threshold ===\n";
    
    std::vector<std::string> benchmarks = {
        "inputs/combinational/c2670.bench",
        "inputs/combinational/c3540.bench",
        "inputs/combinational/c5315.bench",
        "inputs/combinational/c6288.bench",
        "inputs/sequential/s1423.bench",
        "inputs/sequential/s13207.bench",
        "inputs/sequential/s15850.bench",
        "inputs/sequential/s35932.bench"
    };
    
    std::vector<double> thresholds = {0.05, 0.10, 0.15, 0.20, 0.25, 0.30};
    int numVectors = 10000; // Fixed (paper's selected value)
    
    std::ofstream csvFile("validation_fig2.csv");
    csvFile << "Circuit,Threshold,TotalNodes,RareNodes,RarePercentage\n";
    
    for (const auto& benchPath : benchmarks) {
        if (!fs::exists(benchPath)) {
            std::cout << "Skipping " << benchPath << " (not found)\n";
            continue;
        }
        
        std::string circuitName = fs::path(benchPath).stem().string();
        std::cout << "\nProcessing: " << circuitName << "\n";
        
        for (double thresh : thresholds) {
            Netlist netlist;
            if (!netlist.parse(benchPath)) {
                std::cerr << "Failed to parse " << benchPath << "\n";
                continue;
            }
            
            int totalNodes = netlist.getAllNodes().size();
            int thresholdCount = static_cast<int>(numVectors * thresh);
            
            Simulator sim(&netlist);
            sim.findRareNodes(numVectors, thresh);
            
            // Count rare nodes
            int rareCount = 0;
            for (Node* n : netlist.getAllNodes()) {
                if (n->rare_value != -1) rareCount++;
            }
            
            double rarePercent = (rareCount * 100.0) / totalNodes;
            
            csvFile << circuitName << ","
                    << std::fixed << std::setprecision(2) << (thresh * 100) << ","
                    << totalNodes << ","
                    << rareCount << ","
                    << rarePercent << "\n";
            
            std::cout << "  θ=" << std::setw(3) << (int)(thresh*100) << "%: "
                      << rareCount << "/" << totalNodes << " nodes ("
                      << std::fixed << std::setprecision(2) << rarePercent << "%)\n";
        }
    }
    
    csvFile.close();
    std::cout << "\nResults saved to: validation_fig2.csv\n";
}

// Figure 3: Rare nodes vs. Number of Test Vectors
void validateFigure3() {
    std::cout << "\n=== Validating Figure 3: Rare Nodes vs. Test Vectors ===\n";
    
    std::vector<std::string> benchmarks = {
        "inputs/combinational/c2670.bench",
        "inputs/combinational/c3540.bench",
        "inputs/combinational/c5315.bench",
        "inputs/combinational/c6288.bench",
        "inputs/sequential/s1423.bench",
        "inputs/sequential/s13207.bench",
        "inputs/sequential/s15850.bench",
        "inputs/sequential/s35932.bench"
    };
    
    std::vector<int> vectorCounts = {1000, 2500, 5000, 7500, 10000, 15000, 20000};
    double threshold = 0.05; // Fixed (S1: use stricter stealth threshold)
    
    std::ofstream csvFile("validation_fig3.csv");
    csvFile << "Circuit,NumVectors,TotalNodes,RareNodes,RarePercentage\n";
    
    for (const auto& benchPath : benchmarks) {
        if (!fs::exists(benchPath)) {
            std::cout << "Skipping " << benchPath << " (not found)\n";
            continue;
        }
        
        std::string circuitName = fs::path(benchPath).stem().string();
        std::cout << "\nProcessing: " << circuitName << "\n";
        
        for (int numVec : vectorCounts) {
            auto startTime = std::chrono::high_resolution_clock::now();
            
            Netlist netlist;
            if (!netlist.parse(benchPath)) {
                std::cerr << "Failed to parse " << benchPath << "\n";
                continue;
            }
            
            int totalNodes = netlist.getAllNodes().size();
            
            Simulator sim(&netlist);
            sim.findRareNodes(numVec, threshold);
            
            // Count rare nodes
            int rareCount = 0;
            for (Node* n : netlist.getAllNodes()) {
                if (n->rare_value != -1) rareCount++;
            }
            
            auto endTime = std::chrono::high_resolution_clock::now();
            auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(endTime - startTime);
            
            double rarePercent = (rareCount * 100.0) / totalNodes;
            
            csvFile << circuitName << ","
                    << numVec << ","
                    << totalNodes << ","
                    << rareCount << ","
                    << rarePercent << "\n";
            
            std::cout << "  N=" << std::setw(5) << numVec << ": "
                      << rareCount << "/" << totalNodes << " nodes ("
                      << std::fixed << std::setprecision(2) << rarePercent << "%) "
                      << "[" << duration.count() << "ms]\n";
        }
    }
    
    csvFile.close();
    std::cout << "\nResults saved to: validation_fig3.csv\n";
}

// Special Validation for Supervisor for s35932
void validateS35932TransitionCounts() {
    std::cout << "\n=== Validating s35932 Transition Counts (Supervisor Request) ===\n";
    std::string benchPath = "inputs/sequential/s35932.bench";
    if (!fs::exists(benchPath)) {
        std::cout << "Skipping s35932 (not found)\n";
        return;
    }

    Netlist netlist;
    if (!netlist.parse(benchPath)) {
        std::cerr << "Failed to parse " << benchPath << "\n";
        return;
    }
    
    Simulator sim(&netlist);
    int numVectors = 10000;
    // Ensure vector is sized to max ID + 1 to be safe
    int maxId = 0;
    for(Node* n : netlist.getAllNodes()) if(n->id > maxId) maxId = n->id;
    std::vector<int> onesCount(maxId + 1, 0);

    // Run Simulation Locally to get counts
    for (int i = 0; i < numVectors; ++i) {
        sim.clearValues();
        for (Node* in : netlist.getInputs()) in->value = std::rand() % 2;
        for (Node* g : netlist.getGates()) sim.evaluate(g);
        for (Node* out : netlist.getOutputs()) sim.evaluate(out);
        
        for (Node* n : netlist.getAllNodes()) {
            if (n->value == 1) onesCount[n->id]++; 
        }
        if (i % 1000 == 0) std::cout << "Sim " << i << "\r";
    }

    std::vector<double> thresholds = {0.05, 0.10, 0.15, 0.20, 0.25};
    
    std::cout << "\nThreshold Analysis for s35932 (" << numVectors << " vectors):\n";
    std::cout << "Theta | Thresh Count | Nodes Found | Avg Occurrences\n";
    std::cout << "------+--------------+-------------+----------------\n";
    
    for (double th : thresholds) {
        int limit = (int)(numVectors * th);
        long long totalOccurrences = 0;
        int rareNodeCount = 0;
        
        for (Node* n : netlist.getAllNodes()) {
            if (n->type == GateType::INPUT || n->type == GateType::OUTPUT) continue;
            
            int c1 = onesCount[n->id];
            int c0 = numVectors - c1;
            
            if (c1 < limit) {
                totalOccurrences += c1;
                rareNodeCount++;
            } else if (c0 < limit) {
                totalOccurrences += c0;
                rareNodeCount++;
            }
        }
        
        double avg = (rareNodeCount > 0) ? (double)totalOccurrences / rareNodeCount : 0.0;
        std::cout << std::fixed << std::setprecision(2) << th << "  | " 
                  << std::setw(12) << limit << " | " 
                  << std::setw(11) << rareNodeCount << " | " 
                  << std::setw(11) << avg << "\n";
    }
    std::cout << "========================================================\n";
}

int main(int argc, char** argv) {
    std::cout << "========================================\n";
    std::cout << "  Algorithm 1 Validation Tool\n";
    std::cout << "  Paper: Compatibility Graph Assisted HT Insertion\n";
    std::cout << "========================================\n";
    
    // validateFigure2();
    // validateFigure3();
    validateS35932TransitionCounts();
    
    std::cout << "\n=== Validation Complete ===\n";
    // std::cout << "Generated files:\n";
    // std::cout << "  - validation_fig2.csv (Threshold sweep)\n";
    // std::cout << "  - validation_fig3.csv (Vector count sweep)\n";
    
    return 0;
}
