# FlexiRefine — Model Handoff Document

**Created:** 2026-05-05  
**Branch at handoff:** `flexirefine-handoff-before-opus-paper-pass`  
**Quake PDF location:** `test/experiments/osdi2025/paper/Quake-Revision.pdf` and `osdi25-mohoney.pdf`  
**Purpose:** Complete context for a new model instance continuing the FlexiRefine research project, specifically to revise the paper draft to match DZ's latest feedback and the Quake paper's prose style.

---

## 1. Project Summary

### What FlexiRefine Is

FlexiRefine is a **control-plane framework for adaptive maintenance in dynamic partitioned vector indexing**. It addresses a specific gap: existing dynamic vector index systems expose limited control over the tradeoff between maintenance cost, search quality, and total runtime. Maintenance is typically either fully on or fully off.

FlexiRefine treats **post-split partition refinement** as a tunable resource allocation problem. After a partition splits, the system must repair the local partition quality by running K-means on neighboring partitions. FlexiRefine controls *which* partitions receive this repair by ranking candidates using a joint importance–staleness score, then refining only the top-ranked subset within a configurable budget.

The core idea: refinement is most valuable when applied to partitions that are both *important to recent queries* (measured by hit counts) and *structurally stale* (measured by mutations since last refinement). The general score family is:

```
S_{β,γ}(p) = (h_p + 1)^β * D(p)^γ
```

where `h_p` = recent query hit count, `D(p)` = staleness signal (raw mutations `m_p`, or density-normalized `m_p/|p|`), and `β, γ` are exponent parameters. No single `(β, γ)` pair is claimed as universally optimal — the family is a tunable control surface.

### What Quake Is and How FlexiRefine Builds on It

Quake is an adaptive partitioned vector index (OSDI 2025, Mohoney et al.) that uses a cost-model-driven maintenance policy to decide when to split, merge, or delete partitions based on estimated scan-latency impact. After splits, it runs full local K-means refinement on all neighboring partitions.

FlexiRefine is implemented **on top of Quake** as a modification to Quake's maintenance path. It does not change Quake's split/merge/delete decision logic — it only changes which partitions receive K-means refinement after a split. All FlexiRefine experiments use the Quake backend. The Quake PDF is at `test/experiments/osdi2025/paper/Quake-Revision.pdf` and `osdi25-mohoney.pdf` — read these to understand the prose style and paper structure the new model should emulate.

### Current Paper Framing

The paper is titled **"FlexiRefine: A Control-Plane Framework for Adaptive Maintenance in Dynamic Vector Indexing."**

The framing: existing systems do not give users explicit control over the recall–maintenance–latency tradeoff. FlexiRefine exposes this as a first-class, configurable, principled control surface. The paper demonstrates that selective refinement using the joint importance–staleness signal substantially reduces maintenance cost while maintaining recall, whereas naive alternatives (size-only, distance-only, per-split coverage, budget-only) consistently fail to preserve recall.

### Current Main Claims (All Confirmed at 3 Seeds)

1. **Score-based selective refinement reduces Quake's maintenance cost by 38–45%** while preserving mean recall above 0.90, with total runtime overhead below 5%. This is the primary empirical contribution.

2. **Static Faiss-IVF (no maintenance) pays over 4× higher total runtime** than Quake and exhibits high recall variance under dynamic insert/delete workloads, falling below 0.90 on one of three seeds. Dynamic maintenance is necessary.

3. **Naive selective policies fail.** Size-only, distance-only, per-split coverage, hits-only, and budget-without-ranking policies all fail to preserve the recall target while reducing maintenance. The joint importance × staleness signal is necessary.

4. **Density-normalized staleness** (`D(p) = m_p / |p|`) is more stable than raw mutation count (`D(p) = m_p`), with lowest maintenance coefficient of variation (CV = 12.2% for Density70-Linear vs 24.1% for Score50-Raw-Linear).

