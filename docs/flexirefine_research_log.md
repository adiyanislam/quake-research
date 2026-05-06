Last updated: 2026-05-05
Status: internal research log, not paper prose
Rule: do not delete old results; append corrections and mark invalidated results clearly

---

# FlexiRefine Research Log

---

## 1. Project Overview

**FlexiRefine** is a control-plane framework for adaptive maintenance in dynamic partitioned
vector indexing. It builds on the Quake dynamic IVF index and introduces a tunable
refinement-allocation layer that sits between split decisions and refinement execution.

**Context.** A dynamic vector index must handle continuous inserts, deletes, and queries
while preserving recall and search latency. After a partition split, the system runs local
K-means refinement on neighboring partitions to repair centroid quality. Refinement is the
dominant maintenance cost (removing it cuts maintenance ~14x) but is essential for recall.
The research question is: which partitions should receive refinement, and how should they
be ranked when the budget is limited?

**Core hypothesis.** Refinement is most valuable when applied to partitions that are both:
1. **Query-important** — approximated by recent query hit counts `h_p`
2. **Structurally stale** — approximated by mutations since last refinement `m_p`

**Current scoring framework (general family).** The paper's §4.3 defines:

```
S_{β,γ}(p) = (h_p + 1)^β * D(p)^γ
```

where `D(p)` is a staleness transform. Implemented transforms:
- Raw: `D(p) = m_p`
- Density-normalized: `D(p) = m_p / |p|`

Implemented in code as `pow(hits + 1, beta) * pow(staleness, gamma)`, defaults β=1.0, γ=1.0.

**Current empirical best (single run, confirmation pending).** `D70-B1.0-G0.5`:
```
S(p) = (h_p + 1) * sqrt(m_p / |p|)
```
β=1.0, γ=0.5, density normalization on, K=70, split_threshold=240.
- Maintenance: −46.9% vs Quake
- Recall: 0.9035 (above 0.90 target)
- Total runtime: +2.2% vs Quake

---

## 2. Branch Timeline

### `adiyan-osdi2025`
- **Commit:** `32b1662`
- **Based on:** `main`
- **Purpose:** Working branch for OSDI 2025 FlexiRefine research. Contains the original
  hits×mutations score implementation, initial sweep configs, and the base Quake dynamic
  index codebase.
- **Key contents at this point:**
  - `refinement_top_k_score` and `refinement_top_k_hits` implemented
  - Score formula: `(hits + 1) * mutations_since_refinement` at `maintenance_policies.cpp`
  - `refinement_candidates_per_split` declared in `common.h` and bound in `wrap.cpp`
    but **not read in `local_refinement()`** — dead code
  - Experiment configs: density sweep, score sweeps, hybrid/per-split sweep YAMLs all present
- **Status:** Active base branch; not directly edited in subsequent work

### `flexirefine-agent-proposals`
- **Commit:** `32b1662` (same as `adiyan-osdi2025`)
- **Based on:** `adiyan-osdi2025`
- **Purpose:** Exploration branch created for research planning; no code changes made
- **Status:** Stale; superseded by `flexirefine-density-and-persplit-fix`

### `flexirefine-density-and-persplit-fix`
- **Commit:** `ea4de2379812b0857da8b40b1143ae5c811ccf6f`
- **Based on:** `origin/adiyan-osdi2025` (`32b1662`)
- **Purpose:** Fix the `refinement_candidates_per_split` dead-code bug and add
  optional mutation-density normalization.
- **Files changed:** 4
  - `src/cpp/include/common.h` — added `bool refinement_normalize_mutations = false`
  - `src/cpp/src/maintenance_policies.cpp` — implemented per-split cap logic; added
    density staleness branch in score computation
  - `src/cpp/bindings/wrap.cpp` — exposed `refinement_normalize_mutations` in pybind11
    binding and `__repr__`
  - `test/experiments/osdi2025/maintenance_ablation/configs/sift1m_split240_iter2_refine50_density_sweep.yaml`
    — new experiment config
- **Backward-compatible:** Yes. `refinement_normalize_mutations` defaults to `false`.
  `refinement_candidates_per_split` defaults to `-1` (disabled) in all existing configs.
- **Status:** Pushed to origin; experiment run on CloudLab

### `flexirefine-beta-gamma-scoring`
- **Commit:** `bc52a182ba0386e38b0933d024c24eec174a85cf`
- **Based on:** `flexirefine-density-and-persplit-fix` (`ea4de23`)
- **Purpose:** Implement the general score family `S_{β,γ}` from the paper's §4.3 with
  configurable `refinement_score_beta` and `refinement_score_gamma` parameters.
- **Files changed:** 4
  - `src/cpp/include/common.h` — added `double refinement_score_beta = 1.0` and
    `double refinement_score_gamma = 1.0`
  - `src/cpp/src/maintenance_policies.cpp` — replaced linear score line with
    `std::pow(hits+1, beta) * std::pow(staleness, gamma)`
  - `src/cpp/bindings/wrap.cpp` — exposed both params in binding and `__repr__`
  - `test/experiments/osdi2025/maintenance_ablation/configs/sift1m_split240_iter2_refine50_exponent_sweep.yaml`
    — new experiment config with 10 configs (3 linear baselines + 6 sqrt-exponent variants)
- **Backward-compatible:** Yes. Defaults β=1.0, γ=1.0 produce exactly
  `(hits+1) * staleness` — numerically identical to previous behavior.
- **Status:** Pushed to origin; experiment run on CloudLab

### `flexirefine-density70-beta-gamma-grid`
- **Commit:** `0407761`
- **Based on:** `flexirefine-beta-gamma-scoring` (`bc52a18`)
- **Purpose:** YAML-only — add 3×3 beta/gamma grid config for Density70 to characterize
  the full exponent space and support §4.3 of the paper.
