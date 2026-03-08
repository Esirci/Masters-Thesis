#pragma once

#include <string>
#include <vector>
#include <map>
#include <set>
#include <iostream>

enum class GateType {
    INPUT, OUTPUT, AND, NAND, OR, NOR, XOR, XNOR, NOT, BUF, DFF, UNKNOWN
};

struct Node {
    std::string name;
    GateType type = GateType::UNKNOWN;
    std::vector<Node*> inputs;
    std::vector<Node*> outputs;
    int id; // Mapped integer ID for easier graph processing

    // For Simulation/PODEM
    int value = -1;      // Logic value: -1 (X), 0, 1, 2 (D), 3 (D_BAR)
    int rare_value = -1; // Desired rare value (0 or 1) for this node to be a trigger candidate
};

class Netlist {
public:
    Netlist();
    bool parse(const std::string& filename);
    void write(const std::string& filename);
    
    Node* getNode(const std::string& name);
    std::vector<Node*>& getInputs() { return inputs; }
    std::vector<Node*>& getOutputs() { return outputs; }
    std::vector<Node*>& getGates() { return gates; }       // Internal Gates
    std::vector<Node*>& getAllNodes() { return allNodes; } // All Nodes (Inputs + Internal + Outputs)

    // Helper to stringify gate type
    static std::string gateTypeToString(GateType type);
    static GateType stringToGateType(const std::string& str);

    // Dynamic modification helpers
    Node* createGate(const std::string& name, GateType type, const std::vector<Node*>& inputs);
    void replaceOutputNode(Node* oldNode, Node* newNode);
    void renameNode(Node* node, const std::string& newName);
    void shiftIDs(int threshold, int shiftAmount);

private:
    std::vector<Node*> inputs;
    std::vector<Node*> outputs;
    std::vector<Node*> gates;
    std::vector<Node*> allNodes;
    std::map<std::string, Node*> nameToNode;

    Node* getOrCreateNode(const std::string& name);


};

