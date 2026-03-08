import pandas as pd
import numpy as np
from stable_baselines3 import DQN
from sklearn.preprocessing import StandardScaler
import os
import torch
import shap

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

    print("Loading data...")
    train_df = pd.read_csv(TRAIN_PATH)
    test_df = pd.read_csv(TEST_PATH)
    
    # 1. Preprocess
    cols_to_drop_train = [c for c in DROP_COLS if c in train_df.columns]
    X_train_raw = train_df.drop(cols_to_drop_train, axis=1)
    
    cols_to_drop_test = [c for c in DROP_COLS if c in test_df.columns]
    test_filenames = test_df["Name of file"]
    X_test_raw = test_df.drop(cols_to_drop_test, axis=1)
    
    X_train_proc = preprocess_cap_log(X_train_raw)
    X_test_proc = preprocess_cap_log(X_test_raw)
    
    # 2. Scale
    scaler = StandardScaler()
    scaler.fit(X_train_proc)
    X_train_scaled = pd.DataFrame(scaler.transform(X_train_proc), columns=X_train_raw.columns)
    X_test_scaled = pd.DataFrame(scaler.transform(X_test_proc), columns=X_test_raw.columns)
    
    # 3. Find c6288
    target_file = "c6288.txt"
    try:
        target_idx = test_filenames[test_filenames == target_file].index[0]
        # Adjust index because test_filenames index might match original df, but we need location in X_test_scaled
        # iloc is purely positional 0..N
        target_loc = test_filenames.tolist().index(target_file)
        
        print(f"Found {target_file} at index {target_loc}")
        target_sample = X_test_scaled.iloc[target_loc].to_numpy().reshape(1, -1)
        
    except IndexError:
        print(f"Error: {target_file} not found in test set. Listing first 5 files:")
        print(test_filenames.head())
        return

    print("Loading Model...")
    model = DQN.load(MODEL_PATH)
    
    # 4. Setup SHAP
    # Wrapper function: input is numpy array of features
    # output is Q(Trojan) - Q(Non-Trojan)
    # If output > 0, model predicts Trojan.
    
    def q_score_diff(X_numpy):
        # Ensure input is torch tensor
        X_torch = torch.as_tensor(X_numpy).float()
        with torch.no_grad():
            # Get Q-values from the policy's network
            q_values = model.policy.q_net(X_torch)
        # q_values shape: [batch_size, 2]
        # We want column 1 (Trojan) - column 0 (Non-Trojan)
        diff = q_values[:, 1] - q_values[:, 0]
        return diff.numpy()

    # Use a small background dataset (e.g., K-means summary or random sample)
    # Using 50 random samples from train for speed
    background = shap.sample(X_train_scaled, 50)
    
    print("Initializing SHAP KernelExplainer (this might take a minute)...")
    explainer = shap.KernelExplainer(q_score_diff, background)
    
    print(f"Calculating SHAP values for {target_file}...")
    shap_values = explainer.shap_values(target_sample)
    
    # 5. Output Results
    # shap_values is a list or array. For KernelExplainer with vector output, it matches output shape.
    # Here output is 1D (diff), so shap_values is [1, n_features]
    
    vals = shap_values[0] # The values for the single sample
    features = X_train_scaled.columns
    
    # Sort by absolute impact
    feature_importance = pd.DataFrame(list(zip(features, vals)), columns=['Feature', 'SHAP_Value'])
    feature_importance['Abs_SHAP'] = feature_importance['SHAP_Value'].abs()
    feature_importance = feature_importance.sort_values(by='Abs_SHAP', ascending=False)
    
    print("\n" + "="*60)
    print(f"SHAP Explanations for {target_file}")
    print("Positive SHAP -> Pushes towards 'Trojan' prediction")
    print("Negative SHAP -> Pushes towards 'Non-Trojan' prediction")
    print("="*60)
    
    print(feature_importance.head(10))
    print("="*60)
    
    # Explanation
    print("\nInterpretation:")
    top_feature = feature_importance.iloc[0]
    direction = "Trojan" if top_feature['SHAP_Value'] > 0 else "Non-Trojan"
    print(f"The most influential feature is '{top_feature['Feature']}' with a value of {top_feature['SHAP_Value']:.4f}.")
    print(f"This feature is pushing the model towards predicting: {direction}")

if __name__ == "__main__":
    main()
