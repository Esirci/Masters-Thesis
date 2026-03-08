#pragma once
#include "Netlist.h"
#include <vector>
#include <map>
#include <stack>

enum class LogicVal { ZERO, ONE, X, D, D_BAR };

class PODEM {
public:
    PODEM(Netlist* netlist);
    
    // Generates a test vector to justifiy 'targetVal' at 'target' node 
    // and propagates the fault effect to an observable output.
    // Returns: Map of Input Node -> 0/1. Returns empty map if justification fails.
    std::map<Node*, int> generateTest(Node* target, int targetVal);
    
    Node* activeFaultNode = nullptr;
    LogicVal activeFaultVal = LogicVal::X;

private:
    Netlist* netlist;

    // Reset circuit state to Unknown (X)
    void clearCircuit();

    // 5-valued logic tables/functions
    LogicVal computeGateObj(GateType type, const std::vector<LogicVal>& inputs);
    static LogicVal notVal(LogicVal v);
    static LogicVal andVal(LogicVal a, LogicVal b);
    static LogicVal orVal(LogicVal a, LogicVal b);
    static LogicVal xorVal(LogicVal a, LogicVal b);

    // Implementation of the PODEM algorithm logic
    bool imply(); // Forward implication from current state. Returns true if no conflict detected.
    bool checkObjective(Node* objectiveNode, LogicVal objectiveValue);
    
    // Returns true if X-path exists from D-frontier to PO
    bool checkXPath(const std::vector<Node*>& dFrontier); 

    std::pair<Node*, int> getObjective(Node* faultLoc, LogicVal faultVal);
    std::pair<Node*, int> backtrace(Node* k, int val);

    // Recursive search step for PODEM
    // faultLoc: The target node for activation
    // faultActVal: The required logic value (D or D_BAR) for activation
    bool podemRecursion(Node* faultLoc, LogicVal faultActVal);

    // State management
    void assign(Node* var, LogicVal val);
    
    // We need to store original values to backtrack properly.
    // Used for state restoration during recursion.
    std::stack<Node*> decisionStack;
    std::map<Node*, LogicVal> nodeState;

    // Backtrack limit to prevent exponential runtime on large circuits
    int backtrackCount = 0;
    int maxBacktracks = 5000; // Default: 5000 backtracks per node

    LogicVal getVal(Node* n);
    void setVal(Node* n, LogicVal v);
};
