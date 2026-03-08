#include "CompatibilityGraph.h"
#include <iostream>
#include <thread>
#include <atomic>
#include <utility>

CompatibilityGraph::CompatibilityGraph(Netlist* nl) : netlist(nl), podem(nl) {}

void CompatibilityGraph::generateTestVectors(const std::vector<Node*>& rareNodes, int maxSuccessful) {
    std::cout << "Generating Test Vectors for " << rareNodes.size() << " rare nodes..." << std::endl;

    int numThreads = std::max(1, (int)std::thread::hardware_concurrency());
    numThreads = std::min(numThreads, (int)rareNodes.size());

    if (maxSuccessful > 0)
        std::cout << "  (Capped at " << maxSuccessful << " successful vectors, " << numThreads << " threads)" << std::endl;
    else
        std::cout << "  (Using " << numThreads << " parallel threads)" << std::endl;

    // Distribute nodes round-robin across threads
    std::vector<std::vector<Node*>> chunks(numThreads);
    for (size_t i = 0; i < rareNodes.size(); ++i)
        chunks[i % numThreads].push_back(rareNodes[i]);

    // Per-thread local results (no mutex on hot path)
    std::vector<std::vector<std::pair<Node*, std::map<Node*, int>>>> threadResults(numThreads);
    std::vector<std::vector<Node*>> threadValid(numThreads);

    std::atomic<int> totalSuccess(0);
    std::atomic<bool> earlyStop(false);

    std::vector<std::thread> threads;
    for (int t = 0; t < numThreads; ++t) {
        threads.emplace_back([this, t, &chunks, &threadResults, &threadValid,
                              &totalSuccess, &earlyStop, maxSuccessful]() {
            PODEM localPodem(netlist); // Own PODEM state per thread — thread safe

            for (Node* node : chunks[t]) {
                if (earlyStop.load(std::memory_order_relaxed)) break;
                if (node->rare_value == -1) continue;

                auto vec = localPodem.generateTest(node, node->rare_value);
                if (!vec.empty()) {
                    threadResults[t].push_back({node, vec});
                    threadValid[t].push_back(node);
                    int prev = totalSuccess.fetch_add(1, std::memory_order_relaxed);
                    if (maxSuccessful > 0 && prev + 1 >= maxSuccessful)
                        earlyStop.store(true, std::memory_order_relaxed);
                }
            }
        });
    }
    for (auto& th : threads) th.join();

    // Merge results from all threads
    int total = totalSuccess.load();
    for (int t = 0; t < numThreads; ++t) {
        for (auto& [node, vec] : threadResults[t]) testVectors[node] = vec;
        for (Node* n : threadValid[t]) validRareNodes.push_back(n);
    }

    if (maxSuccessful > 0 && total >= maxSuccessful)
        std::cout << "  Early stop: reached " << maxSuccessful << " successful vectors.      " << std::endl;
    std::cout << "PODEM finished. Generated vectors for " << total << " nodes.         " << std::endl;
}

bool CompatibilityGraph::areVectorsCompatible(const std::map<Node*, int>& v1, const std::map<Node*, int>& v2) {
    // Check conflicts
    // Iterate over v1 keys
    for (auto const& [input, val1] : v1) {
        if (v2.count(input)) {
            if (v2.at(input) != val1) return false; // Conflict
        }
    }
    return true;
}

void CompatibilityGraph::buildGraph() {
    std::cout << "Building Compatibility Graph..." << std::endl;
    int edgeCount = 0;
    
    for (size_t i = 0; i < validRareNodes.size(); ++i) {
        for (size_t j = i + 1; j < validRareNodes.size(); ++j) {
            Node* n1 = validRareNodes[i];
            Node* n2 = validRareNodes[j];
            
            if (areVectorsCompatible(testVectors[n1], testVectors[n2])) {
                adj[n1->id].insert(n2->id);
                adj[n2->id].insert(n1->id);
                edgeCount++;
            }
        }
    }
    std::cout << "Graph built. Edges: " << edgeCount << std::endl;
}

// In BronKerbosch
void CompatibilityGraph::bronKerbosch(std::set<int> R, std::set<int> P, std::set<int> X, 
                                      std::vector<std::vector<Node*>>& cliques, int minSize) {
    // Safety Break (Result Limit)
    if (cliques.size() > 1000) {
        pruningOccurred = true;
        return;
    }

    // Safety Break (Recursion Limit)
    recursionCount++;
    if (recursionCount % 10000 == 0) std::cout << "Clique Search Step: " << recursionCount << "\r";
    if (recursionCount > 50000) {
        pruningOccurred = true;
        return;
    }

    if (P.empty() && X.empty()) {
        if (R.size() >= (size_t)minSize) {
            std::vector<Node*> clique;
            // Map IDs back to Node pointers
            auto& allNodes = netlist->getAllNodes();
            for (int id : R) clique.push_back(allNodes[id]);
            cliques.push_back(clique);
        }
        return;
    }
    
    // Pivot selection (simple)
    // if (!P.empty()) ... optimization
    
    // Copy P to iterate safely
    std::set<int> Pi = P;
    
    for (int v : Pi) {
        // Double check recursion limit inside loop to break early
        if (recursionCount > 1000000) {
            pruningOccurred = true;
            break;
        }

        std::set<int> newR = R; newR.insert(v);
        
        std::set<int> newP;
        for (int p : P) if (adj[v].count(p)) newP.insert(p);
        
        std::set<int> newX;
        for (int x : X) if (adj[v].count(x)) newX.insert(x);
        
        bronKerbosch(newR, newP, newX, cliques, minSize);
        
        P.erase(v);
        X.insert(v);
    }
}

std::vector<std::vector<Node*>> CompatibilityGraph::findCliques(int minSize) {
    std::cout << "Finding Cliques (Min Size " << minSize << ")..." << std::endl;
    std::vector<std::vector<Node*>> cliques;
    
    std::set<int> R;
    std::set<int> P;
    std::set<int> X;
    
    for (Node* n : validRareNodes) P.insert(n->id);
    
    recursionCount = 0; // Reset counter
    pruningOccurred = false; // Reset flag
    bronKerbosch(R, P, X, cliques, minSize);
    
    if (recursionCount > 50000) {
        std::cout << "\nWarning: Clique finding terminated early (Limit 50k reached)." << std::endl;
    }

    std::cout << "Found " << cliques.size() << " cliques." << std::endl;
    return cliques;
}

int CompatibilityGraph::getGraphEdgeCount() const {
    int edgeCount = 0;
    for (const auto& [nodeId, neighbors] : adj) {
        edgeCount += neighbors.size();
    }
    return edgeCount / 2; // Each edge counted twice in adjacency list
}

double CompatibilityGraph::getGraphDensity() const {
    int V = validRareNodes.size();
    if (V <= 1) return 0.0;
    
    int E = getGraphEdgeCount();
    int maxEdges = (V * (V - 1)) / 2;
    
    return (double)E / maxEdges;
}
