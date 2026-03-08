"""
create_cv_splits.py
-------------------
Generates 5 stratified folds from short_csv.csv.
Output folder: cv_splits/
  - fold_1_train.csv, fold_1_test.csv
  - fold_2_train.csv, fold_2_test.csv
  - ...
  - fold_5_train.csv, fold_5_test.csv

NO forced file assignments. Pure stratified k-fold.
"""

import pandas as pd
from sklearn.model_selection import StratifiedKFold
import os

DATA_PATH = "short_csv.csv"
OUTPUT_DIR = "cv_splits"
N_FOLDS = 5
SEED = 42


def main():
    if not os.path.exists(DATA_PATH):
        print(f"Error: {DATA_PATH} not found.")
        return

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"Reading {DATA_PATH}...")
    df = pd.read_csv(DATA_PATH)
    print(f"Total shape: {df.shape}")
    print(f"Label distribution:\n{df['Label'].value_counts()}\n")

    X = df.drop("Label", axis=1)
    y = df["Label"]

    skf = StratifiedKFold(n_splits=N_FOLDS, shuffle=True, random_state=SEED)

    for fold_idx, (train_idx, test_idx) in enumerate(skf.split(X, y), start=1):
        train_df = df.iloc[train_idx].reset_index(drop=True)
        test_df  = df.iloc[test_idx].reset_index(drop=True)

        train_path = os.path.join(OUTPUT_DIR, f"fold_{fold_idx}_train.csv")
        test_path  = os.path.join(OUTPUT_DIR, f"fold_{fold_idx}_test.csv")

        train_df.to_csv(train_path, index=False)
        test_df.to_csv(test_path,  index=False)

        print(f"Fold {fold_idx}: train={len(train_df)} "
              f"(T:{(train_df['Label']==1).sum()}, NT:{(train_df['Label']==0).sum()}) | "
              f"test={len(test_df)} "
              f"(T:{(test_df['Label']==1).sum()}, NT:{(test_df['Label']==0).sum()})")

    print(f"\nAll {N_FOLDS} folds saved to '{OUTPUT_DIR}/'")


if __name__ == "__main__":
    main()
