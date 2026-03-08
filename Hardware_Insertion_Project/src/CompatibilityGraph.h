#pragma once
#include "Netlist.h"
#include "PODEM.h"
#include <vector>
#include <map>
#include <set>

class CompatibilityGraph {
public:
    CompatibilityGraph(Netlist* netlist);
    
    // 1. Run PODEM on all rare nodes to get test vectors
    void generateTestVectors(const std::vector<Node*>& rareNodes, int maxSuccessful = 0);
    
    // 2. Build graph (edges between compatible nodes)
    void buildGraph();
    
    // 3. Find cliques of size k (or max cliques)
    // Returns a list of cliques, where each clique is a vector of Nodes.
    std::vector<std::vector<Node*>> findCliques(int minSize);
    
    // Validation/Statistics Methods
    int getValidRareNodeCount() const { return validRareNodes.size(); }
    int getGraphNodeCount() const { return validRareNodes.size(); }
    int getGraphEdgeCount() const;
    double getGraphDensity() const;
    bool wasPruned() const { return pruningOccurred; }
    long long getRecursionCount() const { return recursionCount; }
    
    // Helper to get test vector for a specific rare node (for verification)
    const std::map<Node*, int>& getTestVector(Node* rareNode) {
        return testVectors[rareNode];
    }

private:
    Netlist* netlist;
    PODEM podem;
    
    // Map: RareNode -> Test Vector (Map Input -> 0/1)
    std::map<Node*, std::map<Node*, int>> testVectors;
    std::vector<Node*> validRareNodes; // Nodes where PODEM succeeded

    // Adjacency List for Compatibility Graph
    std::map<int, std::set<int>> adj; // Key: Node ID, Value: Set of Neighbor IDs

    bool areVectorsCompatible(const std::map<Node*, int>& v1, const std::map<Node*, int>& v2);
    
    // Clique finding helper (Bron-Kerbosch)
    void bronKerbosch(std::set<int> R, std::set<int> P, std::set<int> X, 
                      std::vector<std::vector<Node*>>& cliques, int minSize);

    long long recursionCount = 0;
    bool pruningOccurred = false;
};
