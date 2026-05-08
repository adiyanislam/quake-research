# FlexiRefine — DZ Revision Summary
## Branch: `flexirefine-paper-dz-comments-faiss-results`
## Date: 2026-05-05

This document summarizes all changes made in this revision pass, keyed to DZ's
specific comments. For full experiment history, see `flexirefine_research_log.md`.

---

## 1. How Each DZ Comment Was Addressed

| DZ Comment | Action Taken | Section Affected |
|---|---|---|
| Reduce contributions to 3–4 | Condensed from 6 to exactly 4 (C1–C4) | §1 Introduction |
| Merge motivation/use cases into Introduction | Four user personas as prose paragraphs in §1; standalone motivation section removed | §1 |
| Use 7-section structure | Paper now has exactly 7 top-level sections; Discussion + Future Work are §7.1 and §7.2 | All |
| Section 2: Background and Related Work | Renamed from "Related Work"; content kept with 4 subsections | §2 |
| Section 3: Design of FlexiRefine | Renamed from "System Design" | §3 |
| Section 4: Theoretical Analysis | Renamed from "Theoretical Formulation"; added physical motivation for each staleness transform | §4 |
| Evaluation: list RQs at start | 5 explicit RQs listed before §6.1; all subsections use result-style headers | §6 |
| Evaluation: result-style headers | All subsection titles now answer questions (no Q-format titles) | §6 |
| Evaluation: per-subsection comparisons | Each subsection maps to one RQ; Faiss-IVF in §6.4, multiseed confirmation in §6.5 | §6.3–6.6 |
| Do not over-claim one (β,γ) winner | Paper explicitly states "no single pair is universally optimal" in §4 and §6.5 | §4, §6 |
| LIRE: frame as pending/debugging | LIRE appears as TODO placeholder in §6.4 with explanation; no quantitative claims | §5.5, §6.4 |
| No more than 4 related-work subsections | Exactly 4: Vector Indexes, Dynamic Search, Adaptive Query, Vector Databases | §2 |
| Remove/deprioritize SISAP Boytsov | Not present in any section | §2 |
| DB/systems venues first in references | BibTeX contains SOSP, OSDI, SIGMOD, PVLDB, TPAMI entries; ML only for RAG/CLIP | refs.bib |
| No fabricated BibTeX entries | Only 12 real verified entries + todo-quake placeholder; uncertain refs in VERIFY block | refs.bib |
| Strong conclusion | §7 opens with a 5-sentence acceptance argument summarizing the paper's contribution | §7 |

---

## 2. New Results Added

### Faiss-IVF 3-Seed Baseline (§6.4) — [CONFIRMED]

Full `mean ± std` table across seeds {9299, 42, 12345}:

| Config | Maintain (ms) | Total (ms) | Recall |
|---|---|---|---|
| Quake | 70,682 ± 15,431 | 309,741 ± 66,555 | 0.9118 ± 0.0134 |
| Score50-Raw-Linear | 38,579 ± 7,528 | 321,162 ± 64,340 | 0.9017 ± 0.0192 |
| Density70-Linear | 43,735 ± 11,913 | 323,591 ± 54,505 | 0.9039 ± 0.0165 |
| D70-B0.5-G0.5 | 42,224 ± 4,609 | 316,609 ± 54,402 | 0.9064 ± 0.0184 |
| Faiss-IVF (nprobe=20) | 0 ± 0 | 1,315,646 ± 782,124 | 0.9269 ± 0.0668 |

**Key claims now in paper:**
- Score-based selective refinement: 38–45% maintenance reduction, recall ≥ 0.90, <5% total overhead. **[CONFIRMED]**
- Faiss-IVF: 4.25× slower total runtime than Quake; failed 0.90 recall on one seed. **[CONFIRMED]**

---

## 3. Files Changed

| File | Change summary |
|---|---|
| `docs/flexirefine_paper_draft_current.tex` | Full rewrite: 7-section structure, 4 contributions, Faiss-IVF table, RQ preamble, LIRE framed as pending. 1170 lines (was 1054). |
| `docs/flexirefine_refs.bib` | **New file.** 12 verified BibTeX entries + todo-quake placeholder + REFERENCES_TO_VERIFY comment block (~20 candidate entries to confirm). |
| `docs/flexirefine_research_log.md` | Appended §15 (DZ comments), §4.6 (Faiss-IVF results), LIRE status update, updated claims and next steps. |
| `docs/flexirefine_dz_revision_summary.md` | **New file.** This document. |

---

## 4. Paper Structure After This Revision

```
Abstract: 38–45% maintenance, recall > 0.90, <5% overhead, Faiss-IVF 4.25× slower

§1 Introduction
   - Motivation prose: 4 user personas
   - 4 contributions (C1–C4)
   - 7-section roadmap

§2 Background and Related Work
   §2.1 Vector Search Indexes          (HNSW, DiskANN, Faiss, ScaNN, SPANN, PQ)
   §2.2 Dynamic and Streaming          (SPFresh, Quake, DeDrift, FreshDiskANN)
   §2.3 Adaptive Query Processing      (VBASE, APS/LAET/Auncel, DB cracking)
   §2.4 Vector Databases               (Milvus, AnalyticDB-V, VBASE)

§3 Design of FlexiRefine
   §3.1–§3.6  [5 modules + 10 scoring policies]

§4 Theoretical Analysis
   §4.1 Refinement Utility
   §4.2 Importance and Staleness       [expanded with physical motivation per transform]
   §4.3 General Score Family           [explicit "no single winner" statement]
   §4.4 Properties 1–3

§5 System Implementation
   §5.1 Code Structure                 [libraries: C++17, LibTorch, Faiss, pybind11]
   §5.2 New Parameters
   §5.3 Selective Refinement Pipeline
   §5.4 Multi-Seed Evaluation Infra    [NEW]
   §5.5 Evaluator Compat + LIRE note   [NEW]
   §5.6 Engineering Considerations

§6 Evaluation
   RQ1–RQ5 preamble
   §6.1 Experimental Setup             [Faiss-IVF + LIRE TODO in baselines list]
   §6.2 Score-Based: 38–45% reduction  [density sweep + exponent grid, single-run]
   §6.3 Coverage-Only: fails recall    [split-threshold, top-K, per-split negatives]
   §6.4 Static IVF: 4× total runtime   [Faiss-IVF 3-seed confirmed table, LIRE TODO]
   §6.5 Multiseed confirms policy-class [3-seed FlexiRefine confirmation table]
   §6.6 Policy recommendations         [user persona → config mapping]

§7 Conclusion
   [Strong 5-sentence acceptance argument]
   §7.1 Limitations and Discussion
   §7.2 Future Work
```

---

## 5. Remaining TODOs Before Sharing with DZ

- [ ] Complete LIRE 3-seed baseline and add to §6.4
- [ ] Fill in CloudLab platform spec in §6.1
- [ ] Add approximate LOC in §5.1
- [ ] Expand references toward 50–60 total (verify entries in `REFERENCES_TO_VERIFY` block)
- [ ] Fill in Quake paper citation (todo-quake) once publicly available
- [ ] Add HNSW/ScaNN results to §6.8 placeholder (optional for first advisor sharing)
- [ ] Generate actual Pareto frontier figure for Figure 2 placeholder
- [ ] Proofread all `\todo{}` tags and resolve or note as pending

---

## 6. What This Revision Does NOT Change

- C++ code: unchanged
- Experiment configs (YAMLs): unchanged
- Existing result CSVs: unchanged
- Any existing confirmed quantitative claims: all preserved
- Old Overleaf draft (`flexirefine-draft.tex`): untouched
