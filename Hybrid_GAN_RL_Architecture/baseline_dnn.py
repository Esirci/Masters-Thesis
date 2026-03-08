import os
import random
import numpy as np
import pandas as pd

import tensorflow as tf
from sklearn.preprocessing import StandardScaler
from sklearn.utils.class_weight import compute_class_weight
from sklearn.metrics import (
    confusion_matrix, accuracy_score, precision_score, recall_score, f1_score,
    matthews_corrcoef, roc_auc_score, precision_recall_curve, auc, log_loss
)

# -----------------
# Reproducibility
# -----------------
SEED = 42
os.environ["PYTHONHASHSEED"] = str(SEED)
random.seed(SEED)
np.random.seed(SEED)
tf.random.set_seed(SEED)

# -----------------
# Paths
# -----------------
TRAIN_PATH = "train_split.csv"              # change to train_split_augmented.csv for augmented
TEST_PATH  = "test_split.csv"

DROP_COLS = ["Name of file", "Label", "base_design", "trojan_id"]
CAP = 1e12

def preprocess_cap_log(X: pd.DataFrame) -> np.ndarray:
    """Same stable transform you used before (but returns numpy)."""
    X = X.astype(np.float64)
    X.replace([np.inf, -np.inf], np.nan, inplace=True)
    X = X.fillna(X.median(numeric_only=True))
    X = X.clip(lower=-CAP, upper=CAP)
    X = np.sign(X) * np.log1p(np.abs(X))
    return X.to_numpy(dtype=np.float64)

def main():
    if not os.path.exists(TRAIN_PATH):
        print(f"Error: {TRAIN_PATH} not found. Please run create_splits.py first.")
        return
    if not os.path.exists(TEST_PATH):
        print(f"Error: {TEST_PATH} not found. Please run create_splits.py first.")
        return

    train_df = pd.read_csv(TRAIN_PATH)
    test_df = pd.read_csv(TEST_PATH)

    feat_cols = [c for c in train_df.columns if c not in DROP_COLS]

    X_train_raw = preprocess_cap_log(train_df[feat_cols].copy())
    y_train = train_df["Label"].astype(int).to_numpy()

    X_test_raw = preprocess_cap_log(test_df[feat_cols].copy())
    y_test = test_df["Label"].astype(int).to_numpy()

    # ---- Standardize for DNN ----
    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train_raw)
    X_test = scaler.transform(X_test_raw)

    n_features = X_train.shape[1]

    # ---- class weights ----
    classes = np.unique(y_train)
    weights = compute_class_weight(class_weight="balanced", classes=classes, y=y_train)
    class_weights = {int(c): float(w) for c, w in zip(classes, weights)}

    # ---- Model (matches paper architecture) ----
    model = tf.keras.Sequential([
        tf.keras.layers.Input(shape=(n_features,)),
        tf.keras.layers.Dense(20, activation="relu"),
        tf.keras.layers.Dense(20, activation="relu"),
        tf.keras.layers.Dense(20, activation="relu"),
        tf.keras.layers.Dense(20, activation="relu"),
        tf.keras.layers.Dense(20, activation="relu"),
        tf.keras.layers.Dense(1, activation="sigmoid"),
    ])

    model.compile(
        optimizer="adam",
        loss="binary_crossentropy",
        metrics=[tf.keras.metrics.BinaryAccuracy(name="acc")]
    )

    # Optional but recommended: early stopping (prevents overfit on small data)
    early = tf.keras.callbacks.EarlyStopping(
        monitor="val_loss", patience=5, restore_best_weights=True
    )

    history = model.fit(
        X_train, y_train,
        batch_size=32,
        epochs=24,                  # paper setting
        validation_split=0.2,
        class_weight=class_weights,
        callbacks=[early],
        verbose=1
    )

    # ---- Predictions ----
    y_score = model.predict(X_test, verbose=0).ravel()     # probabilities
    y_pred = (y_score >= 0.5).astype(int)                  # hard labels

    # ---- Confusion matrix and derived rates ----
    cm = confusion_matrix(y_test, y_pred)
    tn, fp, fn, tp = cm.ravel()

    tpr = tp / (tp + fn) if (tp + fn) else 0.0
    fpr = fp / (fp + tn) if (fp + tn) else 0.0

    # ---- PRC AUC (needs probabilities) ----
    prec_curve, rec_curve, _ = precision_recall_curve(y_test, y_score)
    prc_auc = auc(rec_curve, prec_curve)

    # ---- Metrics ----
    print("\n-------------------------------------------------------------")
    print("Confusion matrix [[TN FP],[FN TP]]:\n", cm)
    print("Accuracy:", accuracy_score(y_test, y_pred))
    print("TPR (Recall):", tpr)
    print("FPR:", fpr)
    print("Precision:", precision_score(y_test, y_pred, zero_division=0))
    print("Recall:", recall_score(y_test, y_pred, zero_division=0))
    print("F1:", f1_score(y_test, y_pred, zero_division=0))
    print("MCC:", matthews_corrcoef(y_test, y_pred))
    print("ROC AUC:", roc_auc_score(y_test, y_score))
    print("PRC AUC:", prc_auc)
    print("LogLoss:", log_loss(y_test, y_score))
    print("-------------------------------------------------------------\n")

if __name__ == "__main__":
    main()
