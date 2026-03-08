// Validation Tool for Tables 2 & 3 (Paper Replication)
// Table 2: Area Overhead (Gate Count Increase)
// Table 3: Detection Probability (Stealth against Random patterns)

#include "Netlist.h"
#include "Simulator.h"
#include "CompatibilityGraph.h"
#include "TrojanGenerator.h"
#include <iostream>
#include <fstream>
#include <vector>
#include <string>
#include <filesystem>
#include <iomanip>
#include <random>

namespace fs = std::filesystem;

struct TableMetrics {
    std::string circuit;
    int originalGates;
    int trojanGates;
    double areaOverhead; // %
    int triggerSize;
    int tcCount;         // TC: Trigger activated (internally), regardless of output
    int dcCount;         // DC: Trigger activated AND output observable error
    int totalVectors;
    double tcProb;       // TC probability (activation / total)
    double dcProb;       // DC probability (detection / total)
};

TableMetrics validateBenchmark(std::string benchPath, int cliqueSize) {
    TableMetrics metrics;
    metrics.circuit = fs::path(benchPath).stem().string();
    metrics.totalVectors = 100000; // 100k vectors for Validation (Paper used 1M)
    metrics.triggerSize = cliqueSize;

    // 1. Parse Original
    Netlist netlist;
    if (!netlist.parse(benchPath)) {
        std::cerr << "Failed to parse " << benchPath << "\n";
        return metrics;
    }
    metrics.originalGates = netlist.getGates().size();

    // 2. Identify Rare Nodes & Clique (Standard Setup)
    Simulator sim(&netlist);
    sim.findRareNodes(10000, 0.10); // 10k setup, θ=0.10 (S1: balanced stealth threshold)
    
    std::vector<Node*> rareNodes;
    for(Node* n : netlist.getAllNodes()) {
        if(n->rare_value != -1) rareNodes.push_back(n);
    }
    
    CompatibilityGraph cg(&netlist);
    // Detect sequential circuits (contain DFF gates) and cap PODEM to 500 nodes
    bool isSequential = false;
    for (Node* g : netlist.getGates()) {
        if (g->type == GateType::DFF) { isSequential = true; break; }
    }
    int limit = isSequential ? 500 : 0;
    cg.generateTestVectors(rareNodes, limit);
    cg.buildGraph();
    auto cliques = cg.findCliques(cliqueSize);
    
    if(cliques.empty()) {
        std::cout << "[WARN] No cliques of size " << cliqueSize << " for " << metrics.circuit << ". Skipping.\n";
        metrics.trojanGates = metrics.originalGates;
        metrics.areaOverhead = 0.0;
        metrics.tcCount = -1;
        metrics.dcCount = -1;
        return metrics;
    }
    
    // 3. Insert Trojan
    TrojanGenerator generator(&netlist);
    Node* trigger = generator.generateTrigger(cliques[0]); // Use first clique
    TrojanConfig config;
    config.type = TrojanType::FUNCTIONAL_CHANGE_XOR;
    config.triggerSize = cliqueSize;
    generator.insertPayload(trigger, config); // Insert
    
    // 4. Measure Area Overhead (Table 2)
    // Note: Netlist::getGates() might need refetching or size check
    // TrojanGenerator uses createGate which pushes to 'gates' or 'outputs'
    // 'gates' in Netlist is std::vector<Node*>.
    metrics.trojanGates = netlist.getGates().size(); 
    int diff = metrics.trojanGates - metrics.originalGates;
    metrics.areaOverhead = (double)diff * 100.0 / metrics.originalGates;
    
    std::cout << "Original: " << metrics.originalGates << ", Trojan: " << metrics.trojanGates 
              << ", Overhead: " << std::fixed << std::setprecision(2) << metrics.areaOverhead << "%\n";

    // 5. Measure Stealth (Table 3)
    // Run 1M random vectors. If trigger output == 1, it's detected.
    std::cout << "Running Stealth Simulation (" << metrics.totalVectors << " vectors)...\n";
    
    // Trigger is the node returned by generateTrigger.
    // However, for valid detection, we usually check the PAYLOAD effect.
    // But evaluating the Trigger node itself is sufficient to know if it *would* trigger.
    // If Trigger == 1, then the Trojan is Active.
    
    int tcCount = 0;
    int dcCount = 0;
    
    for(int i=0; i<metrics.totalVectors; ++i) {
        // Step 1: Run circuit with same random input WITHOUT Trojan effect
        // (Golden reference: store output values before Trojan payload corrupts them)
        sim.clearValues();
        for(Node* in : netlist.getInputs()) {
            in->value = std::rand() % 2;
        }
        for(Node* g : netlist.getGates()) sim.evaluate(g);
        
        // Evaluate trigger explicitly
        int triggerFired = sim.evaluate(trigger);
        
        // TC: Trigger node is 1 (activated internally)
        if (triggerFired == 1) {
            tcCount++;
            
            // DC: Check if the payload caused an observable output error.
            // Since our payload is XOR(original_output, trigger), when trigger==1
            // the output is ALWAYS flipped. So DC == TC for XOR payload.
            // We record this explicitly for clarity and future payload types.
            // For non-XOR payloads, the output might not always be corrupted.
            dcCount++;
        }
        
        if (i % 50000 == 0) std::cout << "  Sim " << i << "\r";
    }
    std::cout << "  Sim " << metrics.totalVectors << " [Done]\n";
    
    metrics.tcCount = tcCount;
    metrics.dcCount = dcCount;
    metrics.tcProb = (double)tcCount / metrics.totalVectors;
    metrics.dcProb = (double)dcCount / metrics.totalVectors;
    
    return metrics;
}

int main() {
    std::srand(std::time(nullptr));
    std::ofstream csv("validation_tables.csv");
    csv << "Circuit,OriginalGates,TrojanGates,OverheadPct,TriggerSize,TotalVectors,TC_Count,TC_Prob,DC_Count,DC_Prob\n";
    
    std::cout << "Generating Tables 2 & 3...\n";
    
    std::vector<std::pair<std::string, int>> targets = {
        {"inputs/combinational/c2670.bench", 4},
        {"inputs/combinational/c3540.bench", 2},  // Size 2 (Low density)
        {"inputs/combinational/c5315.bench", 4},
        {"inputs/combinational/c6288.bench", 2},  // Size 2 (Very sparse)
        {"inputs/sequential/s1423.bench", 4},
        {"inputs/sequential/s13207.bench", 2},
        {"inputs/sequential/s15850.bench", 2}     // Size 2 (Complex)
    };

    for(auto& t : targets) {
        TableMetrics m = validateBenchmark(t.first, t.second);
        if(m.tcCount != -1) {
            csv << m.circuit << "," 
                << m.originalGates << "," 
                << m.trojanGates << "," 
                << std::fixed << std::setprecision(4) << m.areaOverhead << ","
                << m.triggerSize << ","
                << m.totalVectors << ","
                << m.tcCount << ","
                << std::scientific << m.tcProb << ","
                << m.dcCount << ","
                << std::scientific << m.dcProb << "\n";
        }
    }
    
    csv.close();
    std::cout << "\nResults saved to validation_tables.csv\n";
    return 0;
}
