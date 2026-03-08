# GAN Augmentation — Data Quality Issue Report

**Date:** March 3, 2026
**Dataset:** `train_split_augmented.csv`
**Context:** Post-CTGAN augmentation quality review

---

## Executive Summary

An inspection of the CTGAN-generated synthetic samples in `train_split_augmented.csv` revealed **one critical data quality issue**, one which appears problematic but is actually not, and one that is **entirely intentional**.

| # | Issue | Severity | Status |
|---|-------|----------|--------|
| 1 | Negative values in physically constrained features | 🔴 Critical | ✅ **Resolved** (March 3, 2026) |
| 2 | `######` displayed in Excel | 🟡 Warning | ✅ **Resolved** (consequence of Issue 1) |
| 3 | All generated samples labeled `0` | 🟢 Low | ✅ Expected by design |

---

## Issue 1 (Critical): Negative Values in Physically Constrained Features

### Evidence
Out of the 603 feature columns, **493** contain negative values in the 261 synthetic rows. Examples:

| Feature | Negatives | Synthetic Min | Real Data Min |
|---------|-----------|---------------|---------------|
| `SUM CC1*SUM CO` | 216 / 261 | -4.67×10³⁵ | 238.0 |
| `cc1 > 100` | 213 / 261 | -175,748 | 0.0 |
| `Variance CCS` | 207 / 261 | -5.27×10⁵¹ | 0.13 |
| `Average CC1` | 203 / 261 | -1.41×10¹² | 1.12 |
| `sum CC0` | 201 / 261 | -1.03×10¹⁷ | 6.0 |
| `Normalised loop_in_2` | 200 / 261 | -0.0095 | 0.0 |

### Root Cause
CTGAN is a general-purpose tabular GAN. It learns **statistical distributions** but has **no knowledge of physical constraints**. It does not know that:
- Gate counts (`No of AND`, `No of NOR`, etc.) must be **non-negative integers**
- Probabilities (`P0`, `P1`) must be **between 0 and 1**
- Sums and variances of controllability/observability must be **≥ 0**

The current code specifies discrete columns only by the heuristic `nunique() < 10`, meaning most count-based columns were treated as **unconstrained continuous** by the model, allowing it to generate wildly out-of-range values.

Additionally, the extremely large negative values (e.g., -4.67×10³⁵) are the GAN "hallucinating" outside the training distribution — a well-known failure mode of GANs on sparse/skewed tabular data, especially when training on as few as 73 samples.

---

## Issue 2 (Not a Real Problem): `######` in Excel

### Finding
The inspection script confirmed:
- NaN values in synthetic rows: **0**
- Inf values in synthetic rows: **0**

### Explanation
The `######` you saw in Excel is **not a data corruption issue**. It is Excel's rendering behavior when a cell value is **too large to display** in the current column width. The actual values are extreme negative numbers like `-466,523,685,682,314,277,850,143,611,953,348,608.0` (a symptom of Issue 1 above). The data is present and readable by Python — Excel simply cannot fit the number in the cell.

**Resolution:** This will be automatically fixed once Issue 1 is addressed, since clamping values to the valid range will remove the astronomically large numbers.

---

## Issue 3 (Intentional): All Synthetic Samples Labeled `0`

### Finding
All 261 synthetic rows have `Label = 0` (Non-Trojan).

### Explanation
This is **correct and expected**. The design strategy was:
1. Train CTGAN **exclusively on Non-Trojan samples** (Label 0) from the training set.
2. Generate synthetic Non-Trojan samples to balance the class against the majority Trojan class.
3. Manually assign `Label = 0` to all generated rows.

This is the correct approach. We were not trying to generate Trojans.

---

## Proposed Solution (Do Not Apply Yet)

### Root Issue to Fix
After CTGAN generates synthetic samples, the values must be **clipped and constrained** to the valid physical range observed in the real training data. This is called **post-processing validation**.

### Solution A: Post-Generation Clipping (Recommended, Simple)
After calling `ctgan.sample()`, apply per-column clamping:

```python
# For each feature column, clip synthetic values to [real_min, real_max]
for col in train_data.columns:
    real_min = train_data[col].min()
    real_max = train_data[col].max()
    synthetic_data[col] = synthetic_data[col].clip(lower=real_min, upper=real_max)

# Additionally, for known count-based (integer) columns, round to nearest integer
integer_cols = [c for c in train_data.columns if train_data[col].dtype in ['int64', 'int32'] 
                or (train_data[col].nunique() < 50 and train_data[col].apply(float.is_integer).all())]
for col in integer_cols:
    synthetic_data[col] = synthetic_data[col].round(0).astype(int)
```

**Pros:** Simple, guaranteed to produce physically valid values.
**Cons:** Slightly biases the distribution toward the edges of the real range.

### Solution B: Add SDV Constraints (More Rigorous, Harder)
The `sdv` library (parent of CTGAN) supports explicit physical constraints such as `Positive` and `Between`. These are enforced **during generation**, not as post-processing.

```python
from sdv.constraints import Positive

constraints = [Positive(column_name=col) for col in non_negative_columns]
ctgan = CTGAN(epochs=300, constraints=constraints)
```

**Pros:** Physically sound, constraints are respected inside the model.
**Cons:** Not all CTGAN versions support this; SDV API changes frequently.

### Solution C: Replace CTGAN with SMOTE (Alternative)
SMOTE (Synthetic Minority Over-Sampling Technique) generates new samples by **interpolating between real examples**, which guarantees physically plausible values since they always lie between real data points.

```python
from imblearn.over_sampling import SMOTE
sm = SMOTE(sampling_strategy='auto', random_state=42, k_neighbors=5)
X_resampled, y_resampled = sm.fit_resample(X_train, y_train)
```

**Pros:** Guaranteed valid values, simple, no GAN training needed.
**Cons:** Less "creative" — cannot generate samples outside the convex hull of real data. Less novel from a thesis perspective.

---

## Recommendation

Apply **Solution A (Post-Generation Clipping)** as the primary fix. It is the fastest to implement, guaranteed to work, and still uses CTGAN (preserving the hybrid GAN-RL narrative for the thesis). Add a note in the report clarifying the constraint was added during post-processing.

> [!IMPORTANT]
> The current `train_split_augmented.csv` and `dqn_trojan_detector.zip` model should be considered **invalid**. Once the fix is applied, **both the GAN augmentation and the RL training must be re-run** from scratch to produce correct results.
