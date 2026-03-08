#include "Simulator.h"
#include <cstdlib>
#include <ctime>
#include <iostream>

Simulator::Simulator(Netlist* nl) : netlist(nl) {
    std::srand(std::time(nullptr));
}

void Simulator::clearValues() {
    for (Node* n : netlist->getAllNodes()) {
        n->value = -1;
    }
}

int Simulator::computeGate(GateType type, const std::vector<int>& vals) {
    if (vals.empty() && type != GateType::INPUT) return 0; // Should not happen

    switch (type) {
        case GateType::AND: {
            for (int v : vals) if (v == 0) return 0;
            return 1;
        }
        case GateType::NAND: {
            for (int v : vals) if (v == 0) return 1;
            return 0;
        }
        case GateType::OR: {
            for (int v : vals) if (v == 1) return 1;
            return 0;
        }
        case GateType::NOR: {
            for (int v : vals) if (v == 1) return 0;
            return 1;
        }
        case GateType::NOT:
            return (vals[0] == 0) ? 1 : 0;
        case GateType::BUF:
            return vals[0];
        case GateType::XOR: {
            int result = 0;
            for (int v : vals) result ^= v;
            return result;
        }
        case GateType::XNOR: {
            int result = 0;
            for (int v : vals) result ^= v;
            return !result;
        }
        default:
            return 0;
    }
}

int Simulator::evaluate(Node* node) {
    if (node->value != -1) return node->value;

    std::vector<int> inputVals;
    for (Node* in : node->inputs) {
        inputVals.push_back(evaluate(in));
    }

    node->value = computeGate(node->type, inputVals);
    return node->value;
}

void Simulator::findRareNodes(int numVectors, double thresholdRatio) {
    int threshold = (int)(numVectors * thresholdRatio);
    std::vector<int> onesCount(netlist->getAllNodes().size(), 0);

    for (int i = 0; i < numVectors; ++i) {
        clearValues();
        // Randomize inputs
        for (Node* in : netlist->getInputs()) {
            in->value = std::rand() % 2;
        }

        // Evaluate all gates. Evaluate function handles memoization.
        for (Node* g : netlist->getGates()) {
            evaluate(g);
        }
        for (Node* out : netlist->getOutputs()) {
            evaluate(out);
        }

        // Count
        for (Node* n : netlist->getAllNodes()) {
            if (n->value == 1) {
                onesCount[n->id]++;
            }
        }
        
        if (i % 1000 == 0) std::cout << "Simulation " << i << "/" << numVectors << "\r";
    }
    std::cout << "Simulation completed.                    " << std::endl;

    int rareCount = 0;
    for (Node* n : netlist->getAllNodes()) {
        if (n->type == GateType::INPUT || n->type == GateType::OUTPUT) continue; // Focus on internal nodes
        
        // Check for Rare 1
        if (onesCount[n->id] < threshold) {
            n->rare_value = 1;
            rareCount++;
            // std::cout << "Node " << n->name << " is Rare-1 (Count " << onesCount[n->id] << ")" << std::endl;
        }
        // Check for Rare 0
        else if ((numVectors - onesCount[n->id]) < threshold) {
            n->rare_value = 0;
            rareCount++;
            // std::cout << "Node " << n->name << " is Rare-0 (Count " << (numVectors - onesCount[n->id]) << ")" << std::endl;
        }
    }
    std::cout << "Identified " << rareCount << " rare nodes." << std::endl;
}
