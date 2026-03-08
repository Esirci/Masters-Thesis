"""
precompute_covariance.py
========================
Adversarial Co-Evaluation Framework — Step 2a (run once before MFP selection)

Computes the Ledoit-Wolf precision matrix (inverse covariance) from the 91
clean (Label=0) circuits in HTPred's data.csv, and saves:
  - data/precision_matrix.npy   : precision matrix Σ⁻¹ (shape: 605×605)
  - data/minmax_scaler.pkl      : fitted MinMaxScaler

Run from the Adversarial_Co-Evaluation_Framework directory:
    python attacker/precompute_covariance.py

The precision matrix is used by mfp_selector.py to compute:
    d_M(x) = sqrt((x - μ)^T Σ⁻¹ (x - μ))
for each candidate, where μ is the mean of the clean distribution.
"""

import os
import sys
import numpy as np
import pandas as pd
import joblib
from sklearn.covariance import LedoitWolf
from sklearn.preprocessing import MinMaxScaler

# ---------------------------------------------------------------------------
# Paths (relative to project root — run from Adversarial_Co-Evaluation_Framework/)
# ---------------------------------------------------------------------------
HTPRED_DIR   = os.path.join(os.path.dirname(__file__), '..', '..', 'HTPred-master')
HTRPED_DIR   = os.path.abspath(HTPRED_DIR)
DATA_CSV     = os.path.join(os.path.dirname(__file__), '..', 'data', 'clean_feht_features.csv')  # 605 features — unrolled clean features
OUT_DIR      = os.path.join(os.path.dirname(__file__), '..', 'data')
OUT_PREC     = os.path.join(OUT_DIR, 'precision_matrix.npy')
OUT_MEAN     = os.path.join(OUT_DIR, 'clean_mean.npy')
OUT_SCALER   = os.path.join(OUT_DIR, 'minmax_scaler.pkl')
OUT_COLS     = os.path.join(OUT_DIR, 'feature_columns.txt')

# Columns to drop (metadata / label)
DROP_COLS = ['Label', 'Name of file', 'base_design', 'trojan_id', 'circuit', 'method', 'md_distance']


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    print("=" * 60)
    print("  precompute_covariance.py")
    print("  Adversarial Co-Evaluation Framework — Step 2a")
    print("=" * 60)

    # ------------------------------------------------------------------
    # 1. Load data.csv and filter to clean (Label=0) rows
    # ------------------------------------------------------------------
    print(f"\n[1/4] Loading {DATA_CSV} ...")
    if not os.path.exists(DATA_CSV):
        print(f"[ERROR] data.csv not found at {DATA_CSV}")
        sys.exit(1)

    df = pd.read_csv(DATA_CSV)
    print(f"  Total rows: {len(df)}")
    print(f"  Label distribution:\n{df['Label'].value_counts().to_string()}")

    # Keep only clean circuits
    clean_df = df[df['Label'] == 0].copy()
    print(f"\n  Clean rows (Label=0): {len(clean_df)}")

    # Drop metadata/label columns
    drop = [c for c in DROP_COLS if c in clean_df.columns]
    feature_df = clean_df.drop(columns=drop)
    print(f"  Feature columns after drop: {feature_df.shape[1]}")

    # Save column order (must match what mfp_selector uses)
    feature_cols = list(feature_df.columns)
    with open(OUT_COLS, 'w') as f:
        for col in feature_cols:
            f.write(col + '\n')
    print(f"  Saved feature column list -> {OUT_COLS}")

    # ------------------------------------------------------------------
    # 2. Convert to numeric, fill NaN
    # ------------------------------------------------------------------
    print("\n[2/4] Preprocessing ...")
    X = feature_df.apply(pd.to_numeric, errors='coerce').fillna(0).to_numpy(dtype=float)
    print(f"  Matrix shape: {X.shape}")

    # ------------------------------------------------------------------
    # 3. MinMax scale → [0, 1]
    # ------------------------------------------------------------------
    print("\n[3/4] Fitting MinMaxScaler ...")
    scaler = MinMaxScaler()
    X_scaled = scaler.fit_transform(X)
    joblib.dump(scaler, OUT_SCALER)
    print(f"  Scaler saved -> {OUT_SCALER}")

    # Compute and save clean mean (in scaled space)
    clean_mean = np.mean(X_scaled, axis=0)
    np.save(OUT_MEAN, clean_mean)
    print(f"  Clean mean saved -> {OUT_MEAN}  (shape: {clean_mean.shape})")

    # ------------------------------------------------------------------
    # 4. Ledoit-Wolf shrinkage covariance -> precision matrix
    # ------------------------------------------------------------------
    print("\n[4/4] Fitting Ledoit-Wolf covariance estimator ...")
    lw = LedoitWolf(assume_centered=False)
    lw.fit(X_scaled)

    precision = lw.precision_   # Σ⁻¹ — what we need for Mahalanobis
    shrinkage = lw.shrinkage_

    np.save(OUT_PREC, precision)
    print(f"  Precision matrix saved -> {OUT_PREC}  (shape: {precision.shape})")
    print(f"  Ledoit-Wolf shrinkage coefficient: {shrinkage:.6f}")
    print(f"  (Shrinkage ~0 = empirical; ~1 = diagonal; intermediate = regularized)")

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("  SUMMARY")
    print("=" * 60)
    print(f"  Clean training circuits: {len(clean_df)}")
    print(f"  Feature dimensions:      {X.shape[1]}")
    print(f"  Shrinkage coefficient:   {shrinkage:.6f}")
    print(f"  Precision matrix:        {OUT_PREC}")
    print(f"  Clean mean vector:       {OUT_MEAN}")
    print(f"  MinMax scaler:           {OUT_SCALER}")
    print(f"  Feature column order:    {OUT_COLS}")
    print("=" * 60)
    print("\n[OK] Precomputation complete. Run mfp_selector.py next.")



if __name__ == '__main__':
    main()
