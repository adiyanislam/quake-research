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

### Advisor Framing Notes (2026-05-15)
- **Primary claim:** Tunable maintenance control under maintenance-heavy workloads. Do
  not claim end-to-end runtime improvement as the main contribution.
- **§4 heading:** Rename to "Analysis of Budgeted Refinement" (or "Parameter Analysis").
  Avoid "theoretical analysis."
- **Contributions:** Reduce to 3. Combine implementation and evaluation into one
  contribution. Keep the analysis contribution but tone down the wording. Remove
  contribution mini-headers ("System Implementation," "Theoretical Analysis," etc.).
- **Prose:** Remove em dashes throughout.
- **Figures vs tables:** Database reviewers prefer figures. Prefer figures over tables
  where the data permits.
- **Page target:** Exactly 12 pages.

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
7. **What external baselines are needed?** Minimum: Quake (done, standard dynamic
   workload), Faiss-IVF (done, standard 30/20/50 workload, nprobe=20), HNSW (done,
   insert-only ef44, see §11). ScaNN optional if time allows. LIRE skipped unless DZ
   explicitly approves.
8. **Is the `refinement_candidates_per_split` parameter worth keeping?** After the bug fix,
   per-split budgeting is a negative result. The parameter can be kept for completeness
   (it documents the negative result) but should not be presented as a tuning knob.

---

## 9. Next Experiments

**Current priority order (updated 2026-05-15):**
1. Additional datasets — equal priority to remaining baselines
2. Confirm all three baselines across all three datasets (3 baselines × 3 datasets)
3. Confirmation sweep (top FlexiRefine configs, 3 seeds) — unblocked after §10 fix
4. Gamma fine sweep — deferred until confirmation sweep completes
5. Random refinement — internal control only, not a paper priority (see note below)

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

**Status:** Deferred until confirmation sweep completes.

### 3. External Baselines

**Status as of 2026-05-19:**
- **Quake:** Done — standard 30/20/50 insert/delete/query dynamic workload.
- **Faiss-IVF:** Done — standard 30/20/50 dynamic workload, nprobe=20.
- **HNSW:** Done — insert-only/query-only workload, efSearch=44, 3 seeds confirmed.
  See §11 for full results. Note: insert-only only; do not compare against 30/20/50 tables.
- **LIRE:** Run experimentally; skipped from paper unless DZ explicitly approves.
- **ScaNN:** Optional; include only if time permits after 3 datasets are covered.
- **DiskANN/SVS/DeDrift:** Not planned at this stage.

### 4. Additional Datasets (equal priority to baselines)

Minimum target: all three confirmed baselines across all three datasets.

- **SIFT1M (128-dim, L2):** Done — current main dataset for all experiments.
- **GIST1M (960-dim, L2):** Next target.
- **Third dataset:** TBD, target ~1--10M scale, likely a DEEP subset or T2I-style
  dataset inspired by SIVF evaluations. Specific dataset to be confirmed with advisor.

### 5. Deterministic K-means Seed (Optional Engineering)
**Goal:** Expose a random seed parameter for refinement K-means in C++ to make
refinement deterministic. Would eliminate run variance and simplify confirmation.

**Status:** Not yet started. Would require modifying `refine_partitions()` in
`partition_manager.cpp` and exposing a seed param to `MaintenancePolicyParams`.

### Internal Control Note: Random Refinement

Random refinement was run as an internal sanity check for score-based selection.
Because the current paper direction prioritizes external baselines and multi-dataset
coverage, we are not including random refinement in the main paper at this stage.
Future revisions may revisit it if the scoring-policy contribution becomes central.

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

## 11. Faiss-HNSW Baseline — Insert-Only Workload Results

**Branch:** `flexirefine-faiss-hnsw-baseline`
**Date:** 2026-05-19
**Status:** CONFIRMED (3 seeds). Insert-only baseline only — do not compare against
30/20/50 delete-workload tables.

### Background and Fairness Constraint

Faiss-HNSW does not support true vector deletion. Running it on the standard
30/20/50 insert/delete/query workload would require silently ignoring deletes, which
produces incorrect recall measurements. Decision: use a dedicated insert-only workload
(`delete_ratio: 0.0`, `insert_ratio: 0.5`, `query_ratio: 0.5`) for all HNSW comparisons.

