import pandas as pd
import numpy as np

AUGMENTED_PATH = "train_split_augmented.csv"
TRAIN_PATH = "train_split.csv"

df_aug = pd.read_csv(AUGMENTED_PATH)
df_orig = pd.read_csv(TRAIN_PATH)

df_synthetic = df_aug.iloc[len(df_orig):]

feat_cols = [c for c in df_aug.columns if c not in ["Name of file", "Label", "base_design", "trojan_id"]]

print("=== REMAINING NEGATIVES ANALYSIS ===\n")
print(f"Total synthetic rows: {len(df_synthetic)}")

invalid_negatives = []   # col has negatives in synthetic but NOT in real data (bad)
valid_negatives = []     # col has negatives in synthetic AND in real data (ok)

for col in feat_cols:
    synth_col = pd.to_numeric(df_synthetic[col], errors='coerce')
    n_neg_synth = (synth_col < 0).sum()
    if n_neg_synth == 0:
        continue
    
    real_col = pd.to_numeric(df_orig[col], errors='coerce')
    real_min = real_col.min()
    
    if real_min >= 0:
        # Real data never goes negative -> this is invalid
        invalid_negatives.append((col, int(n_neg_synth), float(synth_col.min()), float(real_min)))
    else:
        # Real data itself has negatives -> this is fine, it's within the trained range
        valid_negatives.append((col, int(n_neg_synth), float(synth_col.min()), float(real_min)))

print(f"Columns with INVALID negatives (real_min >= 0, should have been clipped): {len(invalid_negatives)}")
print(f"Columns with VALID negatives (real_min < 0, acceptable): {len(valid_negatives)}\n")

if invalid_negatives:
    print("=== INVALID NEGATIVE COLUMNS (Top 10) ===")
    for col, n, smin, rmin in sorted(invalid_negatives, key=lambda x: -x[1])[:10]:
        print(f"  '{col}': {n} neg values | synth_min={smin:.4f} | real_min={rmin:.4f}")

if valid_negatives:
    print("\n=== VALID NEGATIVE COLUMNS (sample 5) ===")
    for col, n, smin, rmin in valid_negatives[:5]:
        print(f"  '{col}': {n} neg values | synth_min={smin:.4f} | real_min={rmin:.4f}")

total_invalid = sum(n for _, n, _, _ in invalid_negatives)
total_valid = sum(n for _, n, _, _ in valid_negatives)
print(f"\n=== SUMMARY ===")
print(f"Total INVALID negative cell values remaining: {total_invalid}")
print(f"Total VALID negative cell values (real data also negative): {total_valid}")
print(f"Total remaining negatives: {total_invalid + total_valid}")
