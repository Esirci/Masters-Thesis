#include "PODEM.h"
#include <algorithm>
#include <iostream>

PODEM::PODEM(Netlist* nl) : netlist(nl) {}

// === 5-Valued Logic Helpers ===

LogicVal PODEM::notVal(LogicVal v) {
    switch(v) {
        case LogicVal::ZERO: return LogicVal::ONE;
        case LogicVal::ONE: return LogicVal::ZERO;
        case LogicVal::D: return LogicVal::D_BAR;
        case LogicVal::D_BAR: return LogicVal::D;
        default: return LogicVal::X;
    }
}

LogicVal PODEM::andVal(LogicVal a, LogicVal b) {
    if (a == LogicVal::ZERO || b == LogicVal::ZERO) return LogicVal::ZERO;
    if (a == LogicVal::ONE) return b;
    if (b == LogicVal::ONE) return a;
    if (a == LogicVal::D && b == LogicVal::D_BAR) return LogicVal::ZERO;
    if (a == LogicVal::D_BAR && b == LogicVal::D) return LogicVal::ZERO;
    if (a == LogicVal::D_BAR && b == LogicVal::D) return LogicVal::ZERO;
    
    // X dominates typically, but strict accumulation is handled by caller
    return LogicVal::X; 
}

LogicVal PODEM::orVal(LogicVal a, LogicVal b) {
    if (a == LogicVal::ONE || b == LogicVal::ONE) return LogicVal::ONE;
    if (a == LogicVal::ZERO) return b;
    if (b == LogicVal::ZERO) return a;
    if (a == LogicVal::D && b == LogicVal::D_BAR) return LogicVal::ONE;
    if (a == LogicVal::D_BAR && b == LogicVal::D) return LogicVal::ONE;
    return LogicVal::X;
}

LogicVal PODEM::xorVal(LogicVal a, LogicVal b) {
    /* Full 5-Valued XOR Logic
       Table:
            0    1    D    D'   X
       0    0    1    D    D'   X
       1    1    0    D'   D    X
       D    D    D'   0    1    X
       D'   D'   D    1    0    X
       X    X    X    X    X    X
    */

    if (a == LogicVal::X || b == LogicVal::X) return LogicVal::X;

    // Normalize to integer representation for lookups? Or just if-else.
    
    // Case 0:
    if (a == LogicVal::ZERO) return b;
    if (b == LogicVal::ZERO) return a;
    
    // Case 1:
    if (a == LogicVal::ONE) return notVal(b);
    if (b == LogicVal::ONE) return notVal(a);
    
    // Case D:
    if (a == LogicVal::D) {
        if (b == LogicVal::D) return LogicVal::ZERO;      // D ^ D = 0
        if (b == LogicVal::D_BAR) return LogicVal::ONE;   // D ^ D' = 1
    }
    
    // Case D_BAR:
    if (a == LogicVal::D_BAR) {
        if (b == LogicVal::D) return LogicVal::ONE;       // D' ^ D = 1
        if (b == LogicVal::D_BAR) return LogicVal::ZERO;  // D' ^ D' = 0
    }

    return LogicVal::X; // Should not reach here if all covered
}

LogicVal PODEM::computeGateObj(GateType type, const std::vector<LogicVal>& inputs) {
    if (inputs.empty()) return LogicVal::X;
    
    LogicVal res;
    if (type == GateType::AND || type == GateType::NAND) res = LogicVal::ONE;
    else if (type == GateType::OR || type == GateType::NOR) res = LogicVal::ZERO;
    else if (type == GateType::XOR || type == GateType::XNOR) res = LogicVal::ZERO; // Base for XOR accumulation
    else if (type == GateType::BUF || type == GateType::NOT) res = inputs[0];

    // Accumulate
    if (type == GateType::AND || type == GateType::NAND) {
        for (auto v : inputs) res = andVal(res, v);
    } 
    else if (type == GateType::OR || type == GateType::NOR) {
        for (auto v : inputs) res = orVal(res, v);
    }
    else if (type == GateType::XOR || type == GateType::XNOR) {
        res = inputs[0];
        for (size_t i = 1; i < inputs.size(); ++i) res = xorVal(res, inputs[i]);
    }

    // Invert if needed
    if (type == GateType::NAND || type == GateType::NOR || type == GateType::NOT || type == GateType::XNOR) {
        res = notVal(res);
    }
    
    return res;
}