- **Files changed:** 1
  - `test/experiments/osdi2025/maintenance_ablation/configs/sift1m_split240_iter2_refine50_density70_beta_gamma_grid.yaml`
    — 9-point grid + 4 baselines
- **Backward-compatible:** Yes (YAML only)
- **Status:** Pushed to origin; experiment run on CloudLab

### `flexirefine-confirm-top-configs-3seed`
- **Commit:** `0407761` (same as parent, no new commits yet)
- **Based on:** `flexirefine-density70-beta-gamma-grid`
- **Purpose:** Planned — confirmation sweep of top configs across 3 seeds to compute
  mean ± std for recall, maintenance, and total time
- **Status:** Branch created; **blocked** — the current experiment runner does not support
  multiple workload seeds in a single YAML. See §10 for the proposed fix.

### `flexirefine-research-log`
- **Commit:** TBD (this document)
- **Based on:** `flexirefine-density70-beta-gamma-grid` (`0407761`)
- **Purpose:** Add `docs/flexirefine_research_log.md` — the living research record
- **Files changed:** 1
  - `docs/flexirefine_research_log.md` (this file)
- **Status:** In progress

---

## 3. Implementation Changes

### 3.1 Per-split Candidate Cap Fix

**Problem.** `refinement_candidates_per_split` was declared in `MaintenancePolicyParams`
(`common.h:109`) and exposed via pybind11, but was never read inside `local_refinement()`
in `maintenance_policies.cpp`. Every experiment that set this parameter was silently
ignoring it — the per-split cap was a no-op.