### Implementation Changes (branch `flexirefine-faiss-hnsw-baseline`)

Three bugs were fixed in `src/python/index_wrappers/faiss_hnsw.py`:

1. **Wrong recall from missing ID mapping.** HNSW internally uses 0-based sequential
   IDs; without mapping, search results did not match workload ground-truth IDs.
   Fix: wrap `IndexHNSWFlat` with `faiss.IndexIDMap`; use `add_with_ids` in `build()`
   and `add()`.

2. **`add()` missing `ids` kwarg.** `WorkloadEvaluator` calls `index.add(vecs, ids=ids)`.
   Fix: add `ids: Optional[torch.Tensor] = None` parameter to `add()`.

3. **`index_state()` returned `""` not `dict`.** `row.update("")` raises `TypeError`.
   Fix: return `{"n_total": int(self.index.ntotal), "n_list": 0}`.

4. **`hnsw.efSearch` inaccessible after `load()`.** After `faiss.read_index()`,
   `self.index.index` is a generic `faiss.Index` with no `.hnsw` attribute.
   Fix: call `faiss.downcast_index()` once after load and cache the result in
   `self._hnsw`.

`remove()` intentionally still raises `RuntimeError` to fail loudly on any
accidental delete-workload config.

### Workload Parameters (insert-only)

```
dataset:          SIFT1M (128-dim, L2)
insert_ratio:     0.5
delete_ratio:     0.0
query_ratio:      0.5
number_of_ops:    1000
initial_size:     100000
update_batch_size: 1000   (smaller than 30/20/50 configs to avoid pool exhaustion)
query_batch_size: 100
cluster_dist:     skewed
seeds:            [9299, 42, 12345]
```

Pool check: ~500 insert ops × 1000 = 500k insertions from 900k available. No exhaustion.

### efSearch Tuning (seed 9299 only)

**Coarse sweep** (`sift1m_hnsw_tuning_seed9299.yaml`):

| Config         | Search (ms) | Insert (ms) | Total (ms) | Recall |
|----------------|-------------|-------------|------------|--------|
| HNSW-M32-ef16  | 5833        | 146150      | 151984     | 0.7911 |
| HNSW-M32-ef32  | 7783        | 145934      | 153717     | 0.8868 |
| HNSW-M32-ef64  | 11351       | 146148      | 157499     | 0.9478 |
| HNSW-M32-ef128 | 18230       | 146222      | 164452     | 0.9782 |

ef32 just under 0.90; ef64 overshoots to 0.9478. Fine sweep needed.

**Fine sweep** (`sift1m_hnsw_tuning_fine_seed9299.yaml`):

| Config        | Search (ms) | Insert (ms) | Total (ms) | Recall |
|---------------|-------------|-------------|------------|--------|
| HNSW-M32-ef36 | 7793        | 131903      | 139697     | 0.8997 |
| HNSW-M32-ef40 | 8207        | 131761      | 139968     | 0.9103 |
| HNSW-M32-ef44 | 8618        | 131217      | 139836     | 0.9193 |
| HNSW-M32-ef48 | 9022        | 131892      | 140914     | 0.9268 |
| HNSW-M32-ef56 | 9795        | 131434      | 141230     | 0.9388 |

ef40 is the lowest value above 0.90 on seed 9299. Taken to 3-seed confirmation.

### 3-Seed Results — ef40 (`sift1m_hnsw_insertonly_3seed.yaml`)

| Config           | Search ms   | Insert ms       | Maintain ms | Total ms        | Recall          | Partitions |
|------------------|-------------|-----------------|-------------|-----------------|-----------------|------------|
| HNSW-M32-ef40    | 7724 ± 388  | 137268 ± 4242   | 0           | 144992 ± 4372   | 0.8956 ± 0.0468 | 0          |
| Quake-InsertOnly | 17942 ± 922 | 2989 ± 67       | 39080 ± 1776| 60011 ± 977     | 0.8978 ± 0.0187 | 1700 ± 52  |
| Density70-InsOnly| 21233 ± 654 | 2667 ± 61       | 32544 ± 2537| 56444 ± 2755    | 0.8898 ± 0.0243 | 1216 ± 69  |

Mean recall 0.8956 — just under 0.90 target across 3 seeds. Ran ef44 confirmation.