---

## 2. Current Strongest Confirmed Results

### FlexiRefine 3-Seed Confirmation (`sift1m_split240_iter2_refine50_confirm_top_configs_3seed`)
Seeds: {9299, 42, 12345} | [CONFIRMED]

| Config | Maintain (ms) | Total (ms) | Recall |
|---|---|---|---|
| Quake | 67,658 ± 6,505 | 308,584 ± 54,185 | 0.9084 ± 0.0149 |
| Score50-Raw-Linear | 36,620 ± 8,825 | 320,085 ± 56,744 | 0.9026 ± 0.0181 |
| Density70-Linear | 42,946 ± 5,238 | 317,650 ± 55,656 | 0.9033 ± 0.0183 |
| D70-B0.5-G1.0 | 46,038 ± 15,398 | 332,935 ± 79,071 | 0.9057 ± 0.0174 |
| D70-B1.0-G0.5 | 43,441 ± 5,644 | 321,090 ± 50,160 | 0.9030 ± 0.0206 |
| D70-B0.5-G0.5 | 40,941 ± 8,024 | 316,805 ± 53,578 | 0.9024 ± 0.0215 |

### Faiss-IVF Baseline Comparison (`sift1m_split240_baseline_comparison_faiss_3seed`)
Seeds: {9299, 42, 12345} | [CONFIRMED]

| Config | Search (ms) | Insert (ms) | Delete (ms) | Maintain (ms) | Total (ms) | Recall | Partitions |
|---|---|---|---|---|---|---|---|
| Quake | 197,731 ± 41,144 | 18,425 ± 3,668 | 22,903 ± 6,394 | 70,682 ± 15,431 | 309,741 ± 66,555 | 0.9118 ± 0.0134 | 2437 ± 282 |
| Score50-Raw-Linear | 248,131 ± 57,834 | 14,312 ± 2,042 | 20,141 ± 4,690 | 38,579 ± 7,528 | 321,162 ± 64,340 | 0.9017 ± 0.0192 | 1345 ± 16 |
| Density70-Linear | 245,172 ± 45,798 | 14,364 ± 2,229 | 20,320 ± 4,744 | 43,735 ± 11,913 | 323,591 ± 54,505 | 0.9039 ± 0.0165 | 1348 ± 34 |
| D70-B0.5-G0.5 | 239,872 ± 46,409 | 14,417 ± 2,144 | 20,096 ± 5,112 | 42,224 ± 4,609 | 316,609 ± 54,402 | 0.9064 ± 0.0184 | 1360 ± 20 |
| Faiss-IVF | 1,305,884 ± 780,820 | 9,031 ± 1,503 | 732 ± 169 | 0 ± 0 | 1,315,646 ± 782,124 | 0.9269 ± 0.0668 | 1000 ± 0 |

**Key metrics from Faiss-IVF comparison:**
- D70-B0.5-G0.5 is the best balanced FlexiRefine config: −40.3% maintenance vs Quake, recall 0.9064, +2.2% total runtime
- Score50-Raw-Linear: −45.4% maintenance, recall 0.9017 (highest reduction, higher variance CV=24.1%)
- Density70-Linear: −38.1% maintenance, recall 0.9039, lowest maintenance variance (CV=12.2%)
- Faiss-IVF total runtime: 4.25× slower than Quake; 4.16× slower than D70-B0.5-G0.5
- Faiss-IVF recall fell to 0.8553 at seed_12345 (below 0.90 target)
- Faiss-IVF is a **degradation baseline**, not a competitor

---

## 3. LIRE Status

**LIRE experiments are complete but results should NOT be added to the paper yet.**

The user wants to ask Professor Zhao (DZ) whether the LIRE data strengthens or hurts the paper before including it. Do not:
- Add LIRE result tables to the paper
- Make quantitative claims based on LIRE
- Add a LIRE BibTeX entry (only the SPFresh citation `zhang2023spfresh` is appropriate as related work)

