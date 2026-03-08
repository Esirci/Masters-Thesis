"""
extract_unrolled_clean.py
=========================
Adversarial Co-Evaluation Framework - Step 2 (Data Leakage Fix)

This script generates the `clean_unrolled.bench` for every benchmark circuit 
by invoking `generate_candidates.exe` with an impossible clique size (e.g., 9999).
It then runs HTPred feature extraction on these UNROLLED clean circuits.

This ensures the Golden (Clean) features mathematically align with the Trojan 
features, destroying the DFF -> Combinational data leakage vulnerability.

Outputs:
  data/clean_feht_features.csv
"""

import os
import sys
import subprocess
import pandas as pd
from mfp_selector import extract_features_for_bench

THIS_DIR      = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT  = os.path.dirname(THIS_DIR)
HTPRED_DIR    = os.path.abspath(os.path.join(PROJECT_ROOT, '..', 'HTPred-master'))
HW_DIR        = os.path.abspath(os.path.join(PROJECT_ROOT, '..', 'Hardware_Insertion_Project'))

NON_TROJAN_DIR = os.path.join(HTPRED_DIR, 'Non Trojan Files')
CANDIDATES_EXE = os.path.join(HW_DIR, 'bin', 'generate_candidates.exe')
DATA_DIR       = os.path.join(PROJECT_ROOT, 'data')
CAND_DIR       = os.path.join(DATA_DIR, 'candidates')
OUT_CSV        = os.path.join(DATA_DIR, 'clean_feht_features.csv')

def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(CAND_DIR, exist_ok=True)

    print("=========================================================")
    print("  Extracting Data-Leakage-Free Clean Features")
    print("=========================================================")

    all_files = sorted([
        f for f in os.listdir(NON_TROJAN_DIR)
        if any(f.endswith(ext) for ext in ('.bench', '.bench.txt', '.txt'))
        and not f.startswith('.')
    ])

    results = []
    
    for idx, bench_file in enumerate(all_files):
        print(f"[{idx+1}/{len(all_files)}] {bench_file}")
        bench_path = os.path.join(NON_TROJAN_DIR, bench_file)
        circuit_name = bench_file.replace('.bench.txt', '').replace('.bench', '').replace('.txt', '')
        
        c_dir = os.path.join(CAND_DIR, circuit_name)
        os.makedirs(c_dir, exist_ok=True)
        
        # 1. Output clean_unrolled.bench
        cmd = [CANDIDATES_EXE, bench_path, c_dir, 'XOR', '9999']
        try:
            subprocess.run(cmd, capture_output=True, timeout=30)
        except subprocess.TimeoutExpired:
            print(f"  [WARN] generate_candidates timed out for {circuit_name}")
            pass # it might have still written the unrolled bench!

        unrolled_path = os.path.join(c_dir, 'clean_unrolled.bench')
        if not os.path.exists(unrolled_path):
            print(f"  [ERROR] {unrolled_path} was not generated.")
            continue

        # 2. Extract features directly via HTPred
        import tempfile
        import shutil
        tmp_fd, tmp_csv = tempfile.mkstemp(suffix='.csv')
        os.close(tmp_fd)
        
        original_cwd = os.getcwd()
        try:
            if HTPRED_DIR not in sys.path:
                sys.path.insert(0, HTPRED_DIR)
            os.chdir(HTPRED_DIR)
            import main as htpred_main
            ok, err = htpred_main.process_single_file(
                full_path=os.path.abspath(unrolled_path),
                filename=os.path.basename(unrolled_path),
                label=0,
                csv_path=tmp_csv,
                force_write_headers=True
            )
        finally:
            os.chdir(original_cwd)

        if not ok:
            print(f"  [ERROR] Extraction failed: {err}")
            os.unlink(tmp_csv)
            continue

        df = pd.read_csv(tmp_csv)
        os.unlink(tmp_csv)
        
        row_dict = df.iloc[-1].to_dict()
        row_dict['Name of file'] = bench_file
        row_dict['circuit'] = circuit_name
        row_dict['Label'] = 0
        results.append(row_dict)
        print(f"  [OK] Extracted {len(row_dict)} features.")

    if results:
        df_out = pd.DataFrame(results)
        df_out.to_csv(OUT_CSV, index=False)
        print(f"\n[SUCCESS] Wrote {len(results)} clean unrolled rows to {OUT_CSV}")
    else:
        print("\n[FAILED] No features extracted.")

if __name__ == '__main__':
    main()
