#pragma once
#include "Netlist.h"
#include <vector>

class Simulator {
public:
    Simulator(Netlist* netlist);
    
    // Returns 0 or 1
    int evaluate(Node* node);
    
    // Clears values (sets to -1) for all nodes
    void clearValues();

    // Runs Monte Carlo simulation to identify rare nodes.
    // numVectors: Number of random patterns to simulate.
    // thresholdRatio: Rarity threshold (e.g., 0.2 for < 20% transition probability).
    void findRareNodes(int numVectors, double thresholdRatio);

private:
    Netlist* netlist;
    
    // Helpers
    int computeGate(GateType type, const std::vector<int>& inputVals);
};
