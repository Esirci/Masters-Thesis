#include "Netlist.h"
#include <fstream>
#include <sstream>
#include <algorithm>
#include <regex>
#include <map>
#include <queue>
#include <functional>
#include <fstream>

Netlist::Netlist() {}

Node* Netlist::getOrCreateNode(const std::string& name) {
    if (nameToNode.find(name) == nameToNode.end()) {
        Node* n = new Node();
        n->name = name;
        n->id = allNodes.size();
        allNodes.push_back(n);
        nameToNode[name] = n;
    }
    return nameToNode[name];
}

Node* Netlist::getNode(const std::string& name) {
    if (nameToNode.find(name) != nameToNode.end()) {
        return nameToNode[name];
    }
    return nullptr;
}

GateType Netlist::stringToGateType(const std::string& str) {
    std::string s = str;
    std::transform(s.begin(), s.end(), s.begin(), ::toupper);
    if (s == "INPUT") return GateType::INPUT;
    if (s == "OUTPUT") return GateType::OUTPUT;
    if (s == "BUFF" || s == "BUF") return GateType::BUF;
    if (s == "NOT") return GateType::NOT;
    if (s == "AND") return GateType::AND;
    if (s == "NAND") return GateType::NAND;
    if (s == "OR") return GateType::OR;
    if (s == "NOR") return GateType::NOR;
    if (s == "XOR") return GateType::XOR;
    if (s == "XNOR") return GateType::XNOR;
    if (s == "DFF") return GateType::DFF;
    return GateType::UNKNOWN;
}

std::string Netlist::gateTypeToString(GateType type) {
    switch (type) {
        case GateType::INPUT: return "INPUT";
        case GateType::OUTPUT: return "OUTPUT";
        case GateType::BUF: return "BUFF"; // Standardize on BUFF to match parsed format
        case GateType::NOT: return "NOT";
        case GateType::AND: return "AND";
        case GateType::NAND: return "NAND";
        case GateType::OR: return "OR";
        case GateType::NOR: return "NOR";
        case GateType::XOR: return "XOR";
        case GateType::XNOR: return "XNOR";
        case GateType::DFF: return "DFF";
        default: return "UNKNOWN";
    }
}

bool Netlist::parse(const std::string& filename) {
    std::ifstream file(filename);
    if (!file.is_open()) {
        std::cerr << "Error: Could not open file " << filename << std::endl;
        return false;
    }

    std::string line;
    std::regex inputRegex(R"(INPUT\s*\((.+)\))");
    std::regex outputRegex(R"(OUTPUT\s*\((.+)\))");
    std::regex gateRegex(R"((.+)\s*=\s*([A-Za-z]+)\s*\((.+)\))");

    while (std::getline(file, line)) {
        // Remove comments
        size_t commentPos = line.find('#');
        if (commentPos != std::string::npos) {
            line = line.substr(0, commentPos);
        }
        
        // Trim whitespace
        line.erase(0, line.find_first_not_of(" \t\r\n"));
        line.erase(line.find_last_not_of(" \t\r\n") + 1);

        if (line.empty()) continue;

        std::smatch match;
        if (std::regex_match(line, match, inputRegex)) {
            std::string name = match[1];
            Node* n = getOrCreateNode(name);
            n->type = GateType::INPUT;
            inputs.push_back(n);
        } else if (std::regex_match(line, match, outputRegex)) {
            std::string name = match[1];
            Node* n = getOrCreateNode(name);
            // Outputs are tracked separately but are also nodes in the netlist
            outputs.push_back(n);
        } else if (std::regex_match(line, match, gateRegex)) {
            std::string outName = match[1];
            std::string typeStr = match[2];
            std::string inList = match[3];

            // Trim outName
            outName.erase(0, outName.find_first_not_of(" "));
            outName.erase(outName.find_last_not_of(" ") + 1);

            Node* outNode = getOrCreateNode(outName);
            outNode->type = stringToGateType(typeStr);
            
            // If it's DFF:
            // 1. Logic Output (Q) is Pseudo-Primary Input (PPI)
            // 2. Logic Input (D) is Pseudo-Primary Output (PPO)
            if (outNode->type == GateType::DFF) {
                inputs.push_back(outNode);
                
                // Logic Input (D) is PPO. 
                // The input list is parsed below.
            }
            
            // If it's not marked as an input, add to gates list
            gates.push_back(outNode);

            std::stringstream ss(inList);
            std::string segment;
            while (std::getline(ss, segment, ',')) {
                // Trim segment
                segment.erase(0, segment.find_first_not_of(" "));
                segment.erase(segment.find_last_not_of(" ") + 1);
                
                Node* inNode = getOrCreateNode(segment);
                outNode->inputs.push_back(inNode);
                inNode->outputs.push_back(outNode);
                
                // If this gate is DFF, then 'inNode' is driving it. 
                // That makes 'inNode' a PPO (Pseudo-Primary Output).
                if (outNode->type == GateType::DFF) {
                    bool distinct = true;
                    for(auto* o : outputs) if(o == inNode) distinct = false;
                    if(distinct) outputs.push_back(inNode);
                }
            }
        }
    }
    
    file.close();
    std::cout << "Parsed " << inputs.size() << " inputs, " << outputs.size() << " outputs, " << gates.size() << " gates." << std::endl;
    return true;
}

