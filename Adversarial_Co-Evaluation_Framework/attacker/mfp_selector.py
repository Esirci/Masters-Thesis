"""
mfp_selector.py
===============
Adversarial Co-Evaluation Framework — Step 2b (Core Novelty: MFP Algorithm)

Implements the Minimum Feature Perturbation (MFP) selector.

Given a directory of candidate .bench files (output of generate_candidates.exe),
extracts HTPred 605-feature vectors for each candidate, then selects the one
with the MINIMUM Mahalanobis distance to the clean circuit distribution.

That candidate is the Feature-Evasive Hardware Trojan (FEHT):
    argmin_{c ∈ candidates} d_M(φ(c)) where d_M = sqrt((x-μ)^T Σ⁻¹ (x-μ))

Usage:
    python attacker/mfp_selector.py \\
        --candidates_dir data/candidates/c2670 \\
        --output_dir     data/feht \\
        --label          1

Outputs:
    - data/feht/c2670_feht_mfp.bench        : the selected FEHT
    - data/feht/c2670_all_distances.csv     : Mahalanobis distance for every candidate
    - data/feht/c2670_mfp_result.json       : summary JSON
"""

import os
import sys
import json
import argparse
import shutil
import tempfile
import csv as csv_module
import numpy as np
import pandas as pd
import joblib

# ---------------------------------------------------------------------------
# Resolve paths (project root = parent of attacker/)
# ---------------------------------------------------------------------------
THIS_DIR     = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(THIS_DIR)
HTPRED_DIR   = os.path.join(PROJECT_ROOT, '..', 'HTPred-master')
HTPRED_DIR   = os.path.abspath(HTPRED_DIR)

DATA_DIR     = os.path.join(PROJECT_ROOT, 'data')
PREC_PATH    = os.path.join(DATA_DIR, 'precision_matrix.npy')
MEAN_PATH    = os.path.join(DATA_DIR, 'clean_mean.npy')
SCALER_PATH  = os.path.join(DATA_DIR, 'minmax_scaler.pkl')
COLS_PATH    = os.path.join(DATA_DIR, 'feature_columns.txt')

DROP_COLS = ['Label', 'Name of file', 'base_design', 'trojan_id', 'circuit', 'method', 'md_distance']


# ---------------------------------------------------------------------------
# HTPred feature extraction wrapper
# ---------------------------------------------------------------------------

def extract_features_for_bench(bench_path: str, label: int, feature_cols: list) -> np.ndarray:
    """
    Runs the full HTPred 7-step pipeline on a single .bench file.

    Strategy:
      - Temporarily chdir to HTPred-master (required because all internal
        paths use PARENT_DIR = dirname(ROOT_DIR) = New_Thesis_Direction/)
      - Call process_single_file() with a temp CSV output path
      - Read the temp CSV back, align columns, return feature vector

    Args:
        bench_path   : absolute path to the .bench file
        label        : 0 = clean, 1 = trojan (affects which functional_results dir is used)
        feature_cols : ordered list of 605 feature column names (from feature_columns.txt)

    Returns:
        numpy array of shape (605,) — the feature vector, aligned to feature_cols
    """
    bench_path = os.path.abspath(bench_path)
    filename   = os.path.basename(bench_path)

    # Temp CSV for this single file
    tmp_fd, tmp_csv = tempfile.mkstemp(suffix='.csv')
    os.close(tmp_fd)

    # Save and switch cwd
    original_cwd = os.getcwd()
    try:
        # Add HTPred-master to sys.path so imports work
        if HTPRED_DIR not in sys.path:
            sys.path.insert(0, HTPRED_DIR)

        # Switch cwd so all relative paths (../functional_results_*) resolve correctly
        os.chdir(HTPRED_DIR)

        import main as htpred_main
        # Re-import with fresh PARENT_DIR (chdir ensures it resolves correctly)
        import importlib
        importlib.reload(htpred_main)

        ok, err = htpred_main.process_single_file(
            full_path=bench_path,
            filename=filename,
            label=label,
            csv_path=tmp_csv,
            force_write_headers=True
        )
    finally:
        os.chdir(original_cwd)

    if not ok:
        os.unlink(tmp_csv)
        raise RuntimeError(f"HTPred pipeline failed for {bench_path}: {err}")

    # Read the written CSV
    result_df = pd.read_csv(tmp_csv)
    os.unlink(tmp_csv)

    # Drop metadata/label columns
    drop = [c for c in DROP_COLS if c in result_df.columns]
    result_df = result_df.drop(columns=drop)

    # Align to the expected column order (fill missing with 0, drop extra)
    result_df = result_df.apply(pd.to_numeric, errors='coerce').fillna(0)

    # Reindex to match training feature columns exactly
    result_aligned = result_df.reindex(columns=feature_cols, fill_value=0)

    return result_aligned.iloc[0].to_numpy(dtype=float)