// === PODEM Methods ===

LogicVal PODEM::getVal(Node* n) {
    if (nodeState.find(n) == nodeState.end()) return LogicVal::X;
    return nodeState[n];
}

void PODEM::setVal(Node* n, LogicVal v) {
    nodeState[n] = v;
}

void PODEM::clearCircuit() {
    nodeState.clear();
    for (Node* n : netlist->getAllNodes()) {
        nodeState[n] = LogicVal::X;
    }
}

// Simple event-driven implication
bool PODEM::imply() {
    // Ideally employ an event-driven mechanism.
    // For this implementation, iterative convergence is sufficient.
    
    std::vector<Node*> queue;
    // Add all nodes that have inputs defined but are X
    // Actually, pure PODEM implies from PI assignments forward.
    
    bool infoChanged = true;
    while(infoChanged) {
        infoChanged = false;
        
        for (Node* g : netlist->getGates()) {
            if (getVal(g) != LogicVal::X) continue; // Already decided
            // Special handling for the active fault site
            
            std::vector<LogicVal> inVals;
            bool anyX = false;
            for (Node* in : g->inputs) {
                LogicVal v = getVal(in);
                if (v == LogicVal::X) anyX = true;
                inVals.push_back(v);
            }
            
            LogicVal newVal = computeGateObj(g->type, inVals);
            
            // Fault Injection Logic:
            // If this gate is the target fault location and active, override with D/D_BAR.
            
            if (activeFaultNode && g == activeFaultNode) {
                // If we desired 1 (SA0 -> D), and logic produced 1, we get D.
                // If we desired 0 (SA1 -> D'), and logic produced 0, we get D'.
                if (activeFaultVal == LogicVal::D && newVal == LogicVal::ONE) newVal = LogicVal::D;
                else if (activeFaultVal == LogicVal::D_BAR && newVal == LogicVal::ZERO) newVal = LogicVal::D_BAR;
            }

            if (newVal != LogicVal::X && newVal != getVal(g)) {
                setVal(g, newVal);
                infoChanged = true;
            }
        }

        // outputs
        for (Node* out : netlist->getOutputs()) {
            if (getVal(out) != LogicVal::X) continue;
            std::vector<LogicVal> inVals;
            if(out->inputs.size() > 0) { 
                 // Process output pin logic if applicable
            }
        }
    }
    
    return true;
}

// Objective: Returns pair {Node to justify, Value 0/1}
std::pair<Node*, int> PODEM::getObjective(Node* faultLoc, LogicVal faultActVal) {
    LogicVal fVal = getVal(faultLoc);
    
    // 1. Activate Fault
    if (fVal == LogicVal::X) {
        // Need to set faultLoc to proper activation value.
        // If we want Stuck-At-0, we need 1 (D); if Stuck-At-1, we need 0 (D_BAR).
        return {faultLoc, (faultActVal == LogicVal::D) ? 1 : 0};
    }
    
    // 2. Propagate (D-Frontier)
    // Find a gate with D or D_BAR on input, X on output.
    std::vector<Node*> dFrontier;
    for (Node* g : netlist->getGates()) {
        if (getVal(g) != LogicVal::X) continue;
        
        bool hasD = false;
        for (Node* in : g->inputs) {
            LogicVal v = getVal(in);
            if (v == LogicVal::D || v == LogicVal::D_BAR) hasD = true;
        }
        if (hasD) dFrontier.push_back(g);
    }
    
    if (dFrontier.empty()) return {nullptr, -1}; // Failure
    
    // Heuristic: Pick closest to PO? Pick first?
    Node* g = dFrontier[0];
    
    // Pick an input of g that is X to set to non-controlling value
    // e.g. AND gate -> set X inputs to 1.
    for (Node* in : g->inputs) {
        if (getVal(in) == LogicVal::X) {
            // Determine non-controlling value
            int nonControl = 0;
            if (g->type == GateType::AND || g->type == GateType::NAND) nonControl = 1;
            if (g->type == GateType::OR || g->type == GateType::NOR) nonControl = 0;
            return {in, nonControl};
        }
    }
    
    return {nullptr, -1};
}