The LIRE 3-seed experiment (`sift1m_split240_lire_baseline_3seed`) ran to completion after fixing two bugs:
1. Stale-partition guard in `refine_partitions()` (commit `6c15652`)
2. `min_partition_size: 0` in YAML to prevent delete-after-partition-deletion instability

The current paper says "LIRE pending — TODO: replace with confirmed results once stable." Leave this as-is until the user gives explicit permission to include LIRE data.

---

## 4. All Advisor Feedback (Consolidated)

### DZ Meeting 1 (Early)
- Related Work: max 4 subsections; remove/deprioritize SISAP 2013 Boytsov
- Related Work can move before System Design
- Evaluation: no Q-format section titles; use result-style headers
- Evaluation: combine setup sections into one Experimental Setup
- Motivation/use cases: merge into Introduction

### DZ Meeting 2 (Most Recent)
- **Reduce contributions to 3–4** (was 6). DZ suggested:
  1. Identify the missing flexibility/control-plane problem
  2. Design FlexiRefine (score-based selective refinement)
  3. Implement FlexiRefine (C++/Python, mutation tracking, hit tracking, multi-seed infra)
  4. Evaluate: 38–45% maintenance reduction, recall >0.90, Faiss-IVF 4× slower
- **7-section structure:** §1 Intro, §2 BG+Related, §3 Design, §4 Theory, §5 Implementation, §6 Evaluation, §7 Conclusion
- **Motivation** should be prose in Introduction, not a standalone section
- **Section names:** Design of FlexiRefine (not System Design), Theoretical Analysis (not Theoretical Formulation)
- **References:** prioritize DB/systems venues (SIGMOD, VLDB, OSDI, SOSP, NSDI, EuroSys, ICDE); ML only when essential; aim for ~50 total
- **LIRE:** frame as pending/debugging, no quantitative claims yet
- **Writing style:** avoid bullet-heavy writing; use full prose paragraphs like the Quake paper
- **Conclusion:** one strong paragraph as an acceptance argument, not a long limitations section
- **Evaluation:** list research questions explicitly at start of §6, but subsection headers should answer them with result-style titles (not Q-format)
- **Subsection titles should NOT include exact numbers** (e.g., not "Reduces Maintenance by 38–45%" in the header itself)

---

## 5. Paper Structure Requested by DZ

```
§1 Introduction
   - Opening: dynamic vector search problem, existing systems' limitations
   - Motivation prose: recall-critical, maintenance-constrained,
     search-sensitive, balanced users (as prose, NOT a separate section)
   - FlexiRefine framing: refinement as resource allocation
   - Score family introduced briefly
   - 3–4 contributions (numbered list)
   - 7-section roadmap

§2 Background and Related Work
   §2.1 Vector Search Indexes
   §2.2 Dynamic and Streaming Vector Search
   §2.3 Adaptive Query Processing and Index Maintenance
   §2.4 Vector Databases and Data Management Systems
   [Max 4 subsections. No Boytsov SISAP 2013.]

§3 Design of FlexiRefine
   [All 5 modules: candidate generator, metadata tracker, scoring engine,
    budget allocator, refinement executor. 10 scoring policies.]

§4 Theoretical Analysis
   [Score family with physical motivation for each staleness transform.
    Properties 1–3. "No single (β,γ) winner" stated explicitly.]

§5 System Implementation
   [Code structure, libraries (C++17/LibTorch/Faiss/pybind11), parameters,
    pipeline, multi-seed infrastructure, evaluator compat for non-Quake,
    LIRE caveat as TODO.]

§6 Evaluation
   [Research questions listed explicitly at start.
    Subsections use result-style headers that ANSWER the questions.
    Headers should NOT contain exact numbers.]
   §6.1 Experimental Setup
   §6.2 [Score-based refinement main result — positive finding]
   §6.3 [Naive policies fail — negative result]
   §6.4 [Faiss-IVF comparison — dynamic maintenance necessary]
   §6.5 [Multiseed confirmation — policy-class robustness]
   §6.6 [Policy recommendations — user persona mapping]

§7 Conclusion
   [One strong paragraph: paper's argument for acceptance.
    §7.1 Limitations and Discussion (merged)
    §7.2 Future Work]
```