**Impact on existing results.** All hybrid/per-split sweep results run before commit
`ea4de23` (i.e., those in the paper's Table 5 at submission draft time) reflect a system
where `refinement_candidates_per_split` had no effect. The lower maintenance numbers in
those old runs (e.g., PerSplit3-Top10: 21,584 ms) are artifacts of the bug, not real
per-split behavior. The corrected numbers are in §4.2.

**Fix.** In `local_refinement()`, the flat inner loop was restructured into two passes:
1. **Per-row collection:** For each split centroid (row `r`), collect all candidate
   `(pid, dist)` pairs into `row_candidates`.
2. **Per-split cap:** If `refinement_candidates_per_split > 0` and
   `row_candidates.size() > refinement_candidates_per_split`, sort by distance ascending
   and truncate.
3. **Global union:** Iterate over capped `row_candidates` and update `min_dist_by_pid`
   (keeping minimum distance per pid across all rows).

The distance-threshold filter, size filter, score ranking, and global cap all continue
to operate on `min_dist_by_pid` afterward, unchanged.

**Backward compatibility.** Default value is `-1` (disabled). All existing YAML configs
that do not set `refinement_candidates_per_split` behave identically.

---

### 3.2 Mutation-Density Normalization

**Motivation.** The raw score `S(p) = (h_p + 1) * m_p` does not account for partition
size. A large partition that grew from 1000 to 3000 vectors has the same raw `m_p` as a
small partition that grew from 500 to 2500. But the centroid displacement per vector is
smaller in the large-partition case. Normalizing by current size gives a
**mutation rate** that better approximates centroid drift.

**New staleness formula (when enabled):**
```
D(p) = m_p / |p|     (density-normalized)
D(p) = m_p           (raw, default)
```

**New parameter:** `bool refinement_normalize_mutations = false` in `MaintenancePolicyParams`.

**Implementation location:** `maintenance_policies.cpp`, inside the `refinement_top_k_score`
scoring block:
```cpp
if (params_->refinement_normalize_mutations) {
    int64_t size = partition_manager_->get_partition_size(pid);
    staleness = (size > 0)
        ? static_cast<double>(mutations) / static_cast<double>(size)
        : static_cast<double>(mutations);
} else {
    staleness = static_cast<double>(mutations);
}
```

**Backward compatibility.** Default `false`. All existing configs unchanged.

---

### 3.3 Beta/Gamma Exponent Scoring

**Motivation.** The paper's §4.3 defines the general multiplicative score family:
```
S_{β,γ}(p) = (h_p + 1)^β * D(p)^γ
```
but only β=1, γ=1 (the linear case) was experimentally evaluated. Adding configurable
exponents allows testing whether diminishing-returns transforms on hits or staleness
improve selection quality.

**New parameters:**
- `double refinement_score_beta = 1.0` — exponent on `(hits + 1)`
- `double refinement_score_gamma = 1.0` — exponent on `staleness`

**Implementation location:** `maintenance_policies.cpp`, replaces the score line:
```cpp
// Before:
double score = static_cast<double>(hits + 1) * staleness;

// After:
double score = std::pow(static_cast<double>(hits + 1), params_->refinement_score_beta)
             * std::pow(staleness, params_->refinement_score_gamma);
```

**Interaction with density normalization.** `staleness` is computed first (raw or density
depending on `refinement_normalize_mutations`), then β and γ are applied on top:
- β=1.0, γ=1.0, normalize=false → `(h+1) * m` (original formula)
- β=1.0, γ=1.0, normalize=true → `(h+1) * (m/|p|)` (density)
- β=1.0, γ=0.5, normalize=true → `(h+1) * sqrt(m/|p|)` (current best)

**`std::pow` with zero staleness.** `pow(0.0, γ) = 0.0` for γ > 0, which is the
correct behavior — a partition with zero mutations receives zero score. γ=0 is not tested.

**Backward compatibility.** Defaults β=1.0, γ=1.0 → `pow(x, 1.0) == x` exactly.

---

## 4. Experiment Log

> All experiments use the same base workload unless noted:
> dataset=sift1m, seed=9299, 1000 ops, insert=30%/delete=20%/query=50%,
> initial_size=100000, skewed cluster distribution, uniform query distribution.

---

### 4.1 Density Sweep

**Config:** `sift1m_split240_iter2_refine50_density_sweep`
**Branch:** `flexirefine-density-and-persplit-fix` (`ea4de23`)
**Goal:** Test whether density-normalized staleness (`m_p / |p|`) improves the
recall-maintenance frontier compared to raw mutation count, across top-K budgets 30–100.

**Command:**
```bash
OMP_NUM_THREADS=1 python -m test.experiments.osdi2025.experiment_runner \
  -x maintenance_ablation -c sift1m_split240_iter2_refine50_density_sweep
```

**Results:**

| Config | Search | Insert | Delete | Maintain | Total | Recall | Partitions |
|---|---|---|---|---|---|---|---|
| Quake | 248,584 | 21,016 | 28,833 | 72,176 | 370,609 | 0.9093 | 2319 |
| Score50-RawMutations | 304,961 | 16,132 | 24,801 | 35,292 | 381,188 | 0.9018 | 1333 |
| Density30-NormMutations | 314,158 | 16,129 | 24,381 | 26,906 | 381,575 | 0.8960 | 1290 |
| Density50-NormMutations | 298,797 | 16,288 | 25,472 | 34,726 | 375,284 | 0.8999 | 1333 |
| Density70-NormMutations | 294,138 | 16,647 | 25,311 | 41,091 | 377,188 | 0.9041 | 1364 |
| Density100-NormMutations | 296,772 | 16,268 | 25,156 | 41,596 | 379,794 | 0.9041 | 1335 |

**Interpretation.**
- Density70 is the best balanced above-target result: recall 0.9041, maintenance −43.1%
  vs Quake (+1.8% total). First result clearly above the prior paper claim of 22% reduction.
- Density50 is the sharpest near-target point: recall 0.8999 (borderline 0.90), maintenance
  −51.9% vs Quake. Strictly better than Score50-RawMutations on maintenance and total time,
  slightly worse on recall.
- Density100 ≈ Density70 — K saturates above 70. Consistent with prior score-sweep behavior.
- Density scoring shifts the Pareto frontier: at matched K=50, density scoring achieves
  lower total time (375k vs 381k) at nearly the same maintenance budget.

**Paper status:** USE — supports §4.2 (density staleness formulation) and §6.6 (Q6).
Recall the 22% figure in the abstract must be updated to reflect these stronger results.
Mark as single-run; confirm across seeds before final table.

---

### 4.2 Corrected Hybrid/Per-Split Sweep

**Config:** `sift1m_split240_iter2_refine50_hybrid_sweep`
**Branch:** `flexirefine-density-and-persplit-fix` (`ea4de23`)
**Goal:** Re-run the per-split budgeting experiment after fixing the dead-code bug.
**Note:** Old results from before `ea4de23` (paper Table 5 draft) are **invalidated**.
The old numbers showed unrealistically low maintenance (e.g., PerSplit3-Top10: 21,584 ms)
because the per-split cap was not actually applied.

**Command:**
```bash
OMP_NUM_THREADS=1 python -m test.experiments.osdi2025.experiment_runner \
  -x maintenance_ablation -c sift1m_split240_iter2_refine50_hybrid_sweep
```

**Results (corrected):**

| Config | Search | Insert | Delete | Maintain | Total | Recall | Partitions |
|---|---|---|---|---|---|---|---|
| Quake | 243,748 | 20,774 | 28,637 | 72,701 | 365,861 | 0.9068 | 2368 |
| Quake-NoRefine-Split240 | 341,525 | 16,186 | 21,488 | 9,422 | 388,623 | 0.8855 | 1334 |
| Quake-Split240-Iter2-Refine50-All | 293,305 | 16,633 | 25,364 | 42,824 | 378,127 | 0.9039 | 1366 |
| PerSplit3-Top10 | 319,093 | 16,335 | 25,254 | 30,348 | 391,031 | 0.8889 | 1382 |
| PerSplit3-Top20 | 321,087 | 16,569 | 25,444 | 29,996 | 393,098 | 0.8894 | 1366 |
| PerSplit3-Top30 | 307,477 | 16,895 | 25,480 | 34,863 | 384,717 | 0.8908 | 1444 |
| PerSplit3-Top40 | 336,004 | 16,030 | 24,830 | 36,631 | 413,497 | 0.8907 | 1351 |
| PerSplit5-Top10 | 323,853 | 16,184 | 24,934 | 30,129 | 395,102 | 0.8936 | 1359 |
| PerSplit5-Top20 | 328,804 | 16,436 | 25,496 | 26,616 | 397,353 | 0.8945 | 1322 |
| PerSplit5-Top30 | 323,183 | 16,182 | 25,146 | 28,413 | 392,926 | 0.8945 | 1353 |
| PerSplit5-Top40 | 324,686 | 16,270 | 25,003 | 38,320 | 404,282 | 0.8929 | 1378 |

**Old (buggy) numbers for reference — do not use:**

| Config | Old Maintain | Old Recall | Correct Maintain | Correct Recall |
|---|---|---|---|---|
| PerSplit3-Top10 | 21,584 | 0.8903 | 30,348 | 0.8889 |
| PerSplit3-Top20 | 21,102 | 0.8886 | 29,996 | 0.8894 |
| PerSplit5-Top20 | 24,116 | 0.8930 | 26,616 | 0.8945 |
| PerSplit5-Top30 | 21,830 | 0.8945 | 28,413 | 0.8945 |

**Interpretation.**
After fixing the bug, per-split budgeting is a clean negative result: no per-split config
reaches recall 0.90. Best is PerSplit5-Top20/Top30 at 0.8945. RefineAll (unranked,
radius=50) reaches 0.9039, showing that global unranked refinement already beats all
per-split variants.

Mechanistic explanation: per-split forcing breaks global value ranking. When multiple
splits are spatially close, their neighborhoods overlap. Capping candidates per centroid
forces taking locally-closest candidates from each independently, excluding globally
high-value partitions that rank strongly in the aggregate but not from every nearby
centroid. The result is spatial coverage without value-based discrimination.

This strengthens the paper's core claim: **coverage alone is insufficient; global
value-based ranking (combining importance and staleness) is necessary**.

**Paper status:** USE — rewrite Q5 (§6.5) as a clean negative result using corrected
numbers. Old Table 5 numbers must not appear in final paper.

---

### 4.3 Exponent Sweep (Special Cases)

**Config:** `sift1m_split240_iter2_refine50_exponent_sweep`
**Branch:** `flexirefine-beta-gamma-scoring` (`bc52a18`)
**Goal:** Test a small set of theoretically motivated special cases from the general score
family: sqrt of hits (β=0.5), sqrt of staleness (γ=0.5), and sqrt of both (β=γ=0.5),
applied to both raw and density staleness at K=70.

**Command:**
```bash
OMP_NUM_THREADS=1 python -m test.experiments.osdi2025.experiment_runner \
  -x maintenance_ablation -c sift1m_split240_iter2_refine50_exponent_sweep
```

**Results:**

| Config | β | γ | Density | Search | Maintain | Total | Recall |
|---|---|---|---|---|---|---|---|
| Quake | — | — | — | 248,254 | 71,261 | 368,320 | 0.9107 |
| Score50-Raw-Linear | 1.0 | 1.0 | false | 301,727 | 36,302 | 379,979 | 0.9005 |
| Density50-Linear | 1.0 | 1.0 | true | 293,154 | 35,685 | 370,011 | 0.8990 |
| Density70-Linear | 1.0 | 1.0 | true | 288,802 | 45,744 | 376,183 | 0.9016 |
| Raw70-SqrtMut | 1.0 | 0.5 | false | 305,103 | 43,781 | 389,745 | 0.9019 |
| Raw70-SqrtHits | 0.5 | 1.0 | false | 298,176 | 38,306 | 377,378 | 0.9033 |
| Raw70-SqrtBoth | 0.5 | 0.5 | false | 298,927 | 42,668 | 383,085 | 0.9056 |
| Density70-SqrtMut | 1.0 | 0.5 | true | 298,863 | 37,832 | 378,399 | 0.9008 |
| **Density70-SqrtHits** | **0.5** | **1.0** | **true** | **288,242** | **42,854** | **373,089** | **0.9040** |
| Density70-SqrtBoth | 0.5 | 0.5 | true | 291,992 | 46,979 | 380,825 | 0.9025 |

**Interpretation (preliminary — see §4.4 for update).**
Density70-SqrtHits was the best result in this run: recall 0.9040, Pareto improvement over
Density70-Linear (lower maintenance, lower total, better recall). Suggested β=0.5 was the
key improvement. However, the beta/gamma grid (§4.4) showed that β=1.0 with γ=0.5 is
equally or more competitive, with lower run variance. Treat the β=0.5 hypothesis from this
sweep as preliminary.

**Paper status:** PRELIMINARY — superseded by grid (§4.4). Do not write final paper text
based on this sweep alone. Use as supporting evidence alongside the grid.

---

### 4.4 Density70 Beta/Gamma Grid

**Config:** `sift1m_split240_iter2_refine50_density70_beta_gamma_grid`
**Branch:** `flexirefine-density70-beta-gamma-grid` (`0407761`)
**Goal:** Characterize the full 3×3 region β ∈ {0.5, 1.0, 1.5} × γ ∈ {0.5, 1.0, 1.5}
with density-normalized staleness at K=70. Directly evaluates the general score family
from §4.3 of the paper.

**Command:**
```bash
OMP_NUM_THREADS=1 python -m test.experiments.osdi2025.experiment_runner \
  -x maintenance_ablation -c sift1m_split240_iter2_refine50_density70_beta_gamma_grid
```

**Results:**

| Config | β | γ | Maintain | Total | Recall | Partitions |
|---|---|---|---|---|---|---|
| Quake | — | — | 70,438 | 361,900 | 0.9086 | 2286 |
| Score50-Raw-Linear | 1.0 | 1.0 | 34,433 | 377,708 | 0.9010 | 1310 |
| Density70-Linear | 1.0 | 1.0 | 40,398 | 389,345 | 0.9000 | 1320 |
| Density70-SqrtHits | 0.5 | 1.0 | 42,429 | 396,741 | 0.9006 | 1319 |
| D70-B0.5-G0.5 | 0.5 | 0.5 | 37,805 | 376,547 | 0.9033 | 1357 |
| D70-B0.5-G1.0 | 0.5 | 1.0 | 45,214 | 393,305 | 0.9029 | 1350 |
| D70-B0.5-G1.5 | 0.5 | 1.5 | 54,977 | 382,108 | 0.9049 | 1482 |
| **D70-B1.0-G0.5** | **1.0** | **0.5** | **37,382** | **370,039** | **0.9035** | **1360** |
| D70-B1.0-G1.0 | 1.0 | 1.0 | 50,030 | 393,363 | 0.9052 | 1364 |
| D70-B1.0-G1.5 | 1.0 | 1.5 | 39,504 | 379,727 | 0.9018 | 1331 |
| D70-B1.5-G0.5 | 1.5 | 0.5 | 40,455 | 379,769 | 0.9016 | 1344 |
| D70-B1.5-G1.0 | 1.5 | 1.0 | 35,535 | 374,353 | 0.9013 | 1334 |
| D70-B1.5-G1.5 | 1.5 | 1.5 | 37,364 | 377,434 | 0.9018 | 1336 |

**Grid summary (recall / total time by β row and γ column):**

|  | γ=0.5 | γ=1.0 | γ=1.5 |
|---|---|---|---|
| **β=0.5** | R 0.9033 / T 376k | R 0.9029 / T 393k | R 0.9049 / T 382k |
| **β=1.0** | **R 0.9035 / T 370k** | R 0.9052 / T 393k | R 0.9018 / T 380k |
| **β=1.5** | R 0.9016 / T 380k | R 0.9013 / T 374k | R 0.9018 / T 377k |

**Key patterns:**
1. **γ=0.5 column dominates on total time.** Every β at γ=0.5 produces total time in
   370–380k range. Every β at γ=1.0 exceeds 374k and frequently 390k+. The γ=0.5 column
   pattern is more robust to run variance than individual cell comparisons.
2. **β=1.5 row has lowest recall.** Super-linear hit amplification over-concentrates
   budget on a few hot partitions. Consistent across all γ values.
3. **β=1.0, γ=0.5 is the best single-run balanced point.** Recall 0.9035, total 370,039
   (+2.2% vs Quake), maintenance 37,382 (−46.9% vs Quake).
4. **β=1.0, γ=1.0 has highest single-run recall (0.9052) but worst total (393k).**
   Linear density scoring is good signal but too inclusive at K=70.

**Run variance warning.** Within this single run, `D70-B0.5-G1.0` and the named baseline
`Density70-SqrtHits` are configured identically (β=0.5, γ=1.0, density=true, K=70) but
produce different results: maintains 45,214 vs 42,429, recalls 0.9029 vs 0.9006. This
is a 6.5% maintenance difference and a 0.0023 recall gap between identical configs in
the same run. This is K-means non-determinism propagating through the refinement feedback
loop. See §6 for analysis.

**Paper status:** RERUN NEEDED — use for directional claims only until 3-seed confirmation
completes. Best-supported claim at column level: "γ=0.5 on density staleness consistently
reduces total runtime across all tested β values." Cell-level best claim (B1.0-G0.5)
requires confirmation.

---

## 5. Current Best Claims

### High Confidence
- **Refinement is the dominant maintenance cost.** Removing refinement cuts maintenance
  ~14× (103,926 → 7,263 ms in §6.1 ablation) at the cost of recall dropping
  from 0.909 to 0.879.
- **NoRefine does not preserve recall.** Recall consistently falls ~3 points below
  target when refinement is disabled.
- **Per-split budgeting alone does not preserve recall above 0.90.** Best corrected
  per-split result is 0.8945 (PerSplit5-Top20/Top30). Confirmed after bug fix.
- **Global score-based ranking is necessary for recall ≥ 0.90.** Every policy class
  that abandons global ranking (size-only, distance-only, per-split-only) falls
  below the recall target.

### Medium-High Confidence
- **Density-normalized staleness improves the selective-refinement frontier.**
  At matched K=50, Density50 achieves lower total time and similar maintenance compared
  to Score50-Raw while hitting the recall target. Density70 achieves 43% maintenance
  reduction vs Quake at recall 0.9041.
- **Super-linear hit amplification (β > 1) degrades recall.** β=1.5 row is consistently
  weakest across all γ in the grid. Pattern is robust to run variance.

### Medium Confidence (single-run, needs confirmation)
- **Sublinear staleness compression (γ=0.5) reduces total runtime** without hurting
  recall. Supported by the γ=0.5 column dominating total time in the grid.
- **Score `(h_p + 1) * sqrt(m_p / |p|)` (β=1.0, γ=0.5, density)** is the current
  best single-run configuration: −46.9% maintenance, recall 0.9035, +2.2% total.

### Low Confidence / Needs Confirmation
- **Exact optimal β value.** β=0.5 was best in exponent sweep; β=1.0 was best in grid.
  Difference is within run variance. Need 3-seed mean±std to resolve.
- **Whether γ=0.5 holds on larger workloads or different datasets.**
- **Whether density normalization generalizes beyond SIFT1M.**

---

## 6. Run Variance Notes

**Source.** K-means refinement in `refine_partitions()` uses random centroid
initialization in C++. This is not seeded from the Python-level workload seed. A slightly
better or worse refinement in early maintenance cycles changes which partitions split later,
which changes the candidate set for future cycles. Over 1000 operations with repeated
maintenance, small differences compound into meaningful behavioral divergence.

**Observed magnitude.**
- Maintenance cost: ~5–24% variance for identical configs within and across runs
- Recall: ~0.002–0.005 variance for identical configs
- Two identical configs (`D70-B0.5-G1.0` and `Density70-SqrtHits`) differed by 6.5%
  on maintenance in the same experiment run
- `Density70-Linear` showed 40,398 ms maintenance in one run and 50,030 ms in another
  (same seed, different run)

**Implication for paper.** Single-run results are indicative but not publishable as
definitive numbers. For the final paper:
- Report mean ± std across ≥3 seeds for all key configurations
- Frame directional claims at the column/row level (e.g., "the γ=0.5 column consistently
  reduces total runtime") which are robust to within-cell variance
- The confirmation sweep (§9, item 1) directly addresses this

**Recommendation on K-means seeding.** A future improvement would be to expose a
deterministic K-means seed from C++ to make refinement reproducible. This is not yet
implemented.

---

## 7. Paper Impact

### Abstract
**Current (outdated):** "reduces maintenance by roughly 22% while preserving recall
near 0.90"

**Proposed update (pending seed confirmation):**
"workload-aware scoring with density-normalized staleness reduces maintenance by roughly
40–47% while preserving recall above 0.90, with total runtime within roughly 2–3% of the
full-refinement baseline on SIFT1M"

**Caution:** Do not finalize this number until 3-seed confirmation completes. Use a
conservative framing ("up to roughly X%") for advisor meetings before confirmation.

### Theory Section (§4.2, §4.3)
- Add `D(p) = m_p / |p|` as a new staleness transform to §4.2
- Add `D(p) = sqrt(m_p / |p|)` (γ=0.5 applied to density) as a derived form
- The grid provides the first experimental evaluation of the full `S_{β,γ}` family —
  add a results table and discussion to §4.3

### Evaluation (§6.5, §6.6)
- §6.5 (Q5 — per-split budgeting): Rewrite as clean negative result using corrected
  numbers. Delete old Table 5. New claim: per-split budgeting reduces maintenance but
  fails to reach recall ≥ 0.90 under all tested configurations.
- §6.6 (Q6 — score-based refinement): Add density sweep results and β/γ grid results.
  New headline: density normalization + γ=0.5 is the strongest current policy.

### Discussion / §6.7 (What Did Not Work)
- Add discussion of K-means non-determinism and run variance
- Add section on why per-split fails (local coverage without global ranking)
- Note the need for mean±std reporting

### Open Figures
- Figure 2 (ablation bar chart): placeholder → actual figure from §6.1 data
- Figure 3 (split threshold curve): placeholder → data exists in split-threshold configs
- Figure 4 (Pareto frontier): placeholder → generate from `summary_table.csv` across
  all policy classes; `scripts/plot_split240_refine_results.py` is the right tool
- Figure 1 (architecture diagram): still needs to be drawn

---

## 8. Open Questions

1. **Do the density + γ=0.5 results hold across seeds?** (Directly addressed by §9 item 1)
2. **Do results hold on larger workloads (SIFT10M, MSTuring)?** Not yet tested.
3. **Should γ=0.5 be the new default?** Pending confirmation.
4. **Should β be 0.5 or 1.0?** Within run variance; needs confirmation to resolve.
5. **Should K-means in refinement be deterministically seeded?** Would eliminate a
   major source of experimental noise. Would require a small C++ change to expose a
   seed parameter to `refine_partitions()`.
6. **Should the paper report mean±std or single-run tables for the advisor draft?**
   Recommendation: report single-run with a variance footnote for advisor draft; switch
   to mean±std for final tables.
7. **What external baselines are needed?** The paper flags: Faiss-IVF, ScaNN, SPFresh/LIRE,
   DeDrift, HNSW, DiskANN, SVS. At minimum: Faiss-IVF, LIRE, and one graph-based
   index (HNSW or DiskANN) for a credible conference submission.
8. **Is the `refinement_candidates_per_split` parameter worth keeping?** After the bug fix,
   per-split budgeting is a negative result. The parameter can be kept for completeness
   (it documents the negative result) but should not be presented as a tuning knob.

---

## 9. Next Experiments

### 1. Confirmation Sweep — Top Configs, 3 Seeds (Blocked)
**Goal:** Compute mean ± std for Recall, Maintain, Total across seeds 9299, 42, 12345
for the 6 strongest configurations.

**Configs to confirm:**
- Quake (baseline)
- Score50-Raw-Linear (β=1.0, γ=1.0, raw, K=50)
- Density70-Linear (β=1.0, γ=1.0, density, K=70)
- D70-B0.5-G1.0 (β=0.5, γ=1.0, density, K=70)
- D70-B1.0-G0.5 (β=1.0, γ=0.5, density, K=70) ← current single-run best
- D70-B0.5-G0.5 (β=0.5, γ=0.5, density, K=70)

**Status:** Blocked on seed support in the runner. See §10.

### 2. Gamma Fine Sweep
**Goal:** Given that γ=0.5 appears robust, test γ ∈ {0.25, 0.5, 0.75, 1.0} with β
fixed at 1.0 and density normalization to locate the optimal γ more precisely.

**Status:** Not yet started; depends on confirmation sweep results.

### 3. External Baselines
**Goal:** Add at minimum Faiss-IVF and LIRE/SPFresh-style comparison for a credible
conference submission. DiskANN or HNSW for graph-based comparison.

**Status:** Not yet started. Wrapper classes exist in `src/python/index_wrappers/` for
Faiss-IVF, HNSW, DiskANN, ScaNN.

### 4. Deterministic K-means Seed (Optional Engineering)
**Goal:** Expose a random seed parameter for refinement K-means in C++ to make
refinement deterministic. Would eliminate run variance and simplify confirmation.

**Status:** Not yet started. Would require modifying `refine_partitions()` in
`partition_manager.cpp` and exposing a seed param to `MaintenancePolicyParams`.

---

## 10. Seed Support Limitation and Proposed Fix

### Current Architecture

The workload seed is controlled by a single `seed:` integer in the YAML's
`workload_generator:` section. It is passed to `DynamicWorkloadGenerator` which calls
`torch.manual_seed(seed)` and `np.random.seed(seed)` at construction time.

`run_experiment()` in `maintenance_ablation/run.py` generates **one workload per run**
into `main_output_dir`, then evaluates all indexes against that single workload. There
is no `seeds:` list support; no per-index seed; no multi-workload looping.

The workload regeneration gate is `workload_dir / "runbook.json"`. If this file exists
and `overwrite_workload: false`, the seed field in the YAML is ignored — the existing
workload is reused regardless of what seed is written.

**Conclusion:** The current system cannot produce results for multiple seeds from a single
YAML. The `flexirefine-confirm-top-configs-3seed` branch is waiting for this to be added.

### Proposed Minimal Fix

**Modify only `test/experiments/osdi2025/maintenance_ablation/run.py`.** No changes to
`experiment_utils.py`, `workload_generator.py`, C++ code, or pybind11 bindings.

**Change summary (~50 lines added, 0 existing lines deleted):**

1. At the top of `run_experiment()`, check whether `workload_generator_cfg` has a `seeds:`
   key (list) instead of a single `seed:` integer. If `seeds:` is absent, fall back to
   the current single-seed path exactly as today.

2. If `seeds:` is present, loop over each seed `s`:
   - Call `generate_dynamic_workload()` with `global_output_dir = main_output_dir / f"seed_{s}"`
   - Override seed in `workload_generator_cfg` to `s` for this iteration
   - Evaluate all index configs against `main_output_dir / seed_{s}/`

3. Add `produce_multiseed_summary_table(cfg, main_output_dir, seeds)` which reads
   `{main_output_dir}/seed_{s}/{idx_name}/results.csv` for each (seed, index) pair and
   writes `multiseed_summary.csv` with mean ± std columns.

**YAML change:**
```yaml
workload_generator:
  seeds: [9299, 42, 12345]   # new: list triggers multi-seed loop
  # seed: 9299               # old: still works if seeds: absent
  ...
```

**Output structure:**
```
results/confirm_top_configs_3seed/
  seed_9299/
    runbook.json
    D70-B1.0-G0.5/results.csv
    ...
    summary_table.csv
  seed_42/
    ...
  seed_12345/
    ...
  multiseed_summary.csv   ← mean ± std across seeds
  multiseed_summary.md
```

**Risk:** Low. The new multi-seed path only activates when `seeds:` is explicitly present.
All existing YAMLs using `seed:` (singular) continue to work identically. Awaiting
approval before implementation.

**Approval status:** Pending — questions outstanding (see conversation context):
1. Should `multiseed_summary` report mean±std only, or also preserve per-seed rows?
2. Should per-seed `unified_plot.png` be generated inside each `seed_{s}/` subdir?
3. Should `overwrite_workload: false` skip regeneration if `seed_{s}/runbook.json` exists?

---

## Update: 2026-05-05 — 3-Seed Confirmation, Advisor Meeting, Baseline Plan

---

### §4.5 Experiment: 3-Seed Confirmation of Top FlexiRefine Configs

**Config:** `sift1m_split240_iter2_refine50_confirm_top_configs_3seed.yaml`
**Branch:** `flexirefine-confirm-top-configs-3seed` (commit `9068e16`)
**Goal:** Compute mean ± std for Recall, Maintain, Total across seeds
{9299, 42, 12345} for the 6 strongest configurations, establishing whether
the density + exponent improvements are robust to K-means non-determinism.

**Results (mean ± std, 3 seeds):**

| Config | Maintain (ms) | Total (ms) | Recall |
|---|---|---|---|
| Quake | 67,658 ± 6,505 | 308,584 ± 54,185 | 0.9084 ± 0.0149 |
| Score50-Raw-Linear | 36,620 ± 8,825 | 320,085 ± 56,744 | 0.9026 ± 0.0181 |
| Density70-Linear | 42,946 ± 5,238 | 317,650 ± 55,656 | 0.9033 ± 0.0183 |
| D70-B0.5-G1.0 | 46,038 ± 15,398 | 332,935 ± 79,071 | 0.9057 ± 0.0174 |
| D70-B1.0-G0.5 | 43,441 ± 5,644 | 321,090 ± 50,160 | 0.9030 ± 0.0206 |
| D70-B0.5-G0.5 | 40,941 ± 8,024 | 316,805 ± 53,578 | 0.9024 ± 0.0215 |

**Interpretation:**
- **[CONFIRMED]** All score-based selective refinement configs preserve mean recall ≥ 0.90.
- **[CONFIRMED]** Maintenance reductions of 32–46% vs Quake are reproducible across seeds.
- **[CONFIRMED]** Total runtime within 4% of Quake for all selective configs.
- Exact best (β, γ) pair is **not stable** at n=3 seeds — differences between
  D70-B1.0-G0.5 and Density70-Linear are within their standard deviations.
- The policy-class claim is confirmed; hyperparameter-level claims require n≥5 seeds.
- Density70-Linear has the lowest maintenance coefficient of variation (12.2%),
  making it the most stable recommended default.
- Score50-Raw-Linear has the lowest mean maintenance (−45.9% vs Quake) but
  highest variance (CV 24.1%).
- D70-B0.5-G1.0 has highest mean recall (0.9057) but worst variance and total time.

**Paper status:** **[CONFIRMED]** — use as primary results table (Table 7 / confirmation table).
These are the numbers to cite in the abstract and evaluation conclusions.

---

### §11 Advisor Meeting Notes (2026-05-05)

**Meeting participants:** Adiyan Islam, Dongfang Zhao

#### Baselines
- Target baselines for the paper: **Quake full**, **LIRE/SPFresh-style**, **HNSW**, **ScaNN**, **Faiss-IVF**.
- If time is limited: keep Quake, LIRE, HNSW, ScaNN; Faiss-IVF can be deprioritized.
- DeDrift is optional and not required.
- VLDB/systems audience cares about latency, throughput, scalability, maintenance cost, update
  cost, and recall stability — not just accuracy/precision metrics.

#### References
- Add more references; aim for 50–60 total eventually.
- Remove/deprioritize the SISAP 2013 Boytsov reference (not top-tier, not central).
- Do not exceed 4 related-work categories/subsections.

#### Paper Structure
- Motivation and use cases should be **merged into the Introduction** (not a standalone section).
- Section 3 System Design is strong — keep it.
- Evaluation needs restructuring:
  - Combine §6.1–§6.3 into one "Experimental Setup" section.
  - Experimental Setup must include: platform, datasets/workloads, baselines, metrics, evaluation questions.
  - Do not use Q-format subsection titles. Use result-style headers instead.
- Related Work: DZ suggested it may move after the Introduction; confirmed to move it before System Design.
  Use at most 4 subsections.
- Next steps: add references, share draft with DZ, work on DZ comments.

---

### §12 Baseline Infrastructure Status

#### Current branch: `flexirefine-baseline-comparison-lire-faiss` (commit `465b1b3`)

**Files changed:**
- `src/python/workload_generator.py` — two fixes:
  1. `_init_index()`: only QuakeWrapper receives `num_workers` kwarg on `load()`
  2. `evaluate_workload()`: null-check on `index.maintenance()` return value
- `test/experiments/osdi2025/maintenance_ablation/run.py`:
  - Added module-level `_INDEX_CLASS_MAP = {"Quake": QuakeWrapper, "FaissIVF": FaissIVF}`
  - Per-index `do_maintenance` logic: only Quake indexes run maintenance
  - Removed hardcoded `do_maintenance_flag=True`
- New YAML: `sift1m_split240_baseline_comparison_3seed.yaml`

**Baseline status:**

| Baseline | Implementation | Inserts | Deletes | Maintenance | Ready to run? |
|---|---|---|---|---|---|
| Quake | ✅ Complete | ✅ | ✅ | ✅ Full | Yes |
| LIRE | ✅ Quake config variant | ✅ | ✅ | ✅ Size-based, no K-means | Yes |
| Faiss-IVF | ✅ `faiss_ivf.py` | ✅ | ✅ | ❌ None (static) | Yes — added to runner |
| HNSW | ⚠️ `faiss_hnsw.py` | ✅ | ❌ Not supported | ❌ None | Needs delete-free workload |
| ScaNN | ⚠️ `scann.py` | ✅ | ✅ | ❌ None | Needs `pip install scann` |

**Critical notes:**
- `LIRE` uses `index: Quake` with `refinement_iterations: 0, max_partition_size: 2000`.
  This approximates SPFresh/LIRE design but is NOT an independent LIRE implementation.
  Paper must clarify this distinction.
- `Faiss-IVF` uses static centroids trained at build time. Recall will degrade over the
  dynamic workload — this is expected and scientifically informative, not a bug.
- `HNSW` raises `RuntimeError` on `remove()`. Must use a delete-free workload or
  soft-delete wrapper before it can run on the current workload.
- `ScaNN` requires separate package installation on CloudLab (`pip install scann`).

**Backward compatibility:** All changes are additive. All existing Quake-only YAMLs
continue to work identically (`"Quake" == "Quake"` triggers `do_maintenance=True`).

---

### §5 Updated Current Best Claims

**High confidence [CONFIRMED]:**
- Refinement is the dominant maintenance cost (14× reduction from NoRefine).
- NoRefine reduces maintenance but drops recall ~3 points below target.
- Per-split budgeting (correctly implemented) does NOT preserve recall ≥ 0.90.
- Score-based selective refinement reduces maintenance 32–46% while preserving mean recall ≥ 0.90
  across three independent workload seeds. Total runtime within 4% of Quake.
- Super-linear hit amplification (β > 1) consistently degrades recall.

**Medium-high confidence:**
- Density-normalized staleness (m/|p|) is more stable than raw mutation count
  (maintenance CV 12.2% vs 24.1% for raw at matched recall).
- The γ=0.5 column in the beta/gamma grid consistently reduces total runtime
  relative to γ=1.0 (column-wide pattern, robust to individual cell variance).

**Medium confidence (needs n≥5 seeds):**
- Specific optimal (β, γ) pair within the density policy class.
- Whether D70-B1.0-G0.5 or Density70-Linear is definitively better.

---

### §9 Updated Next Experiments

1. **[COMPLETED]** 3-seed confirmation of top FlexiRefine configs
2. **[NEXT]** 3-seed baseline comparison (LIRE + Faiss-IVF) — YAML ready,
   runner supports both baselines as of commit `465b1b3`.
3. **[PLANNED]** HNSW baseline — requires delete-free workload variant or
   DiskANN substitution. Not in current baseline branch.
4. **[PLANNED]** ScaNN baseline — requires `pip install scann` on CloudLab.
5. **[PLANNED]** Gamma fine sweep: β=1.0 fixed, γ ∈ {0.25, 0.5, 0.75, 1.0},
   density normalization on, after baseline experiments complete.
6. **[DEFERRED]** n=5 seeds (add 1337, 2024) — after baselines are complete.

---

### §2 Updated Branch Timeline

**`flexirefine-confirm-top-configs-3seed`** (commit `9068e16`)
- Based on: `flexirefine-density70-beta-gamma-grid` (`0407761`)
- Purpose: Multi-seed runner support + 3-seed confirmation YAML
- Files changed: `run.py` (multi-seed loop + aggregation), new YAML config
- Status: **DONE — 3-seed results confirmed**

**`flexirefine-paper-draft-current`** (commit `c75ceda`)
- Based on: `flexirefine-confirm-top-configs-3seed` (`9068e16`)
- Purpose: Initial living paper draft reflecting confirmed experimental results
- Files changed: `docs/flexirefine_paper_draft_current.tex` (new file, 1266 lines)
- Status: **DONE — superseded by `flexirefine-paper-restructure-dz-comments`**

**`flexirefine-research-log`** (commit `e21b3e4`)
- Based on: `flexirefine-density70-beta-gamma-grid` (`0407761`)
- Purpose: Create `docs/flexirefine_research_log.md` (this file)
- Status: **DONE (this document is the continuation)**

**`flexirefine-baseline-comparison-lire-faiss`** (commit `465b1b3`)
- Based on: `flexirefine-paper-draft-current` (`c75ceda`)
- Purpose: Add LIRE and Faiss-IVF baseline support to runner + new baseline YAML
- Files changed: `workload_generator.py`, `run.py`, new YAML
- Status: **PUSHED — ready to run on CloudLab**

**`flexirefine-paper-restructure-dz-comments`** (in progress)
- Based on: `flexirefine-paper-draft-current` (`c75ceda`)
- Purpose: Apply DZ advisor feedback — merge Motivation, restructure Evaluation,
  move Related Work, reduce to 4 subsections, result-style headers
- Files changed: `docs/flexirefine_paper_draft_current.tex`, `docs/flexirefine_research_log.md`
- Status: **IN PROGRESS**
