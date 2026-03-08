"""
evaluate_baseline_dnn.py
========================
Adversarial Co-Evaluation Framework — Step 5 (Evasion Evaluation)

This script trains baseline classifiers (DNN, Random Forest, Decision Tree)
on a CLEAN vs RANDOM_TROJAN dataset, then evaluates them on a strict
CIRCUIT-DISJOINT test set of FEHT candidates (MFP, Random, Graph-Only)
to measure Attack Success Rate (ASR) / Accuracy Drop.

It outputs exactly how vulnerable baseline detectors are to feature evasion.
"""

import os
import sys
import json
import numpy as np
import pandas as pd
import joblib

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier
from sklearn.tree import DecisionTreeClassifier
from sklearn.metrics import accuracy_score, recall_score, precision_score, f1_score, confusion_matrix

import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Dropout
from tensorflow.keras.callbacks import EarlyStopping

# ---------------------------------------------------------------------------
# Paths & Config
# ---------------------------------------------------------------------------
THIS_DIR     = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(THIS_DIR)
DATA_DIR     = os.path.join(PROJECT_ROOT, 'data')
RESULTS_DIR  = os.path.join(PROJECT_ROOT, 'results')
DEFENDER_DIR = os.path.join(PROJECT_ROOT, 'defender')

DATASET_PATH = os.path.join(DATA_DIR, 'feht_dataset.csv')
DNN_MODEL_PATH = os.path.join(DEFENDER_DIR, 'baseline_dnn_model.keras')
SCALER_PATH  = os.path.join(DEFENDER_DIR, 'dnn_scaler.pkl')
RESULTS_CSV  = os.path.join(RESULTS_DIR, 'baseline_evasion_results.csv')

DROP_COLS = ['Name of file', 'circuit', 'method', 'Label', 'md_distance']
CAP = 1e12

# Reproducibility
SEED = 42
np.random.seed(SEED)
tf.random.set_seed(SEED)

