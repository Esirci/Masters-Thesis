#include "Netlist.h"
#include <vector>

// TrustHub Taxonomy Effects
enum class TrojanType {
    FUNCTIONAL_CHANGE_XOR,      // TrustHub: Functional / Internally Triggered / Change Functionality
    PERFORMANCE_DEGRADE_DELAY,  // TrustHub: Parametric / Internally Triggered / Degrade Performance
    DOS_STUCK_AT_0,             // TrustHub: Functional / Internally Triggered / Denial of Service
    DOS_STUCK_AT_1,             // TrustHub: Functional / Internally Triggered / Denial of Service
    LEAK_INFORMATION            // TrustHub: Functional / Internally Triggered / Leak Information
};

struct TrojanConfig {
    TrojanType type;
    int triggerSize; // Number of rare nodes to use
};

class TrojanGenerator {
public:
    TrojanGenerator(Netlist* netlist);
    
    // Generate trigger logic (Flat or Tree based on size)
    Node* generateTrigger(const std::vector<Node*>& clique);
    
    // Insert payload based on config type
    void insertPayload(Node* trigger, TrojanConfig config);

private:
    Netlist* netlist;
    int nextId = 0; // Tracks the next available ID for node naming
    int initialMaxId = 0; // Max ID of the original netlist to identify original vs. new components

    std::string genName(); // No prefix, just number
    Node* addGate(GateType type, std::vector<Node*> inputs);
};
