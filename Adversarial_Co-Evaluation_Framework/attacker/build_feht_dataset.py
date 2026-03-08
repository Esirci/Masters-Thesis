"""
build_feht_dataset.py
=====================
Adversarial Co-Evaluation Framework — Step 3 (Full Batch Pipeline)

Processes all 91 clean circuits from HTPred-master/Non Trojan Files/,
generates Trojan candidates for each, and builds feht_dataset.csv containing:

  |  Label  |  Method       | Description                                     |
  |---------|---------------|-------------------------------------------------|
  |    0    |  clean        | Original clean circuit features (from short_csv)|
  |    1    |  mfp          | MFP-selected FEHT (our method)                  |
  |    1    |  random       | Randomly selected candidate (ablation baseline 1)|
  |    1    |  graph_only   | Largest-clique candidate (ablation baseline 2)  |
  [Loss-guided (baseline 3) added in Step 4 after DNN is trained]

Usage:
    python attacker/build_feht_dataset.py [--dry_run] [--circuits N]

Options:
    --dry_run     Run on 3 circuits only (quick sanity check)
    --circuits N  Run on first N circuits (default: all 91)
    --timeout T   Seconds per circuit before skipping (default: 120)

Outputs:
    data/feht_dataset.csv           — main dataset for evaluation
    data/build_summary.json         — per-circuit statistics
    data/feht/<circuit>/            — per-circuit FEHT .bench files and distances
"""

import os
import sys
import json
import random
import argparse
import subprocess
import shutil
import time
import csv as csv_module
import numpy as np
import pandas as pd
import joblib

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
THIS_DIR      = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT  = os.path.dirname(THIS_DIR)
HTPRED_DIR    = os.path.abspath(os.path.join(PROJECT_ROOT, '..', 'HTPred-master'))
HW_DIR        = os.path.abspath(os.path.join(PROJECT_ROOT, '..', 'Hardware_Insertion_Project'))

NON_TROJAN_DIR = os.path.join(HTPRED_DIR, 'Non Trojan Files')
CANDIDATES_EXE = os.path.join(HW_DIR, 'bin', 'generate_candidates.exe')

DATA_DIR       = os.path.join(PROJECT_ROOT, 'data')
SHORT_CSV      = os.path.join(DATA_DIR, 'clean_feht_features.csv')
FEHT_DIR       = os.path.join(DATA_DIR, 'feht')
CAND_DIR       = os.path.join(DATA_DIR, 'candidates')
OUT_CSV        = os.path.join(DATA_DIR, 'feht_dataset.csv')
SUMMARY_JSON   = os.path.join(DATA_DIR, 'build_summary.json')

PREC_PATH      = os.path.join(DATA_DIR, 'precision_matrix.npy')
MEAN_PATH      = os.path.join(DATA_DIR, 'clean_mean.npy')
SCALER_PATH    = os.path.join(DATA_DIR, 'minmax_scaler.pkl')
COLS_PATH      = os.path.join(DATA_DIR, 'feature_columns.txt')

DROP_COLS = ['Label', 'Name of file', 'base_design', 'trojan_id', 'circuit', 'method', 'md_distance']

BENCH_EXTENSIONS = ('.bench', '.bench.txt', '.txt')

random.seed(42)
np.random.seed(42)


# ---------------------------------------------------------------------------
# Import MFP helpers (from mfp_selector.py in same attacker/ dir)
# ---------------------------------------------------------------------------
sys.path.insert(0, THIS_DIR)
from mfp_selector import extract_features_for_bench, mahalanobis_distance


# ---------------------------------------------------------------------------
# Mahalanobis distance
# ---------------------------------------------------------------------------

def compute_md(feat_raw, scaler, clean_mean, precision):
    feat_scaled = scaler.transform(feat_raw.reshape(1, -1))[0]
    return mahalanobis_distance(feat_scaled, clean_mean, precision)


# ---------------------------------------------------------------------------
# Step A: Generate candidates via C++ binary
# ---------------------------------------------------------------------------

