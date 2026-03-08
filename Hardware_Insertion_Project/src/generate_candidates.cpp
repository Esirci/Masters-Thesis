// =============================================================================
// generate_candidates.cpp
// Part of: Adversarial Co-Evaluation Framework — Step 1 (Attacker Side)
// Author: Mohamed (2026)
//
// Purpose:
//   Given a clean .bench file, enumerate ALL valid clique-based Trojan candidates
//   and write each as a separate .bench file. Also writes candidate_metadata.json.
//
// Usage:
//   generate_candidates.exe <input.bench> <output_dir> [payload_type] [clique_size]
//
// Arguments:
//   input.bench   : path to clean circuit (e.g. HTPred-master/Non Trojan Files/c2670.bench.txt)
//   output_dir    : directory to write candidate_0.bench, candidate_1.bench, etc.
//   payload_type  : XOR (default) | DELAY | DOS0 | DOS1 | LEAK
//   clique_size   : minimum trigger size (default: 2)
//
// Output:
//   output_dir/candidate_<i>.bench       — one per valid candidate
//   output_dir/candidate_metadata.json  — statistics + clique node names per candidate
//
// Notes:
//   - Uses theta=0.10 for rare node identification (permanent default from Final_Report.md S1)
//   - Parallel PODEM (hardware_concurrency() threads, auto-detected)
//   - Bron-Kerbosch: hard cap at 1000 cliques / 50k recursions
//   - Area overhead filter: max 10% additional gates (min 10 extra gates)
//   - Each candidate gets a fresh netlist re-parse to avoid shared state corruption
// =============================================================================

#include "Netlist.h"
#include "Simulator.h"
#include "CompatibilityGraph.h"
#include "TrojanGenerator.h"

#include <iostream>
#include <fstream>
#include <sstream>
#include <vector>
#include <string>
#include <filesystem>
#include <chrono>
#include <algorithm>

namespace fs = std::filesystem;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

TrojanType parsePayloadType(const std::string& s) {
    if (s == "DELAY") return TrojanType::PERFORMANCE_DEGRADE_DELAY;
    if (s == "DOS0")  return TrojanType::DOS_STUCK_AT_0;
    if (s == "DOS1")  return TrojanType::DOS_STUCK_AT_1;
    if (s == "LEAK")  return TrojanType::LEAK_INFORMATION;
    return TrojanType::FUNCTIONAL_CHANGE_XOR; // default
}

std::string payloadName(TrojanType t) {
    switch (t) {
        case TrojanType::PERFORMANCE_DEGRADE_DELAY: return "DELAY";
        case TrojanType::DOS_STUCK_AT_0:            return "DOS0";
        case TrojanType::DOS_STUCK_AT_1:            return "DOS1";
        case TrojanType::LEAK_INFORMATION:          return "LEAK";
        default:                                    return "XOR";
    }
}

// Escape a string for JSON
std::string jsonStr(const std::string& s) {
    std::string out;
    for (char c : s) {
        if (c == '\\') out += "\\\\";
        else if (c == '"') out += "\\\"";
        else out += c;
    }
    return "\"" + out + "\"";
}

void writeEmptyMetadata(const std::string& outputDir,
                        const std::string& circuitName,
                        const std::string& inputBench,
                        int originalGateCount,
                        int rareNodeCount,
                        int cliqueSize,
                        const std::string& payloadStr,
                        double elapsed) {
    std::ofstream meta(outputDir + "/candidate_metadata.json");
    meta << "{\n";
    meta << "  \"circuit\": " << jsonStr(circuitName) << ",\n";
    meta << "  \"input_bench\": " << jsonStr(inputBench) << ",\n";
    meta << "  \"original_gate_count\": " << originalGateCount << ",\n";
    meta << "  \"rare_node_count\": " << rareNodeCount << ",\n";
    meta << "  \"total_cliques\": 0,\n";
    meta << "  \"total_candidates\": 0,\n";
    meta << "  \"clique_size\": " << cliqueSize << ",\n";
    meta << "  \"payload\": " << jsonStr(payloadStr) << ",\n";
    meta << "  \"elapsed_seconds\": " << elapsed << ",\n";
    meta << "  \"candidates\": []\n";
    meta << "}\n";
}

// ---------------------------------------------------------------------------
// main
// ---------------------------------------------------------------------------