### Critical Style Notes
- **Write like the Quake paper.** The Quake paper at `test/experiments/osdi2025/paper/Quake-Revision.pdf` and `osdi25-mohoney.pdf` is the stylistic target. Read it carefully before revising. It uses full prose paragraphs, not bullet-heavy writing.
- **Subsection headers should NOT contain exact numbers.** "Score-Based Refinement Reduces Maintenance" is fine. "Score-Based Refinement Reduces Maintenance by 38–45%" in the header is too specific per DZ.
- **Conclusion = one tight paragraph.** Not a multi-section limitations dump. Limitations go in a clearly labeled short subsection if kept.
- **Evaluation questions list at top of §6**, before §6.1. The questions orient the reader but subsection titles answer them with result-style declarative statements, not question-format titles.

---

## 6. Files to Inspect

| File | Purpose |
|---|---|
| `docs/flexirefine_paper_draft_current.tex` | Living working paper draft (current version to revise) |
| `docs/flexirefine_refs.bib` | BibTeX file — 33 verified entries + REFERENCES_TO_VERIFY block (~27 candidates) |
| `docs/flexirefine_research_log.md` | Complete experiment history, branch log, raw results, interpretations |
| `docs/flexirefine_dz_revision_summary.md` | Table of every DZ comment → action taken; remaining TODOs |
| `docs/flexirefine-draft.tex` | **Old Overleaf backup — DO NOT EDIT THIS FILE** |
| `test/experiments/osdi2025/paper/Quake-Revision.pdf` | Quake paper — read for style reference |
| `osdi25-mohoney.pdf` | Another copy of the Quake paper |

**To find the Quake PDFs:**
```bash
find . -name "*.pdf" -not -path "./.git/*"
```

**The new model's primary task is:**
1. Read the current paper draft (`docs/flexirefine_paper_draft_current.tex`)
2. Read the Quake paper PDF to understand the target prose style
3. Revise the paper draft to match DZ's latest feedback (especially prose style, not bullet-heavy, clean section structure)
4. Ensure the BibTeX keys in the paper match the new entries in `docs/flexirefine_refs.bib`
5. Do NOT add LIRE results

---

## 7. Branches and Current State

### Active Research Branches (Most Recent First)

| Branch | Commit | What it contains |
|---|---|---|
| `flexirefine-reference-expansion-no-lire-results` | 7fa2824 (base) | Updated `flexirefine_refs.bib` with 33 verified entries. NOT yet committed to remote — the bib update is staged but this is the working branch. |
| `flexirefine-paper-dz-comments-faiss-results` | `7fa2824` | Latest committed paper draft with DZ revision comments applied + Faiss-IVF results + BibTeX file created |
| `flexirefine-lire-stale-partition-guard` | `f18b710` | LIRE crash fixes: stale-partition guard in C++ + `min_partition_size: 0` in YAML |
| `flexirefine-faiss-baseline-nprobe20` | `7bc7df1` | Faiss-IVF nprobe tuned to 20 for fair comparison |
| `flexirefine-confirm-top-configs-3seed` | `9068e16` | Multi-seed runner support + 3-seed confirmation YAML |
| `flexirefine-beta-gamma-scoring` | `bc52a18` | β/γ exponent scoring implemented |
| `flexirefine-density-and-persplit-fix` | `ea4de23` | Per-split cap bug fix + density normalization |
| `adiyan-osdi2025` | `32b1662` | Base branch (all FlexiRefine work branches from here) |

### Key Implementation Details (C++ Changes)