os.makedirs(RESULTS_DIR, exist_ok=True)
os.makedirs(DEFENDER_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Preprocessing (Identical to original HTPred/GAN-RL pipeline)
# ---------------------------------------------------------------------------
def preprocess_cap_log(X_df):
    """Stable log1p transform matching Hybrid GAN-RL project."""
    X = X_df.astype(np.float64)
    X.replace([np.inf, -np.inf], np.nan, inplace=True)
    X = X.fillna(X.median(numeric_only=True))
    X = X.clip(lower=-CAP, upper=CAP)
    X = np.sign(X) * np.log1p(np.abs(X))
    return X

# ---------------------------------------------------------------------------
# Circuit-Disjoint Splitting
# ---------------------------------------------------------------------------
def create_circuit_disjoint_splits(df):
    """
    Groups data by base 'circuit'. 
    Assigns 70% of circuits to Train, 30% to Test.
    Ensures that test circuits are entirely unseen during training.
    """
    circuits = df['circuit'].unique()
    train_circuits, test_circuits = train_test_split(circuits, test_size=0.30, random_state=SEED)
    
    print(f"\n[Splits] Total circuits: {len(circuits)}")
    print(f"  Train circuits: {len(train_circuits)} -> {train_circuits[:5]}...")
    print(f"  Test circuits:  {len(test_circuits)} -> {test_circuits[:5]}...")

    train_df = df[df['circuit'].isin(train_circuits)].copy()
    test_df  = df[df['circuit'].isin(test_circuits)].copy()
    
    return train_df, test_df

# ---------------------------------------------------------------------------
# DNN Architecture (matches baseline_dnn.py from Hybrid GAN-RL)
# ---------------------------------------------------------------------------
def build_dnn_model(input_dim):
    model = Sequential([
        Dense(20, activation='relu', input_shape=(input_dim,)),
        Dense(20, activation='relu'),
        Dense(20, activation='relu'),
        Dense(20, activation='relu'),
        Dense(20, activation='relu'),
        Dense(1, activation='sigmoid')
    ])
    model.compile(optimizer='adam', loss='binary_crossentropy', metrics=['accuracy'])
    return model

# ---------------------------------------------------------------------------
# Evaluation Helper
# ---------------------------------------------------------------------------
def evaluate_model(name, model, is_keras, X_test, y_test, method_mask):
    """Returns metrics for a specific subset of test data (e.g., only 'mfp' Trojans)."""
    if len(y_test) == 0:
        return {'Method': name, 'Acc': 0, 'TPR': 0, 'TNR': 0, 'F1': 0, 'Count': 0}
        
    X_sub = X_test[method_mask]
    y_sub = y_test[method_mask]
    
    if len(y_sub) == 0:
        return {'Method': name, 'Acc': 0, 'TPR': 0, 'TNR': 0, 'F1': 0, 'Count': 0}

    if is_keras:
        preds_prob = model.predict(X_sub, verbose=0)
        preds = (preds_prob > 0.5).astype(int).flatten()
    else:
        preds = model.predict(X_sub)
        
    acc = accuracy_score(y_sub, preds)
    # If purely testing Trojans, TNR is undefined. We use Recall (TPR) as the main metric.
    try:
        tn, fp, fn, tp = confusion_matrix(y_sub, preds, labels=[0, 1]).ravel()
        tpr = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        tnr = tn / (tn + fp) if (tn + fp) > 0 else 0.0
    except ValueError:
        # Happens if test set has only 1 class
        tpr = recall_score(y_sub, preds, zero_division=0)
        tnr = 0.0 if np.all(y_sub == 1) else 1.0
        
    f1 = f1_score(y_sub, preds, zero_division=0)
    
    return {
        'Detector': name,
        'Acc': round(acc, 4),
        'TPR(Recall)': round(tpr, 4),
        'TNR': round(tnr, 4),
        'F1': round(f1, 4),
        'N_samples': len(y_sub)
    }

# ---------------------------------------------------------------------------
# Main Execution
# ---------------------------------------------------------------------------
def main():
    if not os.path.exists(DATASET_PATH):
        print(f"[ERROR] Dataset not found: {DATASET_PATH}")
        sys.exit(1)

    print("="*60)
    print(" Adversarial Co-Evaluation: Baseline Detector Vulnerability ")
    print("="*60)
    
    # 1. Load Data
    df = pd.read_csv(DATASET_PATH)
    print(f"Loaded dataset: {df.shape[0]} rows, {df.shape[1]} columns.")
    
    # We only train the baseline on standard Random insertions (to simulate a defender
    # who hasn't seen evasive Trojans) and Clean circuits.
    # The Test set will contain ALL methods to see how the detector reacts.
    
    train_df_full, test_df_full = create_circuit_disjoint_splits(df)
    
    # Train set: Only 'clean' and 'random' rows
    train_df = train_df_full[train_df_full['method'].isin(['clean', 'random'])].copy()
    
    y_train = train_df['Label'].values
    y_test  = test_df_full['Label'].values
    
    train_methods = train_df['method'].values
    test_methods  = test_df_full['method'].values
    
    # 2. Preprocess Features
    X_train_raw = train_df.drop(columns=[c for c in DROP_COLS if c in train_df.columns])
    X_test_raw  = test_df_full.drop(columns=[c for c in DROP_COLS if c in test_df_full.columns])
    
    X_train_log = preprocess_cap_log(X_train_raw)
    X_test_log  = preprocess_cap_log(X_test_raw)
    
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train_log)
    X_test_scaled  = scaler.transform(X_test_log)
    
    # Save scaler for Loss-Guided script later
    joblib.dump(scaler, SCALER_PATH)
    
    print(f"\n[Training Data] Clean: {np.sum(y_train==0)}, Trojans (Random only): {np.sum(y_train==1)}")
    print(f"[Testing Data]  Clean: {np.sum(train_methods=='clean')} (train circuits) + {np.sum(test_methods=='clean')} (test circuits)")
    print(f"                Trojans in test set: Random({np.sum(test_methods=='random')}), "
          f"Graph-Only({np.sum(test_methods=='graph_only')}), MFP({np.sum(test_methods=='mfp')}), "
          f"Loss-Guided({np.sum(test_methods=='loss_guided')})")

    # 3. Train Models
    print("\n--- Training Models on Circuit-Disjoint Train Set (Clean + Random Trojans) ---")
    
    # A. DNN
    print("Training DNN Baseline...")
    dnn = build_dnn_model(X_train_scaled.shape[1])
    es = EarlyStopping(monitor='loss', patience=3, restore_best_weights=True)
    dnn.fit(X_train_scaled, y_train, epochs=30, batch_size=16, verbose=0, callbacks=[es])
    dnn.save(DNN_MODEL_PATH)
    
    # B. Random Forest
    print("Training Random Forest...")
    rf = RandomForestClassifier(n_estimators=100, random_state=SEED)
    rf.fit(X_train_scaled, y_train)
    
    # C. Decision Tree
    print("Training Decision Tree...")
    dt = DecisionTreeClassifier(random_state=SEED)
    dt.fit(X_train_scaled, y_train)
    
    # 4. Evaluate Models
    print("\n--- Evaluating Models on Circuit-Disjoint Test Set ---")
    print("We test the models against the unseen Clean circuits, and the three Trojan insertion methods.\n")
    
    results = []
    
    for model_name, model, is_keras in [("DNN", dnn, True), ("Random Forest", rf, False), ("Decision Tree", dt, False)]:
        # Evaluate on Clean (TNR)
        mask_clean = (test_methods == 'clean')
        res_clean = evaluate_model(model_name, model, is_keras, X_test_scaled, y_test, mask_clean)
        res_clean['Subset'] = 'Clean'
        results.append(res_clean)
        
        # Evaluate on Random Trojans (TPR)
        mask_random = (test_methods == 'random')
        res_rand = evaluate_model(model_name, model, is_keras, X_test_scaled, y_test, mask_random)
        res_rand['Subset'] = 'Trojan (Random)'
        results.append(res_rand)
        
        # Evaluate on Graph-Only Trojans (TPR)
        mask_graph = (test_methods == 'graph_only')
        res_graph = evaluate_model(model_name, model, is_keras, X_test_scaled, y_test, mask_graph)
        res_graph['Subset'] = 'Trojan (Graph-Only)'
        results.append(res_graph)
        
        # Evaluate on MFP Trojans (TPR)
        mask_mfp = (test_methods == 'mfp')
        res_mfp = evaluate_model(model_name, model, is_keras, X_test_scaled, y_test, mask_mfp)
        res_mfp['Subset'] = 'Trojan (MFP FEHT)'
        results.append(res_mfp)
        
        # Evaluate on Loss-Guided Trojans (TPR)
        mask_lg = (test_methods == 'loss_guided')
        res_lg = evaluate_model(model_name, model, is_keras, X_test_scaled, y_test, mask_lg)
        res_lg['Subset'] = 'Trojan (Loss-Guided)'
        results.append(res_lg)

    # 5. Display and Save Results
    res_df = pd.DataFrame(results)
    # Reorder columns clearly
    res_df = res_df[['Detector', 'Subset', 'N_samples', 'Acc', 'TPR(Recall)', 'TNR', 'F1']]
    
    print(res_df.to_string(index=False))
    res_df.to_csv(RESULTS_CSV, index=False)
    
    print(f"\n[OK] Results saved to {RESULTS_CSV}")
    print(f"[OK] Trained DNN saved to {DNN_MODEL_PATH}")
    print("\nNext: Run attacker/loss_guided_selector.py to generate the Loss-Guided adversarial baseline.")

if __name__ == "__main__":
    main()
