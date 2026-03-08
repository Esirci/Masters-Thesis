#include "TrojanGenerator.h"
#include <iostream>
#include <algorithm>
#include <cstdlib>
#include <string>
#include <map>
#include <functional>

TrojanGenerator::TrojanGenerator(Netlist* nl) : netlist(nl) {
    // Stealth: Scan for highest ID
    int maxId = 0;
    for (Node* n : netlist->getAllNodes()) {
        try {
            int id = std::stoi(n->name);
            if (id > maxId) maxId = id;
        } catch (...) {
            // Ignore non-numeric names
        }
    }
    nextId = maxId + 1;
    initialMaxId = maxId;
}

std::string TrojanGenerator::genName() {
    return std::to_string(nextId++);
}

Node* TrojanGenerator::generateTrigger(const std::vector<Node*>& clique) {
    // Section 3: Large Clique Optimizations (Multi-Level Tree)
    // If clique size is large (> 8), avoid a massive single AND gate.
    
    if (clique.size() > 8) {
        // Multi-Level Tree Implementation
        // Level 1: Inputs (Rare Nodes)
        // Level 2: Groups of 4 -> AND (for Rare1) / NOR (for Rare0)
        // Level 3: Relaxation -> OR / NAND (to loosen condition)
        // Level 4: Final AND/NOR
        
        std::vector<Node*> level3_outputs;
        
        // Process in chunks of 4
        size_t chunkSize = 4;
        for (size_t i = 0; i < clique.size(); i += chunkSize) {
            std::vector<Node*> chunk;
            for (size_t j = i; j < std::min(i + chunkSize, clique.size()); ++j) {
                chunk.push_back(clique[j]);
            }
            
            std::vector<Node*> rare1_chunk;
            std::vector<Node*> rare0_chunk;
            for (Node* n : chunk) {
                if (n->rare_value == 1) rare1_chunk.push_back(n);
                else rare0_chunk.push_back(n);
            }
            
            // Level 2 Gates
            Node* l2_and = nullptr;
            Node* l2_nor = nullptr;
            if (!rare1_chunk.empty()) l2_and = netlist->createGate(genName(), GateType::AND, rare1_chunk);
            if (!rare0_chunk.empty()) l2_nor = netlist->createGate(genName(), GateType::NOR, rare0_chunk);
            
            // Level 3 Relaxation (Group the groups)
            // Use AND to strictly enforce activation of all sub-groups.
            // Using OR would allow partial activation but compromises rarity.
            // Given PODEM verified compatibility, strict AND ensures validity.
            // However, large cliques might require relaxation for fan-in management.
            // Current strategy: Use AND for validity.
            
            std::vector<Node*> l2_outs;
            if (l2_and) l2_outs.push_back(l2_and);
            if (l2_nor) l2_outs.push_back(l2_nor);
            
            if (!l2_outs.empty()) {
                // Combine outputs from Level 2 gates
                
                Node* chunk_result = nullptr;
                if (l2_outs.size() == 2) chunk_result = netlist->createGate(genName(), GateType::AND, l2_outs);
                else chunk_result = l2_outs[0];
                
                level3_outputs.push_back(chunk_result);
            }
        }
        
        // Level 4: Final Combination
        // Hierarchically AND the chunks to ensure global rarity while respecting fan-in limits.
        
        return netlist->createGate(genName(), GateType::AND, level3_outputs);
        
    } else {
        // Flat Trigger (Original Logic)
        std::vector<Node*> rare1;
        std::vector<Node*> rare0;
        
        for (Node* n : clique) {
            if (n->rare_value == 1) rare1.push_back(n);
            else rare0.push_back(n);
        }
        
        Node* part1 = nullptr;
        if (!rare1.empty()) part1 = netlist->createGate(genName(), GateType::AND, rare1);
        
        Node* part0 = nullptr;
        if (!rare0.empty()) part0 = netlist->createGate(genName(), GateType::NOR, rare0);
        
        if (part1 && part0) return netlist->createGate(genName(), GateType::AND, {part1, part0});
        else if (part1) return part1;
        else if (part0) return part0;
    }
    
    return nullptr;
}