# ---------------------------------------------------------------------------
# Mahalanobis distance
# ---------------------------------------------------------------------------

def mahalanobis_distance(x: np.ndarray, mean: np.ndarray, precision: np.ndarray) -> float:
    """
    Computes d_M(x) = sqrt((x - μ)^T Σ⁻¹ (x - μ))
    """
    diff = x - mean
    return float(np.sqrt(diff @ precision @ diff))


# ---------------------------------------------------------------------------
# Main MFP selection
# ---------------------------------------------------------------------------

def run_mfp_selection(candidates_dir: str, output_dir: str, label: int = 1):
    """
    Runs MFP selection on all candidate .bench files in candidates_dir.

    Returns:
        dict with keys: circuit, best_candidate, best_distance, all_distances
    """
    print("=" * 60)
    print("  mfp_selector.py — Minimum Feature Perturbation Algorithm")
    print("=" * 60)

    # ------------------------------------------------------------------
    # 1. Load precomputed covariance artifacts
    # ------------------------------------------------------------------
    print("\n[1/4] Loading precision matrix, mean, scaler, column list ...")
    for f in [PREC_PATH, MEAN_PATH, SCALER_PATH, COLS_PATH]:
        if not os.path.exists(f):
            print(f"[ERROR] Missing: {f}")
            print("  Run: python attacker/precompute_covariance.py  first.")
            sys.exit(1)

    precision    = np.load(PREC_PATH)
    clean_mean   = np.load(MEAN_PATH)
    scaler       = joblib.load(SCALER_PATH)
    feature_cols = open(COLS_PATH).read().strip().split('\n')

    print(f"  Precision matrix shape: {precision.shape}")
    print(f"  Feature dimensions:     {len(feature_cols)}")

    # ------------------------------------------------------------------
    # 2. Enumerate candidate .bench files
    # ------------------------------------------------------------------
    candidates = sorted([
        f for f in os.listdir(candidates_dir)
        if f.startswith('candidate_') and f.endswith('.bench')
    ])

    if not candidates:
        print(f"[ERROR] No candidate_*.bench files found in {candidates_dir}")
        sys.exit(1)

    print(f"\n[2/4] Found {len(candidates)} candidate files in {candidates_dir}")

    # Detect circuit name from metadata JSON if present
    meta_path = os.path.join(candidates_dir, 'candidate_metadata.json')
    circuit_name = os.path.basename(candidates_dir)
    if os.path.exists(meta_path):
        with open(meta_path) as mf:
            meta = json.load(mf)
            circuit_name = meta.get('circuit', circuit_name)

    # ------------------------------------------------------------------
    # 3. Extract features + compute Mahalanobis distance for each candidate
    # ------------------------------------------------------------------
    print(f"\n[3/4] Extracting HTPred features and computing distances ...")
    os.makedirs(output_dir, exist_ok=True)

    distances = []
    errors    = []

    for i, cand_file in enumerate(candidates):
        cand_path = os.path.join(candidates_dir, cand_file)
        print(f"\n  [{i+1}/{len(candidates)}] Processing: {cand_file}")

        try:
            # Extract 605-feature vector
            feat_raw = extract_features_for_bench(cand_path, label=label,
                                                   feature_cols=feature_cols)

            # Apply same MinMax scaling as training
            feat_scaled = scaler.transform(feat_raw.reshape(1, -1))[0]

            # Mahalanobis distance to clean mean
            dist = mahalanobis_distance(feat_scaled, clean_mean, precision)

            print(f"     Mahalanobis distance: {dist:.6f}")
            distances.append({'file': cand_file, 'distance': dist,
                               'feat_raw': feat_raw, 'feat_scaled': feat_scaled})

        except Exception as e:
            print(f"     [WARN] Feature extraction failed: {e}")
            errors.append({'file': cand_file, 'error': str(e)})

    if not distances:
        print("[ERROR] Feature extraction failed for all candidates.")
        sys.exit(1)

    # ------------------------------------------------------------------
    # 4. Select MFP: minimum Mahalanobis distance
    # ------------------------------------------------------------------
    print(f"\n[4/4] Selecting FEHT (minimum Mahalanobis distance) ...")
    distances.sort(key=lambda d: d['distance'])

    best = distances[0]
    worst = distances[-1]

    print(f"\n  {'Rank':<6} {'File':<30} {'Distance':>12}")
    print(f"  {'-'*6} {'-'*30} {'-'*12}")
    for rank, d in enumerate(distances):
        marker = ' ← FEHT (MFP)' if rank == 0 else ''
        print(f"  {rank+1:<6} {d['file']:<30} {d['distance']:>12.6f}{marker}")

    # Copy winning candidate to output dir
    best_src  = os.path.join(candidates_dir, best['file'])
    best_dest = os.path.join(output_dir, f"{circuit_name}_feht_mfp.bench")
    shutil.copy2(best_src, best_dest)
    print(f"\n  FEHT written → {best_dest}")

    # ------------------------------------------------------------------
    # 5. Save all distances CSV (for ablation analysis in paper)
    # ------------------------------------------------------------------
    dist_csv_path = os.path.join(output_dir, f"{circuit_name}_all_distances.csv")
    with open(dist_csv_path, 'w', newline='') as f:
        writer = csv_module.DictWriter(f, fieldnames=['circuit', 'file', 'distance', 'rank'])
        writer.writeheader()
        for rank, d in enumerate(distances):
            writer.writerow({'circuit': circuit_name, 'file': d['file'],
                             'distance': d['distance'], 'rank': rank + 1})
    print(f"  All distances saved → {dist_csv_path}")

    # ------------------------------------------------------------------
    # 6. Save result JSON summary
    # ------------------------------------------------------------------
    result = {
        'circuit':         circuit_name,
        'total_candidates': len(candidates),
        'successful':      len(distances),
        'failed':          len(errors),
        'feht_mfp': {
            'file':       best['file'],
            'distance':   best['distance'],
            'output':     best_dest
        },
        'worst_candidate': {
            'file':       worst['file'],
            'distance':   worst['distance']
        },
        'distance_spread': worst['distance'] - best['distance'],
        'errors': errors
    }

    result_json_path = os.path.join(output_dir, f"{circuit_name}_mfp_result.json")
    with open(result_json_path, 'w') as f:
        json.dump(result, f, indent=2)
    print(f"  Result JSON saved → {result_json_path}")

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("  MFP SELECTION SUMMARY")
    print("=" * 60)
    print(f"  Circuit:               {circuit_name}")
    print(f"  Candidates evaluated:  {len(distances)} / {len(candidates)}")
    print(f"  FEHT (MFP):            {best['file']}")
    print(f"  MFP distance:          {best['distance']:.6f}")
    print(f"  Worst distance:        {worst['distance']:.6f}")
    print(f"  Distance spread:       {result['distance_spread']:.6f}")
    print("=" * 60)

    return result


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description='MFP Selector — Minimum Feature Perturbation FEHT selection')
    parser.add_argument('--candidates_dir', required=True,
                        help='Directory with candidate_*.bench files (generate_candidates output)')
    parser.add_argument('--output_dir', required=True,
                        help='Directory to write FEHT .bench + distance CSV + result JSON')
    parser.add_argument('--label', type=int, default=1, choices=[0, 1],
                        help='Label for HTPred pipeline: 1=trojan (default), 0=clean')
    return parser.parse_args()


if __name__ == '__main__':
    args = parse_args()
    run_mfp_selection(
        candidates_dir=os.path.abspath(args.candidates_dir),
        output_dir=os.path.abspath(args.output_dir),
        label=args.label
    )
