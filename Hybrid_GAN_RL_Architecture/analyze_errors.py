import pandas as pd
import numpy as np
from stable_baselines3 import DQN
from sklearn.preprocessing import StandardScaler
import os

# Paths
TRAIN_PATH = "train_split_augmented.csv" 
TEST_PATH = "test_split.csv" 
MODEL_PATH = "dqn_trojan_detector"

DROP_COLS = ["Name of file", "Label", "base_design", "trojan_id"]
CAP = 1e12

def preprocess_cap_log(X):
    X = X.astype(np.float64)
    X.replace([np.inf, -np.inf], np.nan, inplace=True)
    X = X.fillna(X.median(numeric_only=True))
    X = X.clip(lower=-CAP, upper=CAP)
    X = np.sign(X) * np.log1p(np.abs(X))
    return X.astype(np.float32)

def main():
    if not os.path.exists(MODEL_PATH + ".zip"):
        print(f"Error: Model {MODEL_PATH} not found.")
        return

    print("Loading data for context...")
    train_df = pd.read_csv(TRAIN_PATH)
    test_df = pd.read_csv(TEST_PATH)
    
    # We need to recreate the exact scaler used during training
    print("Recreating preprocessor...")
    
    # 1. Identify columns to drop (same logic as training)
    cols_to_drop_train = [c for c in DROP_COLS if c in train_df.columns]
    X_train_raw = train_df.drop(cols_to_drop_train, axis=1)
    
    cols_to_drop_test = [c for c in DROP_COLS if c in test_df.columns]
    # Keep the filenames for identifying the error!
    test_filenames = test_df["Name of file"]
    X_test_raw = test_df.drop(cols_to_drop_test, axis=1)
    
    y_test = test_df["Label"].values
    
    # 2. Cap & Log
    X_train_proc = preprocess_cap_log(X_train_raw)
    X_test_proc = preprocess_cap_log(X_test_raw)
    
    # 3. Fit Scaler on TRAIN, Apply to TEST
    scaler = StandardScaler()
    scaler.fit(X_train_proc)
    X_test_scaled = scaler.transform(X_test_proc)
    
    print("Loading Model...")
    model = DQN.load(MODEL_PATH)
    
    print("Predicting...")
    # Generate predictions
    predictions = []
    # stable-baselines3 predict expects numpy array
    for i in range(len(X_test_scaled)):
        obs = X_test_scaled[i]
        action, _ = model.predict(obs, deterministic=True)
        predictions.append(action)
        
    predictions = np.array(predictions)
    
    # Identify Errors
    print("\n--- MISCLASSIFICATION REPORT ---")
    errors_found = 0
    
    for i in range(len(y_test)):
        true_label = y_test[i]
        pred_label = predictions[i]
        
        if true_label != pred_label:
            errors_found += 1
            fname = test_filenames.iloc[i]
            error_type = "False Positive" if pred_label == 1 else "False Negative"
            print(f"File: {fname} | True: {true_label} | Pred: {pred_label} | Type: {error_type}")
            
    if errors_found == 0:
        print("Amazing! No errors found (Accuracy 100%).")
    else:
        print(f"\nTotal Errors: {errors_found}")

if __name__ == "__main__":
    main()