The following C++ changes are on `flexirefine-density-and-persplit-fix` and forward:

1. **`src/cpp/include/common.h`** — `MaintenancePolicyParams` struct adds:
   - `bool refinement_normalize_mutations = false`
   - `double refinement_score_beta = 1.0`
   - `double refinement_score_gamma = 1.0`
   
2. **`src/cpp/src/maintenance_policies.cpp`** — `local_refinement()`:
   - Per-split candidate cap now actually implemented (was dead code before)
   - Score formula: `pow(hits+1, beta) * pow(staleness, gamma)`
   - Density normalization: `staleness = m_p / |p|` when `refinement_normalize_mutations=true`

3. **`src/cpp/src/partition_manager.cpp`** — `refine_partitions()`:
   - Stale-partition guard: filters candidate IDs not present in `partition_store_->partitions_` before calling `kmeans_refine_partitions`, preventing null dereference

4. **`src/python/workload_generator.py`**:
   - Multi-seed runner support (`seeds: [...]` list in YAML)
   - `WorkloadEvaluator`: `parent_info` None-guard, `mi is not None` check for non-Quake indexes
   - Heatmap plotting guard for empty `resident_history`

5. **`test/experiments/osdi2025/maintenance_ablation/run.py`**:
   - Module-level `_INDEX_CLASS_MAP = {"Quake": QuakeWrapper, "FaissIVF": FaissIVF}`
   - Per-index `do_maintenance` flag (only Quake indexes run maintenance)
   - `produce_multiseed_summary()` function for mean±std aggregation

### What Has Been Tried and What the Results Show

| Approach | Result | Status |
|---|---|---|
| Split threshold sweeps | Reduces maintenance but never reaches recall 0.90 | Negative result; in paper |
| Global top-K cap (no ranking) | Same — refines fewer, not better | Negative result; in paper |
| Per-split coverage budgeting | Clean negative after bug fix — never reaches 0.90 | Negative result; in paper |
| Raw mutation scoring `(h+1)*m` | Works — reaches 0.90, reduces maintenance 40-46% | Confirmed; in paper |
| Density scoring `(h+1)*(m/|p|)` | Works — more stable than raw | Confirmed; in paper |
| β/γ exponent family sweep | Column-level pattern: γ=0.5 reduces total time; β=1.5 degrades recall | Single-run directional; in paper |
| 3-seed confirmation | Policy-class claim confirmed; exact (β,γ) winner not stable at n=3 | Primary result; in paper |
| Faiss-IVF baseline | 4.25× slower total, failed 0.90 on one seed | Confirmed; in paper |
| LIRE-style baseline | Complete but pending DZ decision | NOT in paper yet |

---

## 8. Next Task for the New Model

### Primary Objective
Revise `docs/flexirefine_paper_draft_current.tex` to match DZ's latest feedback and the Quake paper's prose style.

### Key Style Changes Needed
1. **Prose over bullets.** The current draft has too many `\begin{itemize}` blocks. Convert these to flowing paragraphs. Read the Quake paper PDF (`osdi25-mohoney.pdf`) carefully — it uses narrative prose throughout.

2. **Subsection headers without exact numbers.** Current draft has headers like "Score-Based Refinement Reduces Maintenance by 38–45%". Per DZ, headers should be declarative but not contain exact result numbers. Change to something like "Score-Based Refinement Exposes a Maintenance–Recall Tradeoff" or similar.

3. **One-paragraph conclusion.** The current §7 Conclusion opens with a paragraph but then has several subsections. The main conclusion statement should be a tight, single strong paragraph. Limitations and future work can be brief subsections.

