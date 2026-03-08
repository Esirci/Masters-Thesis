"""
run_original_cv.py
-------------------
Orchestrator: trains the RL agent on the ORIGINAL (non-augmented) data
for all 5 folds, then prints a mean ± std summary.

Compares directly against the GAN-augmented results in cv_results/.

Usage:
    python run_original_cv.py
"""

import subprocess
import sys
import os
import json
import numpy as np

N_FOLDS      = 5
RESULTS_DIR  = "cv_results_original"
SUMMARY_PATH = os.path.join(RESULTS_DIR, "cv_summary_original.json")


def run_step(fold: int):
    cmd = [sys.executable, "train_rl_original_cv.py", "--fold", str(fold)]
    print(f"\n{'='*60}")
    print(f"Running: {' '.join(cmd)}")
    print('='*60)
    subprocess.run(cmd, check=True)


def load_result(fold: int):
    path = os.path.join(RESULTS_DIR, f"fold_{fold}_results.json")
    with open(path) as f:
        return json.load(f)


def load_augmented_result(fold: int):
    """Load corresponding GAN-augmented result for comparison."""
    path = os.path.join("cv_results", f"fold_{fold}_results.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None


def print_summary(all_results):
    print("\n" + "="*70)
    print("ORIGINAL DATA — 5-FOLD CV SUMMARY")
    print("="*70)
    header = f"{'Fold':<6} {'Accuracy':>10} {'TPR':>10} {'FPR':>10} {'F1':>10} {'TN':>5} {'FP':>5} {'FN':>5} {'TP':>5}"
    print(header)
    print("-"*70)

    metrics = {k: [] for k in ["accuracy", "tpr", "fpr", "f1"]}
    for r in all_results:
        print(f"{r['fold']:<6} {r['accuracy']:>10.4f} {r['tpr']:>10.4f} "
              f"{r['fpr']:>10.4f} {r['f1']:>10.4f} "
              f"{r['tn']:>5} {r['fp']:>5} {r['fn']:>5} {r['tp']:>5}")
        for k in metrics:
            metrics[k].append(r[k])

    print("-"*70)
    means = {k: np.mean(v) for k, v in metrics.items()}
    stds  = {k: np.std(v)  for k, v in metrics.items()}
    print(f"{'Mean':<6} {means['accuracy']:>10.4f} {means['tpr']:>10.4f} {means['fpr']:>10.4f} {means['f1']:>10.4f}")
    print(f"{'Std':<6} {stds['accuracy']:>10.4f}  {stds['tpr']:>10.4f}  {stds['fpr']:>10.4f}  {stds['f1']:>10.4f}")
    print("="*70)

    # --- Side-by-side comparison with GAN-augmented ---
    aug_results = [load_augmented_result(f) for f in range(1, N_FOLDS + 1)]
    if all(r is not None for r in aug_results):
        aug_metrics = {k: [r[k] for r in aug_results] for k in ["accuracy", "tpr", "fpr", "f1"]}
        aug_means   = {k: np.mean(v) for k, v in aug_metrics.items()}
        aug_stds    = {k: np.std(v)  for k, v in aug_metrics.items()}

        print("\n" + "="*60)
        print("COMPARISON: Original vs. GAN-Augmented (Mean ± Std)")
        print("="*60)
        print(f"{'Metric':<12} {'Original':>20} {'GAN-Augmented':>20} {'Delta':>10}")
        print("-"*60)
        for k in ["accuracy", "tpr", "fpr", "f1"]:
            orig_str = f"{means[k]:.4f} ± {stds[k]:.4f}"
            aug_str  = f"{aug_means[k]:.4f} ± {aug_stds[k]:.4f}"
            delta    = aug_means[k] - means[k]
            sign     = "+" if delta >= 0 else ""
            print(f"{k.upper():<12} {orig_str:>20} {aug_str:>20} {sign}{delta:>+9.4f}")
        print("="*60)

    summary = {
        "per_fold": all_results,
        "mean": {k: float(v) for k, v in means.items()},
        "std":  {k: float(v) for k, v in stds.items()},
    }
    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(SUMMARY_PATH, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nSummary saved → {SUMMARY_PATH}")


def main():
    print("Running RL on Original (Non-Augmented) Data — 5 Folds")
    for fold in range(1, N_FOLDS + 1):
        run_step(fold)
    all_results = [load_result(f) for f in range(1, N_FOLDS + 1)]
    print_summary(all_results)


if __name__ == "__main__":
    main()
