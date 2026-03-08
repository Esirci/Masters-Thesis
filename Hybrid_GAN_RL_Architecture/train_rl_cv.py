"""
train_rl_cv.py
--------------
Trains and evaluates the DQN agent for a single CV fold.

Usage:
    python train_rl_cv.py --fold 1
    (trains on cv_augmented/fold_1_train_augmented.csv,
     evaluates on cv_splits/fold_1_test.csv,
     saves model to cv_models/fold_1_dqn)
"""

import argparse
import os
import json
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    accuracy_score, confusion_matrix, precision_score,
    recall_score, f1_score
)
from stable_baselines3 import DQN
from trojan_env import TrojanEnv   # reuse existing env

AUGMENTED_DIR = "cv_augmented"
SPLITS_DIR    = "cv_splits"
MODELS_DIR    = "cv_models"
RESULTS_DIR   = "cv_results"
TIMESTEPS     = 20_000
CAP           = 1e12

DROP_COLS = ["Name of file", "Label", "base_design", "trojan_id"]


def preprocess_cap_log(X: pd.DataFrame) -> np.ndarray:
    X = X.astype(np.float64)
    X.replace([np.inf, -np.inf], np.nan, inplace=True)
    X.fillna(X.median(numeric_only=True), inplace=True)
    X = X.clip(lower=-CAP, upper=CAP)
    X = np.sign(X) * np.log1p(np.abs(X))
    return X.astype(np.float32)


def main(fold: int):
    os.makedirs(MODELS_DIR, exist_ok=True)
    os.makedirs(RESULTS_DIR, exist_ok=True)

    train_path = os.path.join(AUGMENTED_DIR, f"fold_{fold}_train_augmented.csv")
    test_path  = os.path.join(SPLITS_DIR,    f"fold_{fold}_test.csv")
    model_path = os.path.join(MODELS_DIR,    f"fold_{fold}_dqn")

    print(f"\n=== Fold {fold}: RL Training ===")

    # ---- Load & Preprocess ----
    train_df = pd.read_csv(train_path)
    test_df  = pd.read_csv(test_path)

    drop_train = [c for c in DROP_COLS if c in train_df.columns]
    drop_test  = [c for c in DROP_COLS if c in test_df.columns]

    feat_cols = [c for c in train_df.columns if c not in DROP_COLS]
    X_train_raw = train_df[feat_cols]
    y_train     = train_df["Label"].astype(int).to_numpy()
    X_test_raw  = test_df[feat_cols]
    y_test      = test_df["Label"].astype(int).to_numpy()

    X_train_proc = preprocess_cap_log(X_train_raw.copy())
    X_test_proc  = preprocess_cap_log(X_test_raw.copy())

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train_proc)
    X_test_scaled  = scaler.transform(X_test_proc)

    # ---- Environment ----
    # TrojanEnv expects a DataFrame with a 'Label' column and feature columns.
    # Reconstruct one from the scaled arrays.
    col_names = [f"f{i}" for i in range(X_train_scaled.shape[1])]
    train_env_df = pd.DataFrame(X_train_scaled, columns=col_names)
    train_env_df["Label"] = y_train

    env = TrojanEnv(train_env_df)
    # Quick env check
    obs, _ = env.reset()
    assert obs.shape[0] == X_train_scaled.shape[1], "Observation shape mismatch!"

    # ---- Train DQN ----
    model = DQN(
        "MlpPolicy", env,
        learning_rate=1e-4,
        buffer_size=10_000,
        learning_starts=1_000,
        batch_size=32,
        verbose=1
    )
    model.learn(total_timesteps=TIMESTEPS)
    model.save(model_path)

    # ---- Evaluate ----
    predictions = []
    for i in range(len(X_test_scaled)):
        obs = X_test_scaled[i].reshape(1, -1)
        action, _ = model.predict(obs, deterministic=True)
        predictions.append(int(action))

    y_pred = np.array(predictions)
    cm = confusion_matrix(y_test, y_pred)
    tn, fp, fn, tp = cm.ravel()

    results = {
        "fold":     fold,
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "tpr":      float(recall_score(y_test, y_pred, zero_division=0)),
        "fpr":      float(fp / (fp + tn)) if (fp + tn) > 0 else 0.0,
        "precision":float(precision_score(y_test, y_pred, zero_division=0)),
        "f1":       float(f1_score(y_test, y_pred, zero_division=0)),
        "tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)
    }

    print(f"\nFold {fold} Results:")
    print(f"  Confusion Matrix [[TN FP],[FN TP]]: [[{tn} {fp}],[{fn} {tp}]]")
    print(f"  Accuracy:  {results['accuracy']:.4f}")
    print(f"  TPR:       {results['tpr']:.4f}")
    print(f"  FPR:       {results['fpr']:.4f}")
    print(f"  Precision: {results['precision']:.4f}")
    print(f"  F1:        {results['f1']:.4f}")

    result_path = os.path.join(RESULTS_DIR, f"fold_{fold}_results.json")
    with open(result_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Results saved → {result_path}")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--fold", type=int, required=True, help="Fold number (1-5)")
    args = parser.parse_args()
    main(args.fold)
