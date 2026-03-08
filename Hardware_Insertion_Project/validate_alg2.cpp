// Experimental Validation Tool for Algorithm 2 (Compatibility Graph & Clique Finding)
// Metrics: Rare nodes, graph density, clique counts, performance, pruning analysis
// Usage: compile and run with benchmark file path

#include "Netlist.h"
#include "Simulator.h"
#include "CompatibilityGraph.h"
#include <iostream>
#include <fstream>
#include <vector>
#include <string>
#include <filesystem>
#include <iomanip>
#include <chrono>
#include <cmath>

namespace fs = std::filesystem;

struct Alg2Metrics {
    std::string circuit;
    int totalNodes;
    int rareNodes;
    int rareNodes1;
    int rareNodes0;
    int validRareNodes; // After PODEM
    int graphNodes;
    int graphEdges;
    double graphDensity;
    int cliqueCount;
    int minCliqueSize;
    double podemTime;
    double graphBuildTime;
    double cliqueFindTime;
    bool pruningOccurred;
};

class Alg2Validator {
public:
    Alg2Validator() {}
    
    Alg2Metrics runValidation(const std::string& benchPath, int cliqueSize, double threshold = 0.10, int numVectors = 10000) {
        Alg2Metrics metrics;
        metrics.circuit = fs::path(benchPath).stem().string();
        metrics.minCliqueSize = cliqueSize;
        
        std::cout << "\n" << std::string(80, '=') << "\n";
        std::cout << "Circuit: " << metrics.circuit << " | Clique Size: q=" << cliqueSize << "\n";
        std::cout << std::string(80, '=') << "\n";
        
        // Step 1: Parse netlist
        Netlist netlist;
        if (!netlist.parse(benchPath)) {
            std::cerr << "Failed to parse " << benchPath << "\n";
            return metrics;
        }
        
        metrics.totalNodes = netlist.getAllNodes().size();
        std::cout << "Total Nodes: " << metrics.totalNodes << "\n";
        
        // Step 2: Algorithm 1 - Find Rare Nodes
        std::cout << "\n[ALGORITHM 1] Finding Rare Nodes...\n";
        Simulator sim(&netlist);
        sim.findRareNodes(numVectors, threshold);
        
        // Count rare nodes
        std::vector<Node*> rareNodeList;
        int rare1 = 0, rare0 = 0;
        for (Node* n : netlist.getAllNodes()) {
            if (n->rare_value != -1) {
                rareNodeList.push_back(n);
                if (n->rare_value == 1) rare1++;
                else rare0++;
            }
        }
        
        metrics.rareNodes = rareNodeList.size();
        metrics.rareNodes1 = rare1;
        metrics.rareNodes0 = rare0;
        
        std::cout << "Rare Nodes: " << metrics.rareNodes 
                  << " (Rare-1: " << rare1 << ", Rare-0: " << rare0 << ")\n";
        
        if (metrics.rareNodes == 0) {
            std::cout << "No rare nodes found. Skipping Algorithm 2.\n";
            return metrics;
        }
        
        // Step 3: Algorithm 2 - Compatibility Graph
        CompatibilityGraph cg(&netlist);
        
        // 3a: Generate Test Vectors (PODEM)
        std::cout << "\n[ALGORITHM 2] Generating Test Vectors (PODEM)...\n";
        // Detect sequential circuits (contain DFF gates) and cap PODEM to 500 nodes
        bool isSequential = false;
        for (Node* g : netlist.getGates()) {
            if (g->type == GateType::DFF) { isSequential = true; break; }
        }
        int limit = isSequential ? 500 : 0;
        auto podemStart = std::chrono::high_resolution_clock::now();
        cg.generateTestVectors(rareNodeList, limit);
        auto podemEnd = std::chrono::high_resolution_clock::now();
        metrics.podemTime = std::chrono::duration<double>(podemEnd - podemStart).count();
        
        // Access private validRareNodes count via reflection (hack: use public interface)
        // We'll infer it from graph construction
        
        // 3b: Build Compatibility Graph
        std::cout << "\n[ALGORITHM 2] Building Compatibility Graph...\n";
        auto graphStart = std::chrono::high_resolution_clock::now();
        cg.buildGraph();
        auto graphEnd = std::chrono::high_resolution_clock::now();
        metrics.graphBuildTime = std::chrono::duration<double>(graphEnd - graphStart).count();
        
        // Get graph statistics
        metrics.validRareNodes = cg.getValidRareNodeCount();
        metrics.graphNodes = cg.getGraphNodeCount();
        metrics.graphEdges = cg.getGraphEdgeCount();
        metrics.graphDensity = cg.getGraphDensity();
        
        std::cout << "Graph Nodes: " << metrics.graphNodes << "\n";
        std::cout << "Graph Edges: " << metrics.graphEdges << "\n";
        std::cout << "Graph Density: " << std::fixed << std::setprecision(4) 
                  << (metrics.graphDensity * 100) << "%\n";
        
        // 3c: Find Cliques
        std::cout << "\n[ALGORITHM 2] Finding Cliques (q=" << cliqueSize << ")...\n";
        auto cliqueStart = std::chrono::high_resolution_clock::now();
        auto cliques = cg.findCliques(cliqueSize);
        auto cliqueEnd = std::chrono::high_resolution_clock::now();
        metrics.cliqueFindTime = std::chrono::duration<double>(cliqueEnd - cliqueStart).count();
        
        metrics.cliqueCount = cliques.size();
        metrics.pruningOccurred = cg.wasPruned();
        
        // Display results
        std::cout << "\n[RESULTS]\n";
        std::cout << "  Cliques Found: " << metrics.cliqueCount << "\n";
        std::cout << "  PODEM Time: " << std::fixed << std::setprecision(3) << metrics.podemTime << "s\n";
        std::cout << "  Graph Build Time: " << metrics.graphBuildTime << "s\n";
        std::cout << "  Clique Find Time: " << metrics.cliqueFindTime << "s\n";
        std::cout << "  Total Time: " << (metrics.podemTime + metrics.graphBuildTime + metrics.cliqueFindTime) << "s\n";
        
        return metrics;
    }
    
