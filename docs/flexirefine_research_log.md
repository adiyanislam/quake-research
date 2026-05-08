
---

## Update: 2026-05-05 — Advisor Feedback: Research-Question-Driven Evaluation Structure

### §13 Advisor Feedback: Evaluation Structure (DZ, 2026-05-05)

**Key instruction:** Do not structure evaluation as a flat list of per-baseline comparisons. Instead, organize around research questions. Each subsection should answer one question with a result-style header.

**Explicitly rejected structure:**
- Baseline Comparison: Quake
- Baseline Comparison: Faiss-IVF
- Baseline Comparison: LIRE
- Baseline Comparison: HNSW

**Approved structure (research questions → result-style subsections):**

| RQ | Question | Result-style header | Baselines/configs needed |
|---|---|---|---|
| RQ1 | Does FlexiRefine reduce maintenance while preserving recall? | Score-Based Refinement Reduces Maintenance by 38–45% While Preserving Recall | Quake vs FlexiRefine policies |
| RQ2 | Are score-based policies better than naive selective policies? | Coverage-Only and Naive Policies Fail to Preserve Recall | No-refine, top-K, per-split, split-threshold, hits-only |
| RQ3 | Is dynamic maintenance necessary under insert/delete workloads? | Static IVF Avoids Maintenance but Pays 4× Higher Total Runtime | Faiss-IVF (confirmed), LIRE (pending), HNSW/ScaNN (planned) |
| RQ4 | Are results robust across workload seeds? | Score-Based Refinement Generalizes Across Workload Seeds | 3-seed confirmation table |
| RQ5 | Which operating point should a user choose? | Selecting an Operating Point | All confirmed configs, user persona mapping |
| RQ6 | (Optional) How does FlexiRefine compare to graph/optimized baselines? | Comparison with Graph-Based and Optimized Baselines | HNSW, ScaNN (TODO) |

**User persona mapping for RQ5:**
- Recall-critical → Quake full refinement
- Maintenance-constrained → Score50-Raw-Linear (−45.9% maintenance, higher variance)
- Balanced → D70-B0.5-G0.5 (best total runtime, lowest maintenance variance)
- Simplicity/stability → Density70-Linear (lowest CV, recommended default)

**Branch implementing this:** `flexirefine-paper-evaluation-restructure`

### §14 Baseline Plan: Mapped to Research Questions

Baselines are not evaluated as standalone sections. Each baseline appears
in the RQ that it directly answers:

| Baseline | RQ | Status |
|---|---|---|
| Quake (full refinement) | RQ1, RQ4, RQ5 | ✅ All experiments done |
| FlexiRefine policy variants | RQ1, RQ2, RQ4, RQ5 | ✅ Confirmed 3-seed |
| Faiss-IVF (nprobe=20) | RQ3 | ✅ Confirmed 3-seed |
| LIRE-style (size-based, no K-means) | RQ3 | 🔄 In progress — stale-partition guard + min_partition_size fix applied; 3-seed run pending |
| HNSW (delete-free workload) | RQ3/RQ6 | ⏳ Planned |
| ScaNN | RQ3/RQ6 | ⏳ Planned (lower priority) |

**Key insight:** Faiss-IVF already confirms the answer to RQ3 (dynamic maintenance
is necessary: 4.25× total runtime penalty). LIRE will add nuance: does reassignment
without K-means refinement also fail? HNSW and ScaNN are the long-tail comparison
for the optional RQ6.

### §6 Updated Current Best Claims

**[CONFIRMED] — Policy-class claim:**
Score-based selective refinement (any configuration with joint importance×staleness scoring)
reduces maintenance by 32–46% while preserving mean recall above 0.90 across three seeds,
with total runtime within 4% of the full-refinement baseline.

**[CONFIRMED] — Negative-results claim:**
All naive policies (size-only, distance-only, budget-without-ranking, per-split coverage,
hits-alone, β>1) fail to preserve the recall target while reducing maintenance. This
result is robust at n=3 seeds.

**[CONFIRMED] — Dynamic maintenance claim:**
Faiss-IVF (no maintenance) pays 4.25× higher total runtime and fails the recall target
on one of three seeds. Dynamic maintenance is necessary.

**[PENDING] — LIRE claim:**
LIRE-style maintenance (dynamic splits, no K-means) expected to fail recall target,
confirming that K-means quality repair is the essential ingredient.