void TrojanGenerator::insertPayload(Node* trigger, TrojanConfig config) {
    if (!trigger) return;
    auto& outputs = netlist->getOutputs();
    if (outputs.empty()) return;
    
    // 1. Victim Selection (Stealth: Downstream)
    int maxSourceId = -1;
    std::map<Node*, bool> visited;
    std::function<void(Node*)> traverse = [&](Node* n) {
        if (visited[n]) return;
        visited[n] = true;
        int id = -1;
        try { id = std::stoi(n->name); } catch(...) {}
        if (id <= initialMaxId) {
            if (id > maxSourceId) maxSourceId = id;
            return;
        }
        for (Node* in : n->inputs) traverse(in);
    };
    traverse(trigger);
    
    std::vector<Node*> candidates;
    for (Node* out : outputs) {
        int id = -1;
        try { id = std::stoi(out->name); } catch(...) {}
        if (id > maxSourceId) candidates.push_back(out);
    }
    if (candidates.empty()) candidates = outputs; // Fallback

    Node* targetOutput = candidates[std::rand() % candidates.size()];
    std::string originalName = targetOutput->name; 
    // Safe ID generation fallback
    int maxIdVal = 0;
    for (Node* n : netlist->getAllNodes()) {
         try {
             int val = std::stoi(n->name);
             if (val > maxIdVal) maxIdVal = val;
         } catch (...) {}
    }
    // If we only have non-numeric (0), ensure we start high enough
    if (maxIdVal < netlist->getAllNodes().size()) maxIdVal = netlist->getAllNodes().size() + 10000;

    int currentId = maxIdVal + 1000;
    int targetId = currentId; // Just use this as base offset if needed

    // Helper to generate distinct names using currentId
    auto makeName = [&](std::string prefix) {
        return std::to_string(currentId++); 
    };
    
    // 2. ID Shifting Preparation
    // Collect Trojan Gates (Trigger + anything generated in generateTrigger)
    std::vector<Node*> trojanGates;
    visited.clear();
    std::function<void(Node*)> collect = [&](Node* n) {
        if (visited[n]) return;
        visited[n] = true;
        int id = -1;
        try { id = std::stoi(n->name); } catch(...) {}
        if (id > initialMaxId) {
            trojanGates.push_back(n);
            for (Node* in : n->inputs) collect(in);
        }
    };
    collect(trigger);
    
    // Determine Gates Needed based on Payload Type
    // Logic Overhead:
    //   XOR:   1 Gate (Wrapper)
    //   DELAY: 8 Gates (Chain + Mux Logic)
    //   DoS:   1-2 Gates (Logic Override)
    
    int numTrojanGates = trojanGates.size();
    int payloadOverhead = 0;
    
    if (config.type == TrojanType::FUNCTIONAL_CHANGE_XOR) payloadOverhead = 1; // Logic Wrapper
    else if (config.type == TrojanType::DOS_STUCK_AT_0) payloadOverhead = 2; // NOT + AND gate
    else if (config.type == TrojanType::DOS_STUCK_AT_1) payloadOverhead = 1; // OR gate
    else if (config.type == TrojanType::PERFORMANCE_DEGRADE_DELAY) {
        // Delay Logic:
        // Mux Logic (3 gates: AND, AND, OR) + NOT + Chain (e.g. 4 buffers)
        // MUX(S, A, B) = (A & !S) | (B & S). 
        // Total = 8 Gates.
        payloadOverhead = 8;
    }
    else if (config.type == TrojanType::LEAK_INFORMATION) {
        // Logic: Output = MUX(Trigger, Original, Secret).
        // Overhead: 4 Gates (NOT + AND + AND + OR).
        payloadOverhead = 4;
    }
    
    int numNeeded = numTrojanGates + payloadOverhead;
    
    std::cout << "Shifting IDs starting at " << targetId << " by " << numNeeded << std::endl;
    netlist->shiftIDs(targetId, numNeeded);
    
    // ... (Existing Renaming Logic) ...
    // 3. Rename Trojan Gates (Fill the gap)
    currentId = targetId;
    
    // Sort for consistency
    std::sort(trojanGates.begin(), trojanGates.end(), [](Node* a, Node* b) {
        return a->id < b->id; // Use internal ID safe for non-numeric names
    });
    
    for (Node* t : trojanGates) {
        netlist->renameNode(t, std::to_string(currentId++));
    }
    
    // 4. Construct Payload
    std::string internalName = std::to_string(currentId++); // Holds original logic
    netlist->renameNode(targetOutput, internalName); // targetOutput is the node with original inputs
    
    std::string finalOutputName = std::to_string(targetId + numNeeded); 
    Node* payloadNode = nullptr;
    
    if (config.type == TrojanType::FUNCTIONAL_CHANGE_XOR) {
        // ...
        payloadNode = netlist->createGate(finalOutputName, GateType::XOR, {targetOutput, trigger});
        std::cout << "Payload: Functional XOR (Rare Flip)" << std::endl;
    }
    else if (config.type == TrojanType::DOS_STUCK_AT_0) {
        // ...
        Node* notTrigger = netlist->createGate(std::to_string(currentId++), GateType::NOT, {trigger}); 
        payloadNode = netlist->createGate(finalOutputName, GateType::AND, {targetOutput, notTrigger});
        std::cout << "Payload: DoS (Stuck-At-0 when Triggered)" << std::endl;
    }
    else if (config.type == TrojanType::DOS_STUCK_AT_1) {
         // ...
         payloadNode = netlist->createGate(finalOutputName, GateType::OR, {targetOutput, trigger});
         std::cout << "Payload: DoS (Stuck-At-1 when Triggered)" << std::endl;
    }
    else if (config.type == TrojanType::PERFORMANCE_DEGRADE_DELAY) {
        // ...
        Node* curr = targetOutput;
        for(int i=0; i<4; ++i) {
             std::string dName = std::to_string(currentId++);
             curr = netlist->createGate(dName, GateType::BUF, {curr});
        }
        Node* delayedSignal = curr;
        
        // 2. Mux: (Original & !Trigger) | (Delayed & Trigger)
        // NOT Trigger
        Node* notTrigger = netlist->createGate(std::to_string(currentId++), GateType::NOT, {trigger});
        // Term 1
        Node* term1 = netlist->createGate(std::to_string(currentId++), GateType::AND, {targetOutput, notTrigger});
        // Term 2
        Node* term2 = netlist->createGate(std::to_string(currentId++), GateType::AND, {delayedSignal, trigger});
        // OR
        payloadNode = netlist->createGate(finalOutputName, GateType::OR, {term1, term2});
        
        std::cout << "Payload: Parametric Delay (4 Buffers inserted on Trigger)" << std::endl;
    }
    else if (config.type == TrojanType::LEAK_INFORMATION) {
        // 1. Pick a "Secret" node to leak.
        // We want a node that is NOT in the Trojan cone and NOT the Victim.
        // Ideally an internal node with ID <= initialMaxId.
        Node* secretNode = nullptr;
        int attempts = 0;
        while (!secretNode && attempts < 100) {
            Node* cand = netlist->getAllNodes()[std::rand() % netlist->getAllNodes().size()];
            // Select candidate ID
            int cId = -1;
            try { cId = std::stoi(cand->name); } catch(...) {}
            if (cId <= initialMaxId && cand != targetOutput && cand != trigger) {
                secretNode = cand;
            }
            attempts++;
        }
        if (!secretNode) secretNode = trigger; // Fallback (Leak whether trigger is active? Pointless but safe)
        
        std::cout << "Selected Secret Node to Leak: " << secretNode->name << std::endl;
        
        // 2. Mux: (Original & !Trigger) | (Secret & Trigger)
        Node* notTrigger = netlist->createGate(std::to_string(currentId++), GateType::NOT, {trigger});
        Node* term1 = netlist->createGate(std::to_string(currentId++), GateType::AND, {targetOutput, notTrigger});
        Node* term2 = netlist->createGate(std::to_string(currentId++), GateType::AND, {secretNode, trigger});
        payloadNode = netlist->createGate(finalOutputName, GateType::OR, {term1, term2});
        
        std::cout << "Payload: Information Leak (Muxing Secret Node " << secretNode->name << " onto Output " << finalOutputName << ")" << std::endl;
    }
    
    // Default fallback
    if (!payloadNode) payloadNode = netlist->createGate(finalOutputName, GateType::XOR, {targetOutput, trigger});
    
    netlist->replaceOutputNode(targetOutput, payloadNode);
    
    // Explanation Report
    std::cout << "\n[Trojan Insertion Report]\n";
    std::cout << "-------------------------\n";
    std::cout << "Type: ";
    if (config.type == TrojanType::PERFORMANCE_DEGRADE_DELAY) std::cout << "Performance Degradation (Delay)";
    else if (config.type == TrojanType::DOS_STUCK_AT_1) std::cout << "Denial of Service (Stuck-At-1)";
    else if (config.type == TrojanType::DOS_STUCK_AT_0) std::cout << "Denial of Service (Stuck-At-0)";
    else if (config.type == TrojanType::LEAK_INFORMATION) std::cout << "Information Leakage";
    else std::cout << "Functional Change (Bit Flip)";
    std::cout << "\nTrigger: " << trigger->name << " (Inputs: " << trojanGates.size() << " gates)\n";
    std::cout << "Victim: " << originalName << " (Renamed to " << internalName << ")\n";
    std::cout << "Location: Output " << finalOutputName << "\n";
    std::cout << "Effect: When Trigger(Rare) fires, Output is ";
    if (config.type == TrojanType::PERFORMANCE_DEGRADE_DELAY) std::cout << "routed through 4 extra buffers.\n";
    else if (config.type == TrojanType::DOS_STUCK_AT_1) std::cout << "forced to Logic 1.\n";
    else if (config.type == TrojanType::DOS_STUCK_AT_0) std::cout << "forced to Logic 0.\n";
    else if (config.type == TrojanType::LEAK_INFORMATION) std::cout << "replaced by internal Secret Node.\n";
    else std::cout << "inverted (XOR).\n";
    std::cout << "-------------------------\n";
}