void Netlist::write(const std::string& filename) {
    std::ofstream file(filename);
    if (!file.is_open()) return;

    file << "# Generated by Trojan Insertion Framework\n";
    
    // 1. Write Inputs
    // Sort inputs for cleanliness
    std::sort(inputs.begin(), inputs.end(), [](Node* a, Node* b) {
        return a->name < b->name; // Lexicographical is standard for inputs usually
    });

    for (Node* n : inputs) {
        file << "INPUT(" << n->name << ")\n";
    }
    file << "\n";
    
    // 2. Write Outputs
    std::sort(outputs.begin(), outputs.end(), [](Node* a, Node* b) {
        return a->name < b->name;
    });

    for (Node* n : outputs) {
        file << "OUTPUT(" << n->name << ")\n";
    }
    file << "\n";

    // 3. Topological Sort for Gates with Lookahead Priority
    // Goal: Use Kahn's algorithm or DFS to order gates.
    // Metric: EffectiveID(n) = min(ID(n), EffectiveID(successors)).
    
    // Build full graph first
    // Build strict DAG by breaking loops at DFFs
    std::map<Node*, int> dependencyCount;
    std::map<Node*, std::vector<Node*>> fanoutGraph;
    
    for (Node* g : gates) {
        if (g->type == GateType::INPUT) continue;
        dependencyCount[g] = 0;
    }
    
    for (Node* g : gates) {
        if (g->type == GateType::INPUT) continue;
        
        // BREAK CYCLES: DFFs are treated as Pseudo-Inputs for sorting.
        // This effectively breaks feedback loops in sequential circuits.
        if (g->type == GateType::DFF) continue;

        for (Node* in : g->inputs) {
            if (in->type != GateType::INPUT) {
                fanoutGraph[in].push_back(g);
                dependencyCount[g]++;
            }
        }
    }

    // Compute Effective IDs (Memoized DFS with Cycle Detection)
    std::map<Node*, int> effectiveIDs;
    std::map<Node*, bool> visited; 
    std::map<Node*, bool> onStack;
    
    std::function<int(Node*)> getEffectiveID = [&](Node* n) -> int {
        if (n->type == GateType::INPUT) return 0;
        if (visited[n]) return effectiveIDs[n];
        if (onStack[n]) {
             // Cycle detected: Return self ID to recover
             try { return std::stoi(n->name); } catch(...) { return 999999; }
        }
        
        onStack[n] = true;

        int myID = 999999;
        try { myID = std::stoi(n->name); } catch(...) {}
        
        int minNext = myID;
        
        if (fanoutGraph.find(n) != fanoutGraph.end()) {
            for (Node* out : fanoutGraph[n]) {
                int outID = getEffectiveID(out);
                if (outID < minNext) minNext = outID;
            }
        }
        
        onStack[n] = false;
        visited[n] = true;
        effectiveIDs[n] = minNext;
        return minNext;
    };
    
    for (Node* g : gates) {
        if (g->type == GateType::INPUT) continue;
        try {
             getEffectiveID(g);
        } catch (...) {
             // Fallback
             effectiveIDs[g] = 999999;
        }
    }
    
    // Priority Queue using Effective ID
    auto cmp = [&](Node* a, Node* b) {
        int ia = effectiveIDs[a];
        int ib = effectiveIDs[b];
        
        if (ia != ib) return ia > ib; // Min-Heap
        return a->name > b->name;
    };
    
    std::priority_queue<Node*, std::vector<Node*>, decltype(cmp)> readyQueue(cmp);
    
    for (auto const& [node, count] : dependencyCount) {
        if (count == 0) readyQueue.push(node);
    }
    
    while(!readyQueue.empty()) {
        Node* curr = readyQueue.top();
        readyQueue.pop();
        
        file << curr->name << " = " << gateTypeToString(curr->type) << "(";
        for (size_t i = 0; i < curr->inputs.size(); ++i) {
            file << curr->inputs[i]->name;
            if (i < curr->inputs.size() - 1) file << ", ";
        }
        file << ")\n";
        
        for (Node* dependent : fanoutGraph[curr]) {
            dependencyCount[dependent]--;
            if (dependencyCount[dependent] == 0) {
                readyQueue.push(dependent);
            }
        }
    }

    file.close();
}