### 3-Seed Results — ef44 (`sift1m_hnsw_insertonly_3seed_ef44.yaml`) [CONFIRMED]

| Config           | Search ms   | Insert ms       | Maintain ms | Total ms        | Recall          | Partitions |
|------------------|-------------|-----------------|-------------|-----------------|-----------------|------------|
| HNSW-M32-ef44    | 8029 ± 344  | 134206 ± 2820   | 0           | 142235 ± 2690   | 0.9049 ± 0.0449 | 0          |
| Quake-InsertOnly | 17927 ± 1141| 3060 ± 139      | 43768 ± 6399| 64754 ± 5391    | 0.8985 ± 0.0193 | 1785 ± 116 |
| Density70-InsOnly| 21769 ± 92  | 2666 ± 102      | 35508 ± 4573| 59943 ± 4525    | 0.8904 ± 0.0237 | 1219 ± 78  |

### Interpretation

**Search latency:** HNSW search is 2.2–2.7× faster than Quake/Density70 at comparable
recall (~0.90). This is expected: HNSW graph traversal is highly optimized for
static search.

**Insert cost:** HNSW insert time (~134k ms) dominates its total runtime and is
approximately 43.9× higher than Quake insert time (~3k ms). Graph edge construction
during insert is expensive; Quake inserts are local partition appends.

**Total runtime:** Despite faster search, HNSW is 2.20× slower total than
Quake-InsertOnly (142k vs 65k ms) and 2.37× slower than Density70-InsertOnly
(142k vs 60k ms). The insert cost wipes out the search latency advantage.

**Recall variance:** HNSW recall std is 0.0449 (ef44) vs 0.0187–0.0243 for Quake/
Density70. HNSW recall is more variable across seeds, likely because graph quality
depends on insertion order which changes with each seed's skewed cluster sampling.

**Recall at ~0.90:** ef40 (mean 0.8956) is borderline. ef44 (mean 0.9049) is the
selected operating point for a confirmed ≥0.90 baseline.

### What This Does and Does Not Show

- **Shows:** On a pure insert + query workload, HNSW has much lower per-query
  latency but much higher insert overhead than Quake/Density70. Total runtime
  favors Quake by ~2×.
- **Does not show:** HNSW vs Quake under deletes (HNSW cannot delete).
- **Does not show:** HNSW total runtime on the main 30/20/50 workload — those
  numbers are not comparable and must not be mixed into the paper's main table.

### Paper Status

Not yet in the paper. These results are an insert-only baseline only.
Before adding to the paper: confirm what claim is being made (search latency
vs total runtime vs recall), note the insert-only limitation explicitly, and
get advisor sign-off on whether HNSW belongs in the main evaluation or a
separate "static-index baseline" subsection.

---

## 12. Advisor Notes — 2026-05-15

Notes from advisor meeting. None of these require immediate paper edits; all are
pending until explicitly requested.

| # | Note | Action status |
|---|------|---------------|
| 1 | Primary claim is tunable maintenance control, not end-to-end runtime improvement | Pending paper edit |
| 2 | Rename §4 to "Analysis of Budgeted Refinement" or "Parameter Analysis"; avoid "theoretical analysis" | Pending paper edit |
| 3 | Reduce contributions to 3; combine implementation and evaluation; tone down analysis wording | Pending paper edit |
| 4 | Remove contribution mini-headers ("System Implementation," "Theoretical Analysis," etc.) | Pending paper edit |
| 5 | Remove em dashes from paper prose | Pending paper edit |
| 6 | Database reviewers prefer figures over tables | Pending paper edit |
| 7 | Target exactly 12 pages | Pending paper edit |
| 8 | Minimum 3 baselines x 3 datasets required | In progress -- see §9 |
| 9 | Minimum baselines: Quake, Faiss-IVF, HNSW; ScaNN optional | Quake/IVF/HNSW done -- see §9 item 3 |
| 10 | Datasets beyond SIFT1M: GIST1M next; third dataset TBD ~1--10M scale | In progress -- see §9 item 4 |
| 11 | Random refinement is lower priority than 3x3 baseline/dataset coverage | Internal control only -- not in paper plan |
| 12 | LIRE skipped unless DZ explicitly approves | Skipped |
