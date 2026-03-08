import pandas as pd
import numpy as np
from ctgan import CTGAN
import torch
import os

# Reproducibility
SEED = 42
np.random.seed(SEED)
torch.manual_seed(SEED)

# Paths
TRAIN_PATH = "train_split.csv"
AUGMENTED_PATH = "train_split_augmented.csv"

def main():
    if not os.path.exists(TRAIN_PATH):
        print(f"Error: {TRAIN_PATH} not found.")
        return

    print(f"Loading {TRAIN_PATH}...")
    df = pd.read_csv(TRAIN_PATH)
    
    # 1. Identify Imbalance
    label_counts = df["Label"].value_counts()
    print(f"Original Label Counts:\n{label_counts}")
    
    target_label = 0
    majority_label = 1
    
    count_majority = label_counts.get(majority_label, 0)
    count_minority = label_counts.get(target_label, 0)
    
    features_to_generate = count_majority - count_minority
    
    if features_to_generate <= 0:
        print("Dataset is already balanced or minority class is actually majority. Skipping augmentation.")
        return

    print(f"Targeting balance. Need to generate {features_to_generate} samples for Label {target_label}.")

    # 2. Isolate Minority Class
    minority_df = df[df["Label"] == target_label].copy()
    
    # CTGAN requires identifying discrete columns.
    # In this dataset, most are continuous, but we might have some discrete ones.
    # We'll treat columns with < 20 unique values as discrete for now, excluding float columns unless they look categorical.
    # However, 'Label' is strictly discrete but we won't feed it to GAN training in this specific filtering way,
    # OR we can just feed the whole thing.
    # Strategy: Train ONLY on minority rows. The GAN learns the distribution of P(X | Y=0).
    
    # Drop Label dependent on implementation. CTGAN learns what it sees. 
    # If we feed it only Label=0 data, it will output Label=0 data (if we include the column).
    # It's safer to drop the label, generate features, and then re-attach Label=0.
    
    train_data = minority_df.drop("Label", axis=1)
    
    # Heuristic for discrete columns: object types or low cardinality integers
    discrete_columns = []
    for col in train_data.columns:
        if train_data[col].dtype == 'object' or train_data[col].nunique() < 10:
            discrete_columns.append(col)
            
    print(f"Identified {len(discrete_columns)} discrete columns.")

    # 3. Train CTGAN
    print("Initializing CTGAN...")
    ctgan = CTGAN(epochs=300, verbose=True, cuda=torch.cuda.is_available())
    
    print("Training CTGAN on minority class...")
    ctgan.fit(train_data, discrete_columns=discrete_columns)
    
    # 4. Generate Samples
    print(f"Generating {features_to_generate} synthetic samples...")
    synthetic_data = ctgan.sample(features_to_generate)

    # 5. Post-process: Solution A — Per-column clamping to real data range
    print("Post-processing: Clipping synthetic values to valid physical range...")

    # Compute per-column min/max from the REAL minority training data (train_data)
    col_min = train_data.min(numeric_only=True)
    col_max = train_data.max(numeric_only=True)

    # Detect integer-like columns (all real values are whole numbers)
    integer_cols = set()
    for col in train_data.columns:
        col_series = pd.to_numeric(train_data[col], errors='coerce').dropna()
        if len(col_series) > 0 and (col_series == col_series.round(0)).all():
            integer_cols.add(col)

    clipped_count = 0
    for col in synthetic_data.columns:
        if col == "Label":
            continue
        if col not in col_min.index:
            continue  # skip non-numeric or unknown columns

        # Force column to numeric first (object-dtype columns would otherwise be skipped)
        synthetic_data[col] = pd.to_numeric(synthetic_data[col], errors='coerce')

        # Clip to [real_min, real_max]
        before = synthetic_data[col].copy()
        synthetic_data[col] = synthetic_data[col].clip(
            lower=float(col_min[col]),
            upper=float(col_max[col])
        )
        n_clipped = (before != synthetic_data[col]).sum()
        if n_clipped > 0:
            clipped_count += 1

        # Round integer-like columns
        if col in integer_cols:
            synthetic_data[col] = synthetic_data[col].round(0).astype(int)

    # --- Final safety sweep ---
    # Some columns may have been stored as object dtype and skipped above,
    # or may have overflowed on astype(int). Force any remaining invalid
    # negatives to the real minimum (for columns that are always >= 0 in real data).
    safety_fixed = 0
    for col in train_data.columns:   # train_data already has Label dropped
        if col not in col_min.index:
            continue
        if float(col_min[col]) >= 0:  # real data never goes negative
            synth_numeric = pd.to_numeric(synthetic_data[col], errors='coerce')
            if (synth_numeric < 0).any():
                synthetic_data[col] = synth_numeric.clip(lower=float(col_min[col])).fillna(float(col_min[col]))
                if col in integer_cols:
                    synthetic_data[col] = synthetic_data[col].round(0).astype(int)
                safety_fixed += 1

    if safety_fixed > 0:
        print(f"  Safety sweep fixed {safety_fixed} additional columns.")

    print(f"  Clipped values in {clipped_count} columns (first pass).")
    n_neg_after = (synthetic_data.select_dtypes(include='number') < 0).sum().sum()
    print(f"  Remaining negative values after clipping: {n_neg_after}")

    # 6. Attach Label
    synthetic_data["Label"] = target_label

    # 7. Merge
    augmented_df = pd.concat([df, synthetic_data], ignore_index=True)
    
    print(f"Augmented shape: {augmented_df.shape}")
    print(f"New Label Counts:\n{augmented_df['Label'].value_counts()}")
    
    augmented_df.to_csv(AUGMENTED_PATH, index=False)
    print(f"Saved augmented dataset to {AUGMENTED_PATH}")

if __name__ == "__main__":
    main()
