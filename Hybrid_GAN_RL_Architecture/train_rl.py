import pandas as pd
import numpy as np
from stable_baselines3 import DQN
from stable_baselines3.common.env_checker import check_env
from trojan_env import TrojanEnv
import os
from sklearn.preprocessing import StandardScaler

# Paths
TRAIN_PATH = "train_split_augmented.csv" # Use augmented data
TEST_PATH = "test_split.csv" # Real test data
MODEL_PATH = "dqn_trojan_detector"

DROP_COLS = ["Name of file", "Label", "base_design", "trojan_id"]

# Preprocessing from your DNN baseline (important to keep consistent)
CAP = 1e12
def preprocess_cap_log(X):
    X = X.astype(np.float64)
    X.replace([np.inf, -np.inf], np.nan, inplace=True)
    X = X.fillna(X.median(numeric_only=True))
    X = X.clip(lower=-CAP, upper=CAP)
    X = np.sign(X) * np.log1p(np.abs(X))
    return X.astype(np.float32)

def main():
    if not os.path.exists(TRAIN_PATH):
        print(f"Error: Augmented data {TRAIN_PATH} not found.")
        return

    print("Loading datasets...")
    train_df = pd.read_csv(TRAIN_PATH)
    test_df = pd.read_csv(TEST_PATH)
    
    # Preprocessing
    # Separate features and label
    # Identify non-numeric columns present in the dataset to drop
    cols_to_drop = [c for c in DROP_COLS if c in train_df.columns]
    
    X_train_raw = train_df.drop(cols_to_drop, axis=1)
    y_train = train_df["Label"]
    
    cols_to_drop_test = [c for c in DROP_COLS if c in test_df.columns]
    X_test_raw = test_df.drop(cols_to_drop_test, axis=1)
    y_test = test_df["Label"]
    
    # 1. Cap & Log transform (Same as DNN)
    print("Preprocessing: Cap & Log...")
    X_train_proc = preprocess_cap_log(X_train_raw)
    X_test_proc = preprocess_cap_log(X_test_raw)
    
    # 2. Standard Scaling (Important for Neural Networks/RL)
    print("Preprocessing: Scaling...")
    scaler = StandardScaler()
    X_train_scaled = pd.DataFrame(scaler.fit_transform(X_train_proc), columns=X_train_raw.columns)
    X_test_scaled = pd.DataFrame(scaler.transform(X_test_proc), columns=X_test_raw.columns)
    
    # Re-attach labels for the Env
    train_env_df = X_train_scaled.copy()
    train_env_df["Label"] = y_train.values
    
    test_env_df = X_test_scaled.copy()
    test_env_df["Label"] = y_test.values
    
    # Initialize Environment
    print("Initializing TrojanEnv...")
    env = TrojanEnv(train_env_df)
    
    # Sanity check
    check_env(env)
    print("Environment check passed.")
    
    # Initialize Agent
    # MlpPolicy because inputs are vector features (not images)
    print("Initializing DQN Agent...")
    model = DQN("MlpPolicy", env, verbose=1, 
                learning_rate=1e-4, 
                buffer_size=50000,
                exploration_fraction=0.2, # Explores for first 20%
                exploration_final_eps=0.02, # Low final epsilon
                batch_size=32)
    
    # Train
    print("Training Agent (this may take a moment)...")
    # Total timesteps needs to be enough to go through dataset multiple times
    # 20 epochs equivalent? 668 samples * 20 = ~13360 steps
    model.learn(total_timesteps=20000)
    
    print("Training finished. Saving model...")
    model.save(MODEL_PATH)
    
    # Evaluation
    print("\nEvaluating on Test Split...")
    
    # Manual evaluation loop
    # We use the trained model to predict on test_df
    
    predictions = []
    
    obs_array = test_env_df.drop("Label", axis=1).to_numpy().astype(np.float32)
    labels = test_env_df["Label"].to_numpy().astype(int)
    
    for i in range(len(obs_array)):
        obs = obs_array[i]
        action, _states = model.predict(obs, deterministic=True)
        predictions.append(action)
        
    predictions = np.array(predictions)
    
    # Calculate Metrics
    from sklearn.metrics import confusion_matrix, accuracy_score, precision_score, recall_score, f1_score
    
    cm = confusion_matrix(labels, predictions)
    print("Confusion Matrix [[TN FP],[FN TP]]:\n", cm)
    print(f"Accuracy: {accuracy_score(labels, predictions):.4f}")
    
    tn, fp, fn, tp = cm.ravel()
    tpr = tp / (tp + fn) if (tp + fn) else 0
    fpr = fp / (fp + tn) if (fp + tn) else 0
    
    print(f"TPR (Recall): {tpr:.4f}")
    print(f"FPR (False Positive Rate): {fpr:.4f}")
    print(f"Precision: {precision_score(labels, predictions):.4f}")
    print(f"F1 Score: {f1_score(labels, predictions):.4f}")

if __name__ == "__main__":
    main()