Node* Netlist::createGate(const std::string& name, GateType type, const std::vector<Node*>& layerInputs) {
    Node* n = getOrCreateNode(name);
    n->type = type;
    n->inputs = layerInputs;
    
    // Update fanout for inputs
    for (Node* in : layerInputs) {
        in->outputs.push_back(n);
    }
    
    gates.push_back(n);
    return n;
}

void Netlist::replaceOutputNode(Node* oldNode, Node* newNode) {
    for (size_t i = 0; i < outputs.size(); ++i) {
        if (outputs[i] == oldNode) {
            outputs[i] = newNode;
            break;
        }
    }
    // Also, newNode is technically a gate (XOR), so it's in 'gates'.
    // OldNode (now _int) is also in 'gates'. 
    // Logic is consistent.
}

void Netlist::renameNode(Node* node, const std::string& newName) {
    // Remove old entry
    auto it = nameToNode.find(node->name);
    if (it != nameToNode.end()) {
        nameToNode.erase(it);
    }
    
    // Update name
    node->name = newName;
    
    // Add new entry
    nameToNode[newName] = node;
}

void Netlist::shiftIDs(int threshold, int shiftAmount) {
    // We need to iterate over all nodes, find those with ID >= threshold, and shift them.
    // Iterating map is dangerous if we modify it.
    // Collect candidates first.
    std::vector<Node*> toShift;
    
    for (auto const& [name, node] : nameToNode) {
        int id = -1;
        try { id = std::stoi(name); } catch(...) {}
        
        if (id >= threshold) {
            toShift.push_back(node);
        }
    }
    
    // Sort descending to shift highest first to avoid temporary/stale ID collisions
    std::sort(toShift.begin(), toShift.end(), [](Node* a, Node* b) {
        int ia = std::stoi(a->name);
        int ib = std::stoi(b->name);
        return ia > ib;
    });
    
    for (Node* n : toShift) {
        int oldId = std::stoi(n->name);
        std::string newName = std::to_string(oldId + shiftAmount);
        renameNode(n, newName);
    }
}