4. **Citation keys.** The new BibTeX file (`docs/flexirefine_refs.bib`) has these keys that the paper draft's `\cite{}` commands don't yet use correctly:
   - `baranchuk2023dedrift` — replaces `todo-dedrift` in §2.2
   - `singh2021freshdiskann` — replaces `todo-freshdiskann` in §2.2
   - `aguerrebere2024svs` — new, add to §2.2
   - `leis2014morsel` — add to §2.3
   - `kraska2018learned`, `ding2020alex`, `marcus2021bao` — add to §2.3
   - `grbovic2018airbnb`, `pal2020pinnersage` — add to §2.4
   - `karpukhin2020dpr`, `khattab2020colbert` — add to §2.4
   - `babenko2012invertedmulti`, `ge2013opq`, `simhadri2022bigann`, `douze2024faiss` — add to §2.1
   - `hellerstein2000eddies`, `idreos2007cracking` — add to §2.3

5. **Keep LIRE as TODO.** The current draft has `\todo{Replace with confirmed 3-seed LIRE results...}` in §6.4. Leave this exactly as-is.

6. **Do not add or remove Faiss-IVF results.** The 3-seed Faiss-IVF table in §6.4 is correct and confirmed.

### Constraints for the New Model
- Do NOT add LIRE quantitative results to the paper
- Do NOT change C++ code
- Do NOT change YAML experiment configs
- Do NOT edit `docs/flexirefine-draft.tex` (old Overleaf backup)
- Do NOT delete tables or reduce content
- Keep all confirmed quantitative claims: 38–45%, recall >0.90, <5% overhead, Faiss-IVF 4×
- Branch to work on: create a new branch from `flexirefine-reference-expansion-no-lire-results`
- Commit only docs/ files

---

## 9. Quick Reference: Score Family Notation

| Symbol | Meaning |
|---|---|
| `h_p` | Number of recent queries that scanned partition p (sliding window) |
| `m_p` | Mutation count since last refinement for partition p |
| `\|p\|` | Current size (number of resident vectors) of partition p |
| `D(p)` | Staleness signal: raw = `m_p`, density = `m_p / \|p\|` |
| `β` | Exponent on `(h_p + 1)` — importance sensitivity. β < 1 = diminishing returns |
| `γ` | Exponent on `D(p)` — staleness sensitivity. γ < 1 = diminishing returns |
| `ε` | Small smoothing constant (default: 1, via the `+1` in `(h_p + 1)`) |
| `K` | Top-K refinement budget (`refinement_top_k_score` in YAML) |
| `r_f` | Refinement radius (number of nearest neighbor candidates per split centroid) |

### Current Best Configurations (from 3-seed confirmation)

| User Priority | Recommended Config | β | γ | Density | K |
|---|---|---|---|---|---|
| Recall-critical | Quake full refinement | — | — | — | — |
| Maintenance-constrained | Score50-Raw-Linear | 1.0 | 1.0 | false | 50 |
| Balanced | D70-B0.5-G0.5 | 0.5 | 0.5 | true | 70 |
| Stability/simplicity | Density70-Linear | 1.0 | 1.0 | true | 70 |

---

## 10. Remaining TODOs Before Sharing with DZ

- [ ] **Revise prose style** to match Quake paper (fewer bullets, more narrative paragraphs)
- [ ] **Fix subsection headers** to remove exact numbers per DZ feedback
- [ ] **Update citation keys** in paper to use the new BibTeX entries
- [ ] **Expand related work text** to cite the new references
- [ ] **Add LIRE results** — only after user explicitly asks DZ and gets approval
- [ ] **CloudLab platform spec** — fill in §6.1 hardware details (TODO placeholder)
- [ ] **LOC estimate** — fill in §5.1 approximate lines of code (TODO placeholder)
- [ ] **Pareto frontier figure** — generate actual Figure 2 from `summary_table.csv` data
- [ ] **n=5 seeds** — extend confirmation to seeds 1337 and 2024
- [ ] **HNSW/ScaNN baselines** — pending; HNSW needs delete-free workload variant
- [ ] **Fill REFERENCES_TO_VERIFY** — verify ~27 candidate references before submission