def run_generate_candidates(bench_path, output_dir, payload='XOR', clique_size=2, timeout=180):
    """Calls generate_candidates.exe and returns (success, metadata_dict)."""
    os.makedirs(output_dir, exist_ok=True)
    cmd = [CANDIDATES_EXE, bench_path, output_dir, payload, str(clique_size)]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        meta_path = os.path.join(output_dir, 'candidate_metadata.json')
        if os.path.exists(meta_path):
            with open(meta_path) as f:
                meta = json.load(f)
            return True, meta
        else:
            return False, {'error': 'metadata not written', 'stderr': result.stderr[-500:]}
    except subprocess.TimeoutExpired:
        return False, {'error': f'timeout after {timeout}s'}
    except Exception as e:
        return False, {'error': str(e)}


# ---------------------------------------------------------------------------
# Step B: Extract features for all candidates + select ablation choices
# ---------------------------------------------------------------------------

def extract_all_candidates(candidates_dir, feature_cols, scaler, clean_mean, precision):
    """
    Extracts HTPred features for every candidate_*.bench in candidates_dir.
    Returns list of dicts: {file, feat_raw, feat_scaled, md_distance}
    """
    bench_files = sorted([
        f for f in os.listdir(candidates_dir)
        if f.startswith('candidate_') and f.endswith('.bench')
    ])

    results = []
    for bf in bench_files:
        bp = os.path.join(candidates_dir, bf)
        try:
            feat_raw = extract_features_for_bench(bp, label=1, feature_cols=feature_cols)
            md = compute_md(feat_raw, scaler, clean_mean, precision)
            results.append({'file': bf, 'feat_raw': feat_raw, 'md': md, 'path': bp})
        except Exception as e:
            print(f"    [WARN] Feature extraction failed for {bf}: {e}")
    return results


def pick_ablation_candidates(results, metadata_candidates):
    """
    Given the list of (file, feat, md) for all candidates and the metadata,
    selects 3 ablation variants:
      - mfp:        min Mahalanobis distance  (our method)
      - random:     random choice
      - graph_only: largest clique (most trigger nodes)
    Returns dict {method: result_entry}
    """
    if not results:
        return {}

    selections = {}

    # MFP — minimum Mahalanobis distance
    selections['mfp'] = min(results, key=lambda r: r['md'])

    # Random
    selections['random'] = random.choice(results)

    # Graph-only — candidate with the largest clique (most trigger nodes)
    # Metadata contains clique_size per candidate
    meta_by_file = {m['file']: m for m in metadata_candidates}
    def clique_size_of(r):
        return meta_by_file.get(r['file'], {}).get('clique_size', 0)
    selections['graph_only'] = max(results, key=clique_size_of)

    return selections


# ---------------------------------------------------------------------------
# Step C: Collect clean features from short_csv.csv
# ---------------------------------------------------------------------------

def load_clean_features(short_csv_path, feature_cols):
    """Returns dict {filename: feature_row_series} for Label=0 rows."""
    df = pd.read_csv(short_csv_path)
    clean = df[df['Label'] == 0].copy()
    name_col = 'Name of file' if 'Name of file' in clean.columns else None
    drop = [c for c in DROP_COLS if c in clean.columns]
    feat_df = clean.drop(columns=drop)
    feat_df = feat_df.apply(pd.to_numeric, errors='coerce').fillna(0)
    feat_aligned = feat_df.reindex(columns=feature_cols, fill_value=0)
    names = clean[name_col].tolist() if name_col else [f'clean_{i}' for i in range(len(feat_aligned))]
    return dict(zip(names, feat_aligned.values.tolist()))


# ---------------------------------------------------------------------------
# CSV writer helpers
# ---------------------------------------------------------------------------

def make_row(circuit, filename, method, label, feat_row, md, feature_cols):
    row = {
        'Name of file':  filename,
        'circuit':       circuit,
        'method':        method,
        'Label':         label,
        'md_distance':   round(md, 6) if md is not None else ''
    }
    for i, col in enumerate(feature_cols):
        row[col] = feat_row[i]
    return row


def get_csv_fieldnames(feature_cols):
    return ['Name of file', 'circuit', 'method', 'Label', 'md_distance'] + list(feature_cols)


# ---------------------------------------------------------------------------
# Main batch pipeline
# ---------------------------------------------------------------------------