    void exportCSV(const std::vector<Alg2Metrics>& results, const std::string& filename) {
        std::ofstream csv(filename);
        csv << "Circuit,TotalNodes,RareNodes,Rare1,Rare0,ValidRareNodes,GraphNodes,GraphEdges,GraphDensity,"
            << "CliqueSize,CliqueCount,PODEMTime,GraphTime,CliqueTime,TotalTime,Pruning\n";
        
        for (const auto& m : results) {
            csv << m.circuit << ","
                << m.totalNodes << ","
                << m.rareNodes << ","
                << m.rareNodes1 << ","
                << m.rareNodes0 << ","
                << m.validRareNodes << ","
                << m.graphNodes << ","
                << m.graphEdges << ","
                << std::fixed << std::setprecision(4) << m.graphDensity << ","
                << m.minCliqueSize << ","
                << m.cliqueCount << ","
                << std::fixed << std::setprecision(3)
                << m.podemTime << ","
                << m.graphBuildTime << ","
                << m.cliqueFindTime << ","
                << (m.podemTime + m.graphBuildTime + m.cliqueFindTime) << ","
                << (m.pruningOccurred ? "Yes" : "No") << "\n";
        }
        
        csv.close();
        std::cout << "\nResults exported to: " << filename << "\n";
    }
};

int main(int argc, char** argv) {
    std::cout << "========================================\n";
    std::cout << "  Algorithm 2 Validation Tool\n";
    std::cout << "  Paper: Compatibility Graph Assisted HT Insertion\n";
    std::cout << "========================================\n";
    
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
    
    // Clique sizes to test (Table IV from paper)
    std::vector<int> cliqueSizes = {2, 4, 6, 8, 10};
    
    Alg2Validator validator;
    std::vector<Alg2Metrics> allResults;
    
    // Run validation for each benchmark and clique size
    for (const auto& benchPath : benchmarks) {
        if (!fs::exists(benchPath)) {
            std::cout << "Skipping " << benchPath << " (not found)\n";
            continue;
        }
        
        for (int q : cliqueSizes) {
            auto metrics = validator.runValidation(benchPath, q);
            if (metrics.rareNodes > 0) {
                allResults.push_back(metrics);
            }
        }
    }
    
    // Export results
    validator.exportCSV(allResults, "validation_alg2_cliques.csv");
    
    std::cout << "\n=== Validation Complete ===\n";
    std::cout << "Generated files:\n";
    std::cout << "  - validation_alg2_cliques.csv (Clique counts and performance)\n";
    
    return 0;
}
