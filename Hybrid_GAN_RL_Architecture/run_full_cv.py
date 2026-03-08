"""
run_full_cv.py
--------------
Orchestrator: runs the full Hybrid GAN-RL pipeline for all 5 CV folds.

Steps per fold:
  1. GAN augmentation (gan_augmentation_cv.py --fold N)
  2. RL training + evaluation (train_rl_cv.py --fold N)

Then aggregates all fold results and prints/saves a summary table.

Usage:
    python run_full_cv.py
"""

import subprocess
import sys
import os
import json
import numpy as np

N_FOLDS      = 5
RESULTS_DIR  = "cv_results"
SUMMARY_PATH = os.path.join(RESULTS_DIR, "cv_summary.json")


def run_step(script: str, fold: int):
    """Run a python script with --fold argument and stream output."""
    cmd = [sys.executable, script, "--fold", str(fold)]
    print(f"\n{'='*60}")
    print(f"Running: {' '.join(cmd)}")
    print('='*60)
    result = subprocess.run(cmd, check=True)
    return result.returncode


def load_fold_result(fold: int):
    path = os.path.join(RESULTS_DIR, f"fold_{fold}_results.json")
    with open(path) as f:
        return json.load(f)


def print_summary(all_results):
    print("\n" + "="*70)
    print("5-FOLD CROSS-VALIDATION SUMMARY")
    print("="*70)
    header = f"{'Fold':<6} {'Accuracy':>10} {'TPR':>10} {'FPR':>10} {'F1':>10} {'TN':>5} {'FP':>5} {'FN':>5} {'TP':>5}"
    print(header)
    print("-"*70)

    metrics = {k: [] for k in ["accuracy", "tpr", "fpr", "f1"]}
    for r in all_results:
        print(f"{r['fold']:<6} {r['accuracy']:>10.4f} {r['tpr']:>10.4f} {r['fpr']:>10.4f} {r['f1']:>10.4f} "
              f"{r['tn']:>5} {r['fp']:>5} {r['fn']:>5} {r['tp']:>5}")
        for k in metrics:
            metrics[k].append(r[k])

    print("-"*70)
    means = {k: np.mean(v) for k, v in metrics.items()}
    stds  = {k: np.std(v)  for k, v in metrics.items()}
    print(f"{'Mean':<6} {means['accuracy']:>10.4f} {means['tpr']:>10.4f} {means['fpr']:>10.4f} {means['f1']:>10.4f}")
    print(f"{'Std':<6} {stds['accuracy']:>10.4f}  {stds['tpr']:>10.4f}  {stds['fpr']:>10.4f}  {stds['f1']:>10.4f}")
    print("="*70)

    summary = {
        "per_fold": all_results,
        "mean":     {k: float(v) for k, v in means.items()},
        "std":      {k: float(v) for k, v in stds.items()},
    }
    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(SUMMARY_PATH, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nSummary saved → {SUMMARY_PATH}")
    return summary


def main():
    print("Starting 5-Fold Cross-Validation Pipeline")
    print(f"Folds: {N_FOLDS} | Scripts: gan_augmentation_cv.py, train_rl_cv.py")

    for fold in range(1, N_FOLDS + 1):
        # Step 1: GAN — skip if already done
        aug_path = os.path.join("cv_augmented", f"fold_{fold}_train_augmented.csv")
        if os.path.exists(aug_path):
            print(f"\n[Fold {fold}] GAN augmented file already exists — skipping GAN step.")
        else:
            run_step("gan_augmentation_cv.py", fold)
        # Step 2: RL
        run_step("train_rl_cv.py", fold)

    # Aggregate
    all_results = [load_fold_result(f) for f in range(1, N_FOLDS + 1)]
    print_summary(all_results)


if __name__ == "__main__":
    main()
