"""
gan_augmentation_cv.py
-----------------------
Runs CTGAN augmentation on a single fold's training CSV.
Applies per-column physical clamping (Solution A) to prevent
negative values and integer overflow in synthetic data.

Usage:
    python gan_augmentation_cv.py --fold 1
    (runs on cv_splits/fold_1_train.csv → cv_augmented/fold_1_train_augmented.csv)
"""

import argparse
import pandas as pd
import numpy as np
from ctgan import CTGAN
import torch
import os

SEED = 42
CAP = 1e12
EPOCHS = 300
INPUT_DIR  = "cv_splits"
OUTPUT_DIR = "cv_augmented"

np.random.seed(SEED)
torch.manual_seed(SEED)


def preprocess_for_ctgan(df):
    """Drop non-numeric string columns before feeding to CTGAN."""
    return df.select_dtypes(include=[np.number])


def apply_constraints(synthetic_data, train_data):
    """Clip synthetic values to [real_min, real_max] and round integer-like columns."""
    col_min = train_data.min(numeric_only=True)
    col_max = train_data.max(numeric_only=True)

    integer_cols = set()
    for col in train_data.columns:
        series = pd.to_numeric(train_data[col], errors='coerce').dropna()
        if len(series) > 0 and (series == series.round(0)).all():
            integer_cols.add(col)

    clipped_count = 0
    for col in synthetic_data.columns:
        if col not in col_min.index:
            continue
        synthetic_data[col] = pd.to_numeric(synthetic_data[col], errors='coerce')
        before = synthetic_data[col].copy()
        synthetic_data[col] = synthetic_data[col].clip(
            lower=float(col_min[col]), upper=float(col_max[col])
        )
        if (before != synthetic_data[col]).sum() > 0:
            clipped_count += 1
        if col in integer_cols:
            synthetic_data[col] = synthetic_data[col].round(0).astype(int)

    # Safety sweep: fix any remaining invalid negatives (int64 overflow)
    safety_fixed = 0
    for col in train_data.columns:
        if col not in col_min.index:
            continue
        if float(col_min[col]) >= 0:
            synth_num = pd.to_numeric(synthetic_data[col], errors='coerce')
            if (synth_num < 0).any():
                synthetic_data[col] = synth_num.clip(lower=float(col_min[col])).fillna(float(col_min[col]))
                if col in integer_cols:
                    synthetic_data[col] = synthetic_data[col].round(0).astype(int)
                safety_fixed += 1

    n_neg = (synthetic_data.select_dtypes(include='number') < 0).sum().sum()
    print(f"  Columns clipped: {clipped_count} | Safety sweep fixed: {safety_fixed} | Remaining negatives: {n_neg}")
    return synthetic_data


def main(fold: int):
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    train_path = os.path.join(INPUT_DIR, f"fold_{fold}_train.csv")
    out_path   = os.path.join(OUTPUT_DIR, f"fold_{fold}_train_augmented.csv")

    if not os.path.exists(train_path):
        print(f"Error: {train_path} not found. Run create_cv_splits.py first.")
        return

    print(f"\n=== Fold {fold}: GAN Augmentation ===")
    df = pd.read_csv(train_path)
    print(f"Loaded {len(df)} rows — Labels: {df['Label'].value_counts().to_dict()}")

    label_counts = df["Label"].value_counts()
    count_majority = label_counts.get(1, 0)
    count_minority = label_counts.get(0, 0)
    n_to_generate  = count_majority - count_minority

    if n_to_generate <= 0:
        print("Already balanced. Saving as-is.")
        df.to_csv(out_path, index=False)
        return

    print(f"Need to generate {n_to_generate} Non-Trojan samples.")

    # Isolate minority class features (drop Label)
    DROP_COLS = ["Name of file", "Label", "base_design", "trojan_id"]
    minority_df  = df[df["Label"] == 0].copy()
    drop_present = [c for c in DROP_COLS if c in minority_df.columns]
    train_data   = minority_df.drop(drop_present, axis=1)
    train_data   = preprocess_for_ctgan(train_data)

    discrete_columns = [
        col for col in train_data.columns
        if train_data[col].dtype == 'object' or train_data[col].nunique() < 10
    ]
    print(f"Discrete columns identified: {len(discrete_columns)}")

    print(f"Training CTGAN ({EPOCHS} epochs)...")
    ctgan = CTGAN(epochs=EPOCHS, verbose=True, cuda=torch.cuda.is_available())
    ctgan.fit(train_data, discrete_columns=discrete_columns)

    print(f"Generating {n_to_generate} samples...")
    synthetic_data = ctgan.sample(n_to_generate)

    print("Applying physical constraints...")
    synthetic_data = apply_constraints(synthetic_data, train_data)
    synthetic_data["Label"] = 0

    # Defragment before concat to suppress PerformanceWarning
    synthetic_data = synthetic_data.copy()

    augmented_df = pd.concat([df, synthetic_data], ignore_index=True)
    print(f"Augmented shape: {augmented_df.shape} — Labels: {augmented_df['Label'].value_counts().to_dict()}")
    augmented_df.to_csv(out_path, index=False)
    print(f"Saved → {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--fold", type=int, required=True, help="Fold number (1-5)")
    args = parser.parse_args()
    main(args.fold)
