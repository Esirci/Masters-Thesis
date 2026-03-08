"""
evaluate_ganrl.py
=================
Adversarial Co-Evaluation Framework — Step 6 (Robustness Evaluation)

This script evaluates the Hybrid GAN-RL 'dqn_trojan_detector' against 
the strictly circuit-disjoint FEHT dataset generated in Phase 1.
"""

import os
import sys
import numpy as np
import pandas as pd
import joblib

from stable_baselines3 import DQN
from sklearn.metrics import accuracy_score, recall_score, precision_score, f1_score, confusion_matrix

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
THIS_DIR       = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT   = os.path.dirname(THIS_DIR)
DATA_DIR       = os.path.join(PROJECT_ROOT, 'data')
RESULTS_DIR    = os.path.join(PROJECT_ROOT, 'results')
DEFENDER_DIR   = os.path.join(PROJECT_ROOT, 'defender')

DATASET_PATH   = os.path.join(DATA_DIR, 'feht_dataset.csv')
DNN_SCALER     = os.path.join(DEFENDER_DIR, 'dnn_scaler.pkl')
RESULTS_CSV    = os.path.join(RESULTS_DIR, 'ganrl_robustness_results.csv')

# Load the RL model from the original project directory to ensure we test the exact validated model
RL_PROJECT_DIR = os.path.join(os.path.dirname(PROJECT_ROOT), 'Hybrid_GAN_RL_Architecture')
RL_MODEL_PATH  = os.path.join(RL_PROJECT_DIR, 'dqn_trojan_detector.zip')

DROP_COLS = ['Name of file', 'circuit', 'method', 'Label', 'md_distance']
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

# ---------------------------------------------------------------------------
# Evaluation Wrapper
# ---------------------------------------------------------------------------
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
    print(" Adversarial Co-Evaluation: GAN-RL Robustness Evaluation ")
    print("="*60)

    if not os.path.exists(DATASET_PATH):
        print(f"[ERROR] FEHT dataset not found: {DATASET_PATH}")
        sys.exit(1)

    if not os.path.exists(RL_MODEL_PATH):
        print(f"[ERROR] RL model not found at {RL_MODEL_PATH}")
        sys.exit(1)

    df = pd.read_csv(DATASET_PATH)
    _, test_df_full = create_circuit_disjoint_splits(df)

    y_test = test_df_full['Label'].values
    test_methods = test_df_full['method'].values

    scaler = joblib.load(DNN_SCALER)
    
    X_test_raw = test_df_full.drop(columns=[c for c in DROP_COLS if c in test_df_full.columns])
    X_test_log = preprocess_cap_log(X_test_raw)
    
    X_test_scaled_df = pd.DataFrame(scaler.transform(X_test_log), columns=X_test_raw.columns)
    obs_array = X_test_scaled_df.to_numpy().astype(np.float32)

    print(f"\n[1/3] Loading DQN Agent from: {RL_MODEL_PATH}")
    agent = DQN.load(RL_MODEL_PATH)

    # Validate feature shape!
    if agent.observation_space.shape[0] != obs_array.shape[1]:
        print(f"[ERROR] Model requires {agent.observation_space.shape[0]} features, but test set has {obs_array.shape[1]}")
        sys.exit(1)

    print("\n[2/3] Evaluating Agent on strictly circuit-disjoint FEHT test set...")
    
    results = []
    
    mask_clean = (test_methods == 'clean')
    res_clean = evaluate_rl_model("GAN-RL DQN", agent, obs_array, y_test, mask_clean)
    res_clean['Subset'] = 'Clean'
    results.append(res_clean)
    
    mask_rand = (test_methods == 'random')
    res_rand = evaluate_rl_model("GAN-RL DQN", agent, obs_array, y_test, mask_rand)
    res_rand['Subset'] = 'Trojan (Random)'
    results.append(res_rand)
    
    mask_graph = (test_methods == 'graph_only')
    res_graph = evaluate_rl_model("GAN-RL DQN", agent, obs_array, y_test, mask_graph)
    res_graph['Subset'] = 'Trojan (Graph-Only)'
    results.append(res_graph)
    
    mask_mfp = (test_methods == 'mfp')
    res_mfp = evaluate_rl_model("GAN-RL DQN", agent, obs_array, y_test, mask_mfp)
    res_mfp['Subset'] = 'Trojan (MFP FEHT)'
    results.append(res_mfp)

    mask_lg = (test_methods == 'loss_guided')
    res_lg = evaluate_rl_model("GAN-RL DQN", agent, obs_array, y_test, mask_lg)
    res_lg['Subset'] = 'Trojan (Loss-Guided)'
    results.append(res_lg)

    print("\n[3/3] GAN-RL Evaluation Results:")
    res_df = pd.DataFrame(results)
    res_df = res_df[['Detector', 'Subset', 'N_samples', 'Acc', 'TPR(Recall)', 'TNR', 'F1']]
    print("\n" + res_df.to_string(index=False) + "\n")

    os.makedirs(RESULTS_DIR, exist_ok=True)
    res_df.to_csv(RESULTS_CSV, index=False)
    print(f"[OK] Results saved to {RESULTS_CSV}")

if __name__ == '__main__':
    main()
