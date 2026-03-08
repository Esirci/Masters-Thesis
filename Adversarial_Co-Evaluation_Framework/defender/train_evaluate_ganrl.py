"""
train_evaluate_ganrl.py
=======================
Adversarial Co-Evaluation Framework 

This script natively trains a new DQN agent on the new non-leaky
FEHT dataset train split (circuit-disjoint), bypassing the GAN augmentation
for speed, to see if the RL architecture's structural False-Positive penalty
design generates a naturally robust detector against the Evasion Attacks.
"""

import os
import sys
import numpy as np
import pandas as pd
import joblib

from stable_baselines3 import DQN
from stable_baselines3.common.env_checker import check_env
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, recall_score, precision_score, f1_score, confusion_matrix

from trojan_env import TrojanEnv

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
THIS_DIR       = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT   = os.path.dirname(THIS_DIR)
DATA_DIR       = os.path.join(PROJECT_ROOT, 'data')
RESULTS_DIR    = os.path.join(PROJECT_ROOT, 'results')
DEFENDER_DIR   = os.path.join(PROJECT_ROOT, 'defender')

DATASET_PATH   = os.path.join(DATA_DIR, 'feht_dataset.csv')
RL_MODEL_PATH  = os.path.join(DEFENDER_DIR, 'retrained_dqn_detector')
RESULTS_CSV    = os.path.join(RESULTS_DIR, 'retrained_rl_robustness.csv')

DROP_COLS = ['Name of file', 'circuit', 'method', 'Label', 'md_distance', 'base_design', 'trojan_id']
CAP = 1e12

# ---------------------------------------------------------------------------
# Preprocessing Logic
# ---------------------------------------------------------------------------
def preprocess_cap_log(X_df):
    X = X_df.astype(np.float64)
    X.replace([np.inf, -np.inf], np.nan, inplace=True)
    X = X.fillna(X.median(numeric_only=True))
    X = X.clip(lower=-CAP, upper=CAP)
    X = np.sign(X) * np.log1p(np.abs(X))
    return X.astype(np.float32)

def create_circuit_disjoint_splits(df):
    SEED = 42
    from sklearn.model_selection import train_test_split
    circuits = df['circuit'].unique()
    train_circuits, test_circuits = train_test_split(circuits, test_size=0.30, random_state=SEED)

    train_df = df[df['circuit'].isin(train_circuits)].copy()
    test_df  = df[df['circuit'].isin(test_circuits)].copy()
    return train_df, test_df

def evaluate_rl_model(name, model, env_obs, labels, method_mask):
    if len(labels) == 0:
        return {'Method': name, 'Acc': 0, 'TPR': 0, 'TNR': 0, 'F1': 0, 'Count': 0}

    obs_sub = env_obs[method_mask]
    lbl_sub = labels[method_mask]

    if len(lbl_sub) == 0:
        return {'Method': name, 'Acc': 0, 'TPR': 0, 'TNR': 0, 'F1': 0, 'Count': 0}

    predictions = []
    for i in range(len(obs_sub)):
        obs = obs_sub[i]
        action, _states = model.predict(obs, deterministic=True)
        predictions.append(action)

    predictions = np.array(predictions)
    acc = accuracy_score(lbl_sub, predictions)
    try:
        tn, fp, fn, tp = confusion_matrix(lbl_sub, predictions, labels=[0, 1]).ravel()
        tpr = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        tnr = tn / (tn + fp) if (tn + fp) > 0 else 0.0
    except ValueError:
        tpr = recall_score(lbl_sub, predictions, zero_division=0)
        tnr = 0.0 if np.all(lbl_sub == 1) else 1.0

    f1 = f1_score(lbl_sub, predictions, zero_division=0)

    return {
        'Detector': name,
        'Acc': round(acc, 4),
        'TPR(Recall)': round(tpr, 4),
        'TNR': round(tnr, 4),
        'F1': round(f1, 4),
        'N_samples': len(lbl_sub)
    }

def main():
    print("="*60)
    print(" Native DQN Retraining & Evasion Evaluation ")
    print("="*60)

    df = pd.read_csv(DATASET_PATH)
    train_df_full, test_df_full = create_circuit_disjoint_splits(df)
    
    # RL trains ONLY on Clean and Random Trojans (no evasive ones)
    train_df = train_df_full[train_df_full['method'].isin(['clean', 'random'])].copy()

    y_train = train_df['Label'].values
    y_test = test_df_full['Label'].values
    test_methods = test_df_full['method'].values

    X_train_raw = train_df.drop(columns=[c for c in DROP_COLS if c in train_df.columns])
    X_test_raw = test_df_full.drop(columns=[c for c in DROP_COLS if c in test_df_full.columns])

    print("[1/3] Preprocessing: Cap & Log & Scale")
    X_train_log = preprocess_cap_log(X_train_raw)
    X_test_log = preprocess_cap_log(X_test_raw)

    scaler = StandardScaler()
    X_train_scaled = pd.DataFrame(scaler.fit_transform(X_train_log), columns=X_train_raw.columns)
    X_test_scaled = pd.DataFrame(scaler.transform(X_test_log), columns=X_test_raw.columns)

    # Re-attach labels for TrojanEnv
    train_env_df = X_train_scaled.copy()
    train_env_df["Label"] = y_train

    print("[2/3] Training DQN Agent...")
    env = TrojanEnv(train_env_df)
    check_env(env)
    
    # Adjust timesteps so it converges quickly but accurately
    model = DQN("MlpPolicy", env, verbose=0, learning_rate=1e-4, buffer_size=50000, batch_size=32)
    model.learn(total_timesteps=15000)
    model.save(RL_MODEL_PATH)

    print("[3/3] Evaluating on completely unseen circuits...")
    obs_array = X_test_scaled.to_numpy().astype(np.float32)

    results = []
    for method in ['clean', 'random', 'graph_only', 'mfp', 'loss_guided']:
        mask = (test_methods == method)
        if method == 'clean':
            name = 'Clean'
        elif method == 'random':
            name = 'Trojan (Random)'
        elif method == 'graph_only':
            name = 'Trojan (Graph-Only)'
        elif method == 'mfp':
            name = 'Trojan (MFP FEHT)'
        else:
            name = 'Trojan (Loss-Guided)'
            
        res = evaluate_rl_model("Retrained RL", model, obs_array, y_test, mask)
        res['Subset'] = name
        results.append(res)

    res_df = pd.DataFrame(results)[['Detector', 'Subset', 'N_samples', 'Acc', 'TPR(Recall)', 'TNR', 'F1']]
    print("\n" + res_df.to_string(index=False) + "\n")
    res_df.to_csv(RESULTS_CSV, index=False)
    print(f"[OK] Saved to {RESULTS_CSV}")

if __name__ == '__main__':
    main()
