#include "Netlist.h"
#include "Simulator.h"
#include "CompatibilityGraph.h"
#include "TrojanGenerator.h"
#include <iostream>
#include <filesystem>
#include <vector>
#include <string>

namespace fs = std::filesystem;

// Function to process a single bench file
void processFile(const std::string& inputPath, const std::string& outputDir) {
    std::cout << "\n------------------------------------------------------------\n";
    std::cout << "Processing: " << inputPath << "\n";
    std::cout << "------------------------------------------------------------\n";

    Netlist netlist;
    if (!netlist.parse(inputPath)) {
        std::cout << "Failed to parse " << inputPath << "\n";
        return;
    }
    std::cout << "Successfully parsed netlist (" << netlist.getAllNodes().size() << " nodes).\n";

    // Phase 1: Simulation
    Simulator sim(&netlist);
    sim.findRareNodes(10000, 0.10); // θ=0.10: balanced stealth/feasibility (S1)

    std::vector<Node*> rareNodes;
    for(Node* n : netlist.getAllNodes()) {
        if (n->rare_value != -1) rareNodes.push_back(n);
    }
    
    if (rareNodes.empty()) {
        std::cout << "No rare nodes found. Skipping.\n";
        return;
    }

    // Phase 2: PODEM & Compatibility
    CompatibilityGraph cg(&netlist);
    cg.generateTestVectors(rareNodes);
    cg.buildGraph();

    // User Configuration
    std::cout << "\n[Config for " << fs::path(inputPath).filename().string() << "]\n";
    
    // Trigger Size
    std::cout << "Step 1: Select Trigger Size (e.g. 2, 4, 8) [0 to Skip File]: ";
    int trigSize;
    std::cin >> trigSize;
    if (trigSize == 0) return;
    if (trigSize < 2) trigSize = 2; // Safety

    std::cout << "Searching for Cliques of size " << trigSize << "...\n";
    auto cliques = cg.findCliques(trigSize);

    // Fallback logic
    if (cliques.empty()) {
        std::cout << "Warning: No cliques of size " << trigSize << " found. Trying smaller...\n";
        for (int s = trigSize - 1; s >= 2; --s) {
            cliques = cg.findCliques(s);
            if (!cliques.empty()) {
                std::cout << "Fallback: Found clique of size " << s << ".\n";
                trigSize = s;
                break;
            }
        }
    }

    if (cliques.empty()) {
        std::cout << "Error: No viable triggers found. Skipping.\n";
        return;
    }

    // Payload Type
    std::cout << "Step 2: Select TrustHub Payload Type:\n";
    std::cout << "1. Change Functionality (Bit Flip XOR)\n";
    std::cout << "2. Degrade Performance (Triggered Delay)\n";
    std::cout << "3. Denial of Service (Stuck-At-1)\n";
    std::cout << "4. Information Leakage (Leak Internal Node)\n";
    std::cout << "Enter choice [1-4]: ";
    
    int choice;
    std::cin >> choice;
    
    TrojanConfig config;
    config.triggerSize = trigSize; 
    switch(choice) {
        case 2: config.type = TrojanType::PERFORMANCE_DEGRADE_DELAY; break;
        case 3: config.type = TrojanType::DOS_STUCK_AT_1; break;
        case 4: config.type = TrojanType::LEAK_INFORMATION; break;
        default: config.type = TrojanType::FUNCTIONAL_CHANGE_XOR; break;
    }

    // Phase 3: Insert
    TrojanGenerator tg(&netlist);
    Node* trigger = tg.generateTrigger(cliques[0]);
    if (trigger) {
        tg.insertPayload(trigger, config);
        
        // Output path
        fs::path p(inputPath);
        std::string filename = p.stem().string() + "_trojan.bench";
        fs::path outP = fs::path(outputDir) / filename;
        
        netlist.write(outP.string());
        std::cout << "Values saved to: " << outP.string() << "\n";
    }
}

int main(int argc, char** argv) {
    // Single File Mode (Legacy)
    if (argc >= 2) {
        processFile(argv[1], ".");
        return 0;
    }

    // Batch Directory Mode
    std::vector<std::string> directories = {"inputs/combinational", "inputs/sequential"};
    
    std::cout << "============================================\n";
    std::cout << "      Batch Hardware Trojan Framework       \n";
    std::cout << "============================================\n";

    for (const auto& dir : directories) {
        if (!fs::exists(dir)) {
            std::cout << "Directory not found: " << dir << ". creating...\n";
            fs::create_directories(dir);
            continue;
        }

        std::string outDir = "outputs/" + fs::path(dir).filename().string();
        if (!fs::exists(outDir)) fs::create_directories(outDir);

        std::cout << "\nScanning directory: " << dir << "\n";
        int count = 0;
        for (const auto& entry : fs::directory_iterator(dir)) {
            if (entry.path().extension() == ".bench") {
                processFile(entry.path().string(), outDir);
                count++;
            }
        }
        if (count == 0) std::cout << "No .bench files found in " << dir << "\n";
    }
    
    std::cout << "\nBatch Processing Complete.\n";
    return 0;
}
