import pandas as pd
from sklearn.model_selection import train_test_split
import os

# Paths
DATA_PATH = "short_csv.csv"
TRAIN_PATH = "train_split.csv"
TEST_PATH = "test_split.csv"

# Files to explicitly force into the training set so the model learns their pattern.
# c6288.txt is the only Non-Trojan c6288 circuit but there are 110 Trojan c6288 variants.
# Without seeing c6288.txt as clean during training, the model defaults to "Trojan" for it.
FORCE_TRAIN_FILES = ["c6288.txt"]

def main():
    if not os.path.exists(DATA_PATH):
        print(f"Error: {DATA_PATH} not found.")
        return

    print(f"Reading {DATA_PATH}...")
    df = pd.read_csv(DATA_PATH)

    print(f"Total shape: {df.shape}")

    if "Label" not in df.columns:
        print("Error: 'Label' column not found in dataset.")
        print("Columns found:", df.columns.tolist())
        return

    print("Label distribution:\n", df["Label"].value_counts())

    # --- Forced assignment ---
    # Pull out rows that must be in the training set
    if "Name of file" in df.columns:
        forced_train_mask = df["Name of file"].isin(FORCE_TRAIN_FILES)
        forced_train = df[forced_train_mask]
        remaining = df[~forced_train_mask]
        if len(forced_train) > 0:
            print(f"\nForcing {len(forced_train)} file(s) into training set: {FORCE_TRAIN_FILES}")
    else:
        forced_train = pd.DataFrame()
        remaining = df
        print("Warning: 'Name of file' column not found. Cannot force-assign files.")

    # --- Stratified split on the remaining rows ---
    train_df, test_df = train_test_split(
        remaining,
        test_size=0.2,
        random_state=42,
        stratify=remaining["Label"]
    )

    # Append forced rows to training
    if len(forced_train) > 0:
        train_df = pd.concat([train_df, forced_train], ignore_index=True)

    print(f"\nTrain shape: {train_df.shape}")
    print(f"Test shape: {test_df.shape}")
    print(f"\nTrain label distribution:\n{train_df['Label'].value_counts()}")
    print(f"\nTest label distribution:\n{test_df['Label'].value_counts()}")

    # Verify forced files are in train
    if "Name of file" in df.columns and len(forced_train) > 0:
        in_train = train_df["Name of file"].isin(FORCE_TRAIN_FILES).any()
        in_test = test_df["Name of file"].isin(FORCE_TRAIN_FILES).any()
        print(f"\nVerification — c6288.txt in train: {in_train}, in test: {in_test}")

    train_df.to_csv(TRAIN_PATH, index=False)
    test_df.to_csv(TEST_PATH, index=False)
    print(f"\nSaved to {TRAIN_PATH} and {TEST_PATH}")

if __name__ == "__main__":
    main()

