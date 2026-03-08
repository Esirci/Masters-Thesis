"""
loss_guided_selector.py
=======================
Adversarial Co-Evaluation Framework — 4th Ablation Method

From the SAME set of generated candidates (built by generate_candidates.exe),
selects the candidate that the Baseline DNN is LEAST confident is a Trojan.

This uses the trained `baseline_dnn_model.keras` and its corresponding scaler 
from Step 5 to evaluate each candidate's feature vector, minimizing P(Trojan).
"""

import os
import sys
import json
import csv
import argparse
import numpy as np
import pandas as pd
import joblib

import tensorflow as tf

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
THIS_DIR      = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT  = os.path.dirname(THIS_DIR)
DATA_DIR      = os.path.join(PROJECT_ROOT, 'data')
FEHT_DIR      = os.path.join(DATA_DIR, 'feht')
CAND_DIR      = os.path.join(DATA_DIR, 'candidates')
DEFENDER_DIR  = os.path.join(PROJECT_ROOT, 'defender')

DNN_MODEL_PATH = os.path.join(DEFENDER_DIR, 'baseline_dnn_model.keras')
SCALER_PATH    = os.path.join(DEFENDER_DIR, 'dnn_scaler.pkl')
OUT_CSV        = os.path.join(DATA_DIR, 'feht_dataset.csv')
COLS_PATH      = os.path.join(DATA_DIR, 'feature_columns.txt')

CAP = 1e12

# ---------------------------------------------------------------------------
# Import HTPred feature extractor (from mfp_selector.py)
# ---------------------------------------------------------------------------
sys.path.insert(0, THIS_DIR)
from mfp_selector import extract_features_for_bench

# ---------------------------------------------------------------------------
# Preprocessing Logic
# ---------------------------------------------------------------------------
def preprocess_cap_log(X_df):
    X = X_df.astype(np.float64)
    X.replace([np.inf, -np.inf], np.nan, inplace=True)
    X = X.fillna(X.median(numeric_only=True))
    X = X.clip(lower=-CAP, upper=CAP)
    X = np.sign(X) * np.log1p(np.abs(X))
    return X

# ---------------------------------------------------------------------------
# Core Logic
# ---------------------------------------------------------------------------
def pick_loss_guided_baseline(candidates_dir, feature_cols, dnn_model, std_scaler):
    """
    Evaluates all candidate_*.bench files via HTPred -> Preprocess -> DNN
    Returns dict best_result or None
    """
    bench_files = sorted([f for f in os.listdir(candidates_dir) if f.startswith('candidate_') and f.endswith('.bench')])
    if not bench_files:
        return None

    results = []
    for bf in bench_files:
        bp = os.path.join(candidates_dir, bf)
        try:
            # 1. Extract raw HTPred features
            feat_raw = extract_features_for_bench(bp, label=1, feature_cols=feature_cols)
            
            # 2. Preprocess (log1p capping) and Scale
            feat_df = pd.DataFrame([feat_raw], columns=feature_cols)
            feat_log = preprocess_cap_log(feat_df)
            feat_scaled = std_scaler.transform(feat_log)
            
            # 3. Predict probability of Trojan (Label=1)
            proba = float(dnn_model.predict(feat_scaled, verbose=0)[0][0])
            
            results.append({'file': bf, 'proba': proba, 'feat_raw': feat_raw, 'path': bp})
        except Exception as e:
            print(f"    [WARN] Loss-guided evaluation failed for {bf}: {e}")

    if not results:
        return None

    # Loss-guided objective: Minimize P(Trojan)
    best_result = min(results, key=lambda x: x['proba'])
    
    return best_result

# ---------------------------------------------------------------------------
# Main Routine
# ---------------------------------------------------------------------------
def run_loss_guided_generation(dry_run=False):
    print("="*65)
    print("  Loss-Guided Evasion Generator (4th Ablation Baseline)")
    print("="*65)

    if not os.path.exists(DNN_MODEL_PATH) or not os.path.exists(SCALER_PATH):
        print(f"[ERROR] Missing DNN model or scaler.")
        print("  Make sure evaluate_baseline_dnn.py has been run first!")
        sys.exit(1)

    # 1. Load trained artifacts
    dnn_model = tf.keras.models.load_model(DNN_MODEL_PATH)
    std_scaler = joblib.load(SCALER_PATH)
    feature_cols = open(COLS_PATH).read().strip().split('\n')
    
    # 2. Find circuits that generated candidates during build_feht_dataset
    if not os.path.exists(CAND_DIR):
        print("[ERROR] candidates directory not found.")
        sys.exit(1)
        
    all_circuits = sorted(os.listdir(CAND_DIR))
    if dry_run:
        all_circuits = all_circuits[:5]
        print(f"  [DRY RUN] Processing {len(all_circuits)} circuits")
        
    # We load the existing CSV so we can append the new rows
    if not os.path.exists(OUT_CSV):
        print(f"[ERROR] feht_dataset.csv not found. Run build_feht_dataset.py first.")
        sys.exit(1)
        
    # Prepare to append to CSV
    csv_file = open(OUT_CSV, 'a', newline='', encoding='utf-8')
    fieldnames = ['Name of file', 'circuit', 'method', 'Label', 'md_distance'] + list(feature_cols)
    writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
    
    success_count = 0
    print("[A] Processing circuits to append loss-guided baseline...")

    for idx, circuit_name in enumerate(all_circuits):
        cand_dir = os.path.join(CAND_DIR, circuit_name)
        # Skip if no candidates were generated originally
        bench_files = [f for f in os.listdir(cand_dir) if f.startswith('candidate_')]
        if not bench_files:
            continue
            
        print(f"  [{idx+1}/{len(all_circuits)}] {circuit_name} ({len(bench_files)} candidates)")
        
        best = pick_loss_guided_baseline(cand_dir, feature_cols, dnn_model, std_scaler)
        if best is None:
            print(f"    [SKIP] Failed to evaluate candidates for {circuit_name}")
            continue
            
        print(f"    Selected: {best['file']}  (P(Trojan) = {best['proba']:.6f})")
        
        # Write the new row to CSV
        original_bench_file_name = f"{circuit_name}.bench" # Approximation for Name format
        row = {
            'Name of file':  original_bench_file_name,
            'circuit':       circuit_name,
            'method':        'loss_guided',
            'Label':         1,
            'md_distance':   '' # MD is not relevant for this method, but keep column aligned
        }
        for i, col in enumerate(feature_cols):
            row[col] = best['feat_raw'][i]
            
        writer.writerow(row)
        success_count += 1
        csv_file.flush()

    csv_file.close()

    print("\n" + "="*65)
    print("  LOSS-GUIDED GENERATION SUMMARY")
    print("="*65)
    print(f"  Circuits evaluated:      {len(all_circuits)}")
    print(f"  Loss-guided rows added:  {success_count}")
    print(f"  Appended to:             {OUT_CSV}")
    print("="*65)
    print("\n[OK] feht_dataset.csv now contains the loss_guided ablation rows.")
    print("Next: re-run evaluate_baseline_dnn.py to see if Loss-Guided evades the DNN.")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry_run', action='store_true', help='Process only first 5 circuits')
    args = parser.parse_args()
    
    run_loss_guided_generation(dry_run=args.dry_run)