def run_batch(dry_run=False, max_circuits=None, timeout_per_circuit=180):
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(FEHT_DIR, exist_ok=True)
    os.makedirs(CAND_DIR, exist_ok=True)

    # Verify prerequisites
    for p in [PREC_PATH, MEAN_PATH, SCALER_PATH, COLS_PATH]:
        if not os.path.exists(p):
            print(f"[ERROR] Missing precomputed artifact: {p}")
            print("  Run: python attacker/precompute_covariance.py  first.")
            sys.exit(1)
    if not os.path.exists(CANDIDATES_EXE):
        print(f"[ERROR] generate_candidates.exe not found at {CANDIDATES_EXE}")
        sys.exit(1)

    print("=" * 65)
    print("  build_feht_dataset.py -- Adversarial Co-Evaluation Framework")
    print("=" * 65)

    # Load precomputed artifacts
    precision  = np.load(PREC_PATH)
    clean_mean = np.load(MEAN_PATH)
    scaler     = joblib.load(SCALER_PATH)
    feature_cols = open(COLS_PATH).read().strip().split('\n')
    print(f"  Feature dims:      {len(feature_cols)}")

    # Load clean feature rows from short_csv
    print(f"  Loading clean features from short_csv.csv...")
    clean_feats = load_clean_features(SHORT_CSV, feature_cols)
    print(f"  Clean circuits in dataset: {len(clean_feats)}")

    # Enumerate bench files
    all_files = sorted([
        f for f in os.listdir(NON_TROJAN_DIR)
        if any(f.endswith(ext) for ext in BENCH_EXTENSIONS)
        and not f.startswith('.')
    ])
    if max_circuits:
        all_files = all_files[:max_circuits]
    if dry_run:
        all_files = all_files[:3]
        print(f"  [DRY RUN] Processing {len(all_files)} circuits only.")

    print(f"  Circuits to process: {len(all_files)}\n")

    # Summary tracking
    summary = {
        'total': len(all_files),
        'success': 0,
        'no_candidates': 0,
        'failed': 0,
        'circuits': {}
    }

    fieldnames = get_csv_fieldnames(feature_cols)
    csv_file = open(OUT_CSV, 'w', newline='', encoding='utf-8')
    writer = csv_module.DictWriter(csv_file, fieldnames=fieldnames)
    writer.writeheader()

    # Write clean rows first (from short_csv.csv — no re-extraction needed)
    print("[A] Writing clean circuit rows...")
    for fname, feat_row in clean_feats.items():
        circuit_name = fname.replace('.bench.txt', '').replace('.bench', '').replace('.txt', '')
        md = compute_md(np.array(feat_row), scaler, clean_mean, precision)
        row = make_row(circuit_name, fname, 'clean', 0, feat_row, md, feature_cols)
        writer.writerow(row)
    print(f"    Written {len(clean_feats)} clean rows.\n")

    # Process each circuit
    print("[B] Processing circuits for Trojan candidate selection...")
    for idx, bench_file in enumerate(all_files):
        bench_path   = os.path.join(NON_TROJAN_DIR, bench_file)
        circuit_name = bench_file.replace('.bench.txt', '').replace('.bench', '').replace('.txt', '')
        cand_dir     = os.path.join(CAND_DIR, circuit_name)
        feht_dir     = os.path.join(FEHT_DIR, circuit_name)
        os.makedirs(feht_dir, exist_ok=True)

        print(f"\n[{idx+1}/{len(all_files)}] {circuit_name}")
        t_start = time.time()
        circ_summary = {'bench_file': bench_file, 'status': 'failed',
                        'n_candidates': 0, 'methods': {}}

        # Step A: Generate candidates
        print(f"  [A] Generating candidates...")
        ok, meta = run_generate_candidates(bench_path, cand_dir,
                                           payload='XOR', clique_size=2,
                                           timeout=timeout_per_circuit)
        if not ok:
            print(f"  [SKIP] generate_candidates failed: {meta.get('error','?')}")
            circ_summary['status'] = 'generate_failed'
            circ_summary['error'] = meta.get('error', '?')
            summary['failed'] += 1
            summary['circuits'][circuit_name] = circ_summary
            continue

        n_cand = meta.get('total_candidates', 0)
        circ_summary['n_candidates'] = n_cand
        print(f"    Candidates: {n_cand}")

        if n_cand == 0:
            print(f"  [SKIP] No valid candidates for {circuit_name}.")
            circ_summary['status'] = 'no_candidates'
            summary['no_candidates'] += 1
            summary['circuits'][circuit_name] = circ_summary
            continue

        # Step B: Extract features for all candidates
        print(f"  [B] Extracting HTPred features for {n_cand} candidates...")
        all_results = extract_all_candidates(cand_dir, feature_cols, scaler, clean_mean, precision)

        if not all_results:
            print(f"  [SKIP] Feature extraction failed for all candidates.")
            circ_summary['status'] = 'extraction_failed'
            summary['failed'] += 1
            summary['circuits'][circuit_name] = circ_summary
            continue

        print(f"    Extracted: {len(all_results)}/{n_cand} candidates.")

        # Step C: Select ablation candidates
        metadata_candidates = meta.get('candidates', [])
        choices = pick_ablation_candidates(all_results, metadata_candidates)

        # Save distances CSV for this circuit
        dist_path = os.path.join(feht_dir, f'{circuit_name}_all_distances.csv')
        with open(dist_path, 'w', newline='') as df_file:
            dw = csv_module.DictWriter(df_file, fieldnames=['circuit', 'file', 'md_distance'])
            dw.writeheader()
            for r in sorted(all_results, key=lambda x: x['md']):
                dw.writerow({'circuit': circuit_name, 'file': r['file'],
                             'md_distance': round(r['md'], 6)})

        # Step D: Write rows + copy FEHT bench files
        for method, r in choices.items():
            # Copy .bench to feht dir
            dest_bench = os.path.join(feht_dir, f'{circuit_name}_{method}.bench')
            shutil.copy2(r['path'], dest_bench)

            # Write to CSV
            row = make_row(circuit_name, bench_file, method, 1,
                           r['feat_raw'].tolist(), r['md'], feature_cols)
            writer.writerow(row)
            circ_summary['methods'][method] = {'file': r['file'], 'md': round(r['md'], 6)}
            print(f"    [{method}]: {r['file']}  (MD={r['md']:.4f})")

        elapsed = time.time() - t_start
        circ_summary['status'] = 'success'
        circ_summary['elapsed_s'] = round(elapsed, 2)
        summary['success'] += 1
        summary['circuits'][circuit_name] = circ_summary
        print(f"  Done in {elapsed:.1f}s")

        # Flush periodically so output is saved even if interrupted
        csv_file.flush()

    csv_file.close()

    # Save summary JSON
    with open(SUMMARY_JSON, 'w') as f:
        json.dump(summary, f, indent=2)

    # Print final summary
    total_rows = summary['success'] * 3 + len(clean_feats)  # 3 methods per circuit
    print("\n" + "=" * 65)
    print("  BUILD SUMMARY")
    print("=" * 65)
    print(f"  Circuits attempted:      {summary['total']}")
    print(f"  Successfully processed:  {summary['success']}")
    print(f"  No candidates found:     {summary['no_candidates']}")
    print(f"  Errors/failures:         {summary['failed']}")
    print(f"  Clean rows written:      {len(clean_feats)}")
    print(f"  Trojan rows written:     {summary['success'] * 3}  (3 methods x circuits)")
    print(f"  Total rows in dataset:   {total_rows}")
    print(f"  Output CSV:              {OUT_CSV}")
    print(f"  Build summary JSON:      {SUMMARY_JSON}")
    print("=" * 65)
    print("\n[OK] feht_dataset.csv is ready. Next: run evaluate_baseline_dnn.py")

    return summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(description='Build FEHT dataset for all 91 circuits')
    p.add_argument('--dry_run', action='store_true',
                   help='Process only 3 circuits (quick sanity check)')
    p.add_argument('--circuits', type=int, default=None,
                   help='Process only first N circuits (default: all)')
    p.add_argument('--timeout', type=int, default=180,
                   help='Timeout per circuit in seconds (default: 180)')
    return p.parse_args()


if __name__ == '__main__':
    args = parse_args()
    run_batch(dry_run=args.dry_run,
              max_circuits=args.circuits,
              timeout_per_circuit=args.timeout)