int main(int argc, char** argv) {
    if (argc < 3) {
        std::cerr << "Usage: generate_candidates <input.bench> <output_dir> "
                     "[payload_type] [clique_size]\n";
        std::cerr << "  payload_type: XOR (default) | DELAY | DOS0 | DOS1 | LEAK\n";
        std::cerr << "  clique_size : minimum trigger size (default: 2)\n";
        return 1;
    }

    std::string inputBench = argv[1];
    std::string outputDir  = argv[2];
    std::string payloadStr = (argc >= 4) ? std::string(argv[3]) : "XOR";
    int cliqueSize         = (argc >= 5) ? std::stoi(argv[4]) : 2;

    TrojanType payload = parsePayloadType(payloadStr);

    // Create output directory
    fs::create_directories(outputDir);

    auto startTotal = std::chrono::high_resolution_clock::now();

    std::cout << "============================================================\n";
    std::cout << "  generate_candidates — Adversarial Co-Evaluation Framework\n";
    std::cout << "============================================================\n";
    std::cout << "Input:       " << inputBench  << "\n";
    std::cout << "Output dir:  " << outputDir   << "\n";
    std::cout << "Payload:     " << payloadStr  << "\n";
    std::cout << "Clique size: " << cliqueSize  << "\n\n";

    // -------------------------------------------------------------------------
    // Phase 1: Parse & Simulate (shared base netlist — read-only after this)
    // -------------------------------------------------------------------------
    std::cout << "[1/4] Parsing netlist...\n";
    Netlist baseNetlist;
    if (!baseNetlist.parse(inputBench)) {
        std::cerr << "[ERROR] Failed to parse " << inputBench << "\n";
        return 1;
    }
    int originalGateCount = (int)baseNetlist.getGates().size();
    std::cout << "  Gates: " << originalGateCount << "\n";
    
    std::string cleanUnrolledPath = outputDir + "/clean_unrolled.bench";
    baseNetlist.write(cleanUnrolledPath);

    std::cout << "[1/4] Finding rare nodes (theta=0.10, 10k vectors)...\n";
    Simulator sim(&baseNetlist);
    sim.findRareNodes(10000, 0.10);

    std::vector<Node*> rareNodes;
    for (Node* n : baseNetlist.getAllNodes()) {
        if (n->rare_value != -1) rareNodes.push_back(n);
    }
    std::cout << "  Rare nodes: " << rareNodes.size() << "\n";

    std::string circuitName = fs::path(inputBench).stem().string();

    auto elapsed_so_far = [&]() {
        return std::chrono::duration<double>(
            std::chrono::high_resolution_clock::now() - startTotal).count();
    };

    if (rareNodes.empty()) {
        std::cout << "[WARN] No rare nodes found. Circuit produces 0 candidates.\n";
        writeEmptyMetadata(outputDir, circuitName, inputBench,
                           originalGateCount, 0, cliqueSize, payloadStr, elapsed_so_far());
        return 0;
    }

    // -------------------------------------------------------------------------
    // Phase 2: Compatibility Graph + Clique Finding
    // -------------------------------------------------------------------------
    std::cout << "[2/4] Building compatibility graph (parallel PODEM)...\n";
    CompatibilityGraph cg(&baseNetlist);
    cg.generateTestVectors(rareNodes); // parallel with hardware_concurrency() threads
    cg.buildGraph();

    std::cout << "[2/4] Finding cliques (min size " << cliqueSize << ")...\n";
    auto cliques = cg.findCliques(cliqueSize);

    // Graceful fallback: if no clique of requested size, try size 2
    if (cliques.empty() && cliqueSize > 2) {
        std::cout << "[WARN] No cliques of size " << cliqueSize
                  << " found. Falling back to size 2.\n";
        cliques = cg.findCliques(2);
        cliqueSize = 2;
    }

    std::cout << "  Total cliques: " << cliques.size() << "\n";

    if (cliques.empty()) {
        std::cout << "[WARN] No valid cliques. Circuit produces 0 candidates.\n";
        writeEmptyMetadata(outputDir, circuitName, inputBench,
                           originalGateCount, (int)rareNodes.size(),
                           cliqueSize, payloadStr, elapsed_so_far());
        return 0;
    }

    // -------------------------------------------------------------------------
    // Phase 3: Generate One Candidate Per Clique
    // -------------------------------------------------------------------------
    std::cout << "[3/4] Generating candidates...\n";

    // Max overhead: 10% of original gate count, minimum 10 extra gates
    const int MAX_OVERHEAD_GATES = std::max(10, (int)(originalGateCount * 0.10));

    // Store clique node names from baseNetlist (pointers are only valid there)
    // We need names to look up nodes in each fresh re-parsed netlist
    struct CandidateRecord {
        int id;
        std::vector<std::string> cliqueNodeNames;
        std::vector<int>         cliqueRareValues;  // rare_value per node
        int   gateOverhead = -1;
        bool  valid        = false;
    };

    std::vector<CandidateRecord> records;
    int validCount = 0;

    for (int i = 0; i < (int)cliques.size(); ++i) {
        CandidateRecord rec;
        rec.id = i;

        // Save clique node names + rare values from base netlist
        for (Node* n : cliques[i]) {
            rec.cliqueNodeNames.push_back(n->name);
            rec.cliqueRareValues.push_back(n->rare_value);
        }

        // Fresh netlist re-parse — avoids mutation of shared state
        Netlist candidateNetlist;
        if (!candidateNetlist.parse(inputBench)) {
            std::cout << "  [SKIP] Candidate " << i << ": re-parse failed.\n";
            records.push_back(rec);
            continue;
        }

        // Map clique from base netlist into fresh netlist by name
        std::vector<Node*> freshClique;
        bool allFound = true;
        for (int j = 0; j < (int)rec.cliqueNodeNames.size(); ++j) {
            Node* fn = candidateNetlist.getNode(rec.cliqueNodeNames[j]);
            if (!fn) { allFound = false; break; }
            fn->rare_value = rec.cliqueRareValues[j]; // restore rare_value (lost on re-parse)
            freshClique.push_back(fn);
        }

        if (!allFound) {
            std::cout << "  [SKIP] Candidate " << i << ": clique node not found in fresh netlist.\n";
            records.push_back(rec);
            continue;
        }

        // Generate trigger + payload
        TrojanGenerator gen(&candidateNetlist);
        Node* trigger = gen.generateTrigger(freshClique);

        if (!trigger) {
            std::cout << "  [SKIP] Candidate " << i << ": trigger generation failed.\n";
            records.push_back(rec);
            continue;
        }

        TrojanConfig cfg;
        cfg.type        = payload;
        cfg.triggerSize = (int)freshClique.size();
        gen.insertPayload(trigger, cfg);

        // Area overhead check
        int newGateCount = (int)candidateNetlist.getGates().size();
        int overhead     = newGateCount - originalGateCount;
        rec.gateOverhead = overhead;

        if (overhead > MAX_OVERHEAD_GATES) {
            std::cout << "  [SKIP] Candidate " << i << ": overhead +" << overhead
                      << " gates > max " << MAX_OVERHEAD_GATES << "\n";
            records.push_back(rec);
            continue;
        }

        // Write .bench file
        std::string outPath = outputDir + "/candidate_" + std::to_string(i) + ".bench";
        candidateNetlist.write(outPath);

        rec.valid = true;
        validCount++;
        records.push_back(rec);

        std::cout << "  [OK]  Candidate " << i << " written"
                  << "  (overhead: +" << overhead << " gates,"
                  << " trigger nodes: ";
        for (const auto& name : rec.cliqueNodeNames) std::cout << name << " ";
        std::cout << ")\n";
    }

    // -------------------------------------------------------------------------
    // Phase 4: Write Metadata JSON
    // -------------------------------------------------------------------------
    std::cout << "[4/4] Writing metadata...\n";
    double elapsed = elapsed_so_far();

    std::string metaPath = outputDir + "/candidate_metadata.json";
    std::ofstream meta(metaPath);

    meta << "{\n";
    meta << "  \"circuit\": " << jsonStr(circuitName) << ",\n";
    meta << "  \"input_bench\": " << jsonStr(inputBench) << ",\n";
    meta << "  \"original_gate_count\": " << originalGateCount << ",\n";
    meta << "  \"rare_node_count\": " << (int)rareNodes.size() << ",\n";
    meta << "  \"total_cliques\": " << (int)cliques.size() << ",\n";
    meta << "  \"total_candidates\": " << validCount << ",\n";
    meta << "  \"clique_size\": " << cliqueSize << ",\n";
    meta << "  \"payload\": " << jsonStr(payloadStr) << ",\n";
    meta << "  \"elapsed_seconds\": " << elapsed << ",\n";
    meta << "  \"candidates\": [\n";

    bool firstValid = true;
    for (auto& rec : records) {
        if (!rec.valid) continue;

        if (!firstValid) meta << ",\n"; // comma between entries
        firstValid = false;

        meta << "    {\n";
        meta << "      \"id\": " << rec.id << ",\n";
        meta << "      \"file\": " << jsonStr("candidate_" + std::to_string(rec.id) + ".bench") << ",\n";
        meta << "      \"gate_overhead\": " << rec.gateOverhead << ",\n";
        meta << "      \"clique_size\": " << (int)rec.cliqueNodeNames.size() << ",\n";
        meta << "      \"clique_nodes\": [";
        for (int j = 0; j < (int)rec.cliqueNodeNames.size(); ++j) {
            meta << jsonStr(rec.cliqueNodeNames[j]);
            if (j < (int)rec.cliqueNodeNames.size() - 1) meta << ", ";
        }
        meta << "]\n";
        meta << "    }";
    }
    if (!firstValid) meta << "\n"; // newline after last entry if any
    meta << "  ]\n";
    meta << "}\n";
    meta.close();

    // -------------------------------------------------------------------------
    // Summary
    // -------------------------------------------------------------------------
    std::cout << "\n============================================================\n";
    std::cout << "  SUMMARY\n";
    std::cout << "============================================================\n";
    std::cout << "  Circuit:         " << circuitName << "\n";
    std::cout << "  Original gates:  " << originalGateCount << "\n";
    std::cout << "  Rare nodes:      " << rareNodes.size() << "\n";
    std::cout << "  Total cliques:   " << cliques.size() << "\n";
    std::cout << "  Valid candidates:" << validCount << "\n";
    std::cout << "  Elapsed:         " << elapsed << "s\n";
    std::cout << "  Metadata:        " << metaPath << "\n";
    std::cout << "============================================================\n";

    return 0;
}