std::pair<Node*, int> PODEM::backtrace(Node* k, int val) {
    Node* curr = k;
    int currVal = val;
    
    while (curr->inputs.size() > 0) { // While not PI
        // Stop if DFF (treated as Pseudo-PI)
        if (curr->type == GateType::DFF) break;

        // Pick an input that is X
        Node* next = nullptr;
        for (Node* in : curr->inputs) {
            if (getVal(in) == LogicVal::X) {
                next = in;
                break;
            }
        }
        if (!next) break;
        
        // Invert val if inverting gate
        if (curr->type == GateType::NAND || curr->type == GateType::NOR || 
            curr->type == GateType::NOT || curr->type == GateType::XNOR) {
            currVal = !currVal;
        }
        
        curr = next;
    }
    return {curr, currVal};
}

bool PODEM::podemRecursion(Node* faultLoc, LogicVal faultActVal) {
    // Abort if backtrack budget exceeded
    if (backtrackCount >= maxBacktracks) return false;

    // 1. Check if fault detected (D/D_BAR at PO)
    for (Node* out : netlist->getOutputs()) {
        LogicVal v = getVal(out);
        if (v == LogicVal::D || v == LogicVal::D_BAR) return true;
    }
    
    // 2. Determine Objective
    std::pair<Node*, int> obj = getObjective(faultLoc, faultActVal);
    if (obj.first == nullptr) return false; // Failure (no D-frontier or activation impossible)

    // 3. Backtrace
    std::pair<Node*, int> decision = backtrace(obj.first, obj.second);
    Node* pi = decision.first;
    int val = decision.second;

    // 4. Try assignment val
    setVal(pi, (val == 1) ? LogicVal::ONE : LogicVal::ZERO);
    imply();
    if (podemRecursion(faultLoc, faultActVal)) return true;

    // 5. Backtrack & Try !val
    backtrackCount++;
    if (backtrackCount >= maxBacktracks) return false;

    setVal(pi, (val == 1) ? LogicVal::ZERO : LogicVal::ONE); // Flip
    
    // Save-State/Restore backtracking ensuring atomic operations.
    
    // === RESTART logic for step 4 ===
    auto stateBefore = nodeState;
    
    setVal(pi, (val == 1) ? LogicVal::ONE : LogicVal::ZERO);
    imply();
    if (podemRecursion(faultLoc, faultActVal)) return true;
    
    backtrackCount++;
    // Backtrack: Restore state
    nodeState = stateBefore;
    
    // Try other value
    setVal(pi, (val == 1) ? LogicVal::ZERO : LogicVal::ONE);
    imply();
    if (podemRecursion(faultLoc, faultActVal)) return true;
    
    // Backtrack: Restore state & return failure
    nodeState = stateBefore;
    setVal(pi, LogicVal::X); // Undo assignment
    return false;
}

std::map<Node*, int> PODEM::generateTest(Node* target, int targetVal) {
    clearCircuit();
    backtrackCount = 0; // Reset per-node budget
    
    // We want target to be targetVal.
    // Stuck-At fault model:
    // If we want 1, we treat it as faulty 0 (SA0), so value becomes D.
    // If we want 0, we treat it as faulty 1 (SA1), so value becomes D_BAR.
    
    LogicVal faultActVal = (targetVal == 1) ? LogicVal::D : LogicVal::D_BAR;
    this->activeFaultNode = target;
    this->activeFaultVal = faultActVal;
    
    if (podemRecursion(target, faultActVal)) {
        std::map<Node*, int> result;
        for (Node* in : netlist->getInputs()) {
            LogicVal v = getVal(in);
            result[in] = (v == LogicVal::ONE) ? 1 : 0; // X defaults to 0
        }
        // Cleanup
        this->activeFaultNode = nullptr;
        return result;
    }
    
    this->activeFaultNode = nullptr;
    return {}; // Empty map = Failure
}
