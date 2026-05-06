#!/usr/bin/env python3
"""
Quake Maintenance Policy Ablation Study Runner
───────────────────────────────────────────────
This experiment evaluates different maintenance policy configurations within Quake
under a dynamic workload involving inserts, deletes, and queries.
It generates detailed reports including:
1. Per-index CSV logs of operations.
2. A 9-panel unified plot comparing various metrics across configurations.
3. A stacked bar chart breaking down cumulative time per operation type.
4. A summary table (CSV and Markdown) of key performance indicators.

Multi-seed support:
If workload_generator.seeds (list) is present in the YAML, the experiment loops
over each seed, generating a separate workload in main_output_dir/seed_{s}/ and
evaluating all indexes against it.  After all seeds finish, aggregate mean±std
tables are written to main_output_dir/multiseed_raw.csv,
multiseed_summary.csv, and multiseed_summary.md.

If only workload_generator.seed (int) is present, the experiment behaves exactly
as before — no behaviour change.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Any # Added Any for type hinting

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from tabulate import tabulate
from matplotlib.cm import get_cmap
from matplotlib.lines import Line2D

# Common utilities
import test.experiments.osdi2025.experiment_utils as common_utils

# Index wrapper imports
from quake.index_wrappers.quake import QuakeWrapper
from quake.index_wrappers.faiss_ivf import FaissIVF

# Module-level index class map — add new wrappers here as baselines are added.
# do_maintenance is automatically disabled for non-Quake indexes (they return None).
_INDEX_CLASS_MAP = {
    "Quake":    QuakeWrapper,
    "FaissIVF": FaissIVF,
}

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger(__name__)

OP_STYLE = {
    "query":    dict(ls="-", marker="o", mfc="none", ms=4, lw=1.2),
    "insert":   dict(ls="-", marker="s", mfc="none", ms=4, lw=1.2),
    "delete":   dict(ls="-", marker="^", mfc="none", ms=4, lw=1.2),
    "maintain": dict(ls="None", marker="X", mfc="black", ms=5),
}
LAT_OPS = ["query", "insert", "delete", "maintain"]
IDX_LAT_Q, IDX_LAT_I, IDX_LAT_D, IDX_LAT_M = 0, 1, 2, 3
IDX_PART, IDX_RES, IDX_REC, IDX_TOT, IDX_SPL = 4, 5, 6, 7, 8

# Metric columns collected per run
_METRICS = ["Search", "Insert", "Delete", "Maintain", "Total", "Recall", "Partitions"]


def unified_plot(cfg: Dict[str, Any], out_dir: Path) -> None:
    styles = cfg["plot"].get("styles", {})
    fig, axs2d = plt.subplots(3, 3, figsize=(18, 12), sharex="col")
    axs = axs2d.flatten()

    idx_handles: List[Line2D] = []
    for j, idx_cfg in enumerate(cfg.get("indexes", [])): # Added .get for safety
        nm, st = idx_cfg["name"], styles.get(idx_cfg["name"], {})
        idx_handles.append(Line2D([0], [0],
                                  color=st.get("color", f"C{j % 10}"),
                                  marker=st.get("marker", "o"),
                                  ls="", markersize=6, label=nm))

    max_ops_overall = 0

    for j, idx_cfg in enumerate(cfg.get("indexes", [])):
        name = idx_cfg["name"]
        st = styles.get(name, {})
        colour = st.get("color", f"C{j % 10}")
        marker = st.get("marker", "o")

        csv_path = out_dir / name / "results.csv"
        if not csv_path.exists():
            log.warning("[unified_plot] Results CSV %s missing – skipped for this index.", csv_path)
            continue
        try:
            df = pd.read_csv(csv_path)
            if df.empty:
                log.warning(f"[unified_plot] Empty CSV: {csv_path}")
                continue
            if 'operation_number' in df.columns and not df['operation_number'].empty:
                max_ops_overall = max(max_ops_overall, df.operation_number.max())
        except pd.errors.EmptyDataError:
            log.warning(f"[unified_plot] Could not read or empty CSV: {csv_path}")
            continue

        # Latency plots
        for op, ax_idx_val in zip(LAT_OPS, [IDX_LAT_Q, IDX_LAT_I, IDX_LAT_D, IDX_LAT_M]):
            ax = axs[ax_idx_val]
            y_val_series = None
            if op == "maintain":
                if 'maintenance_time_ms' in df.columns:
                    sub = df[df.maintenance_time_ms.fillna(0) > 0]
                    y_val_series = sub.maintenance_time_ms
            elif 'operation_type' in df.columns and 'latency_ms' in df.columns:
                sub = df[df.operation_type == op]
                y_val_series = sub.latency_ms

            if y_val_series is not None and not y_val_series.empty:
                ax.plot(sub.operation_number, y_val_series, color=colour, **OP_STYLE[op])

        # Other metric plots
        plot_specs = [
            (IDX_PART, 'n_list'), (IDX_RES, 'n_resident'),
            (IDX_REC, 'recall', lambda d: (d.operation_type == "query") & d.recall.notna()),
            (IDX_TOT, 'total_cumulative_time',
             lambda d: pd.Series(np.cumsum(d.latency_ms.fillna(0) + d.maintenance_time_ms.fillna(0)), name='total_cumulative_time')),
            (IDX_SPL, ['n_splits', 'n_deletes']) # Special handling for splits/deletes
        ]

        for spec_item in plot_specs:
            ax_idx_val = spec_item[0]
            metric_name_or_list = spec_item[1]
            condition_func = spec_item[2] if len(spec_item) > 2 else lambda d: d[metric_name_or_list].notna()

            ax = axs[ax_idx_val]

            if ax_idx_val == IDX_TOT: # Cumulative time calculation
                if 'latency_ms' in df.columns and 'maintenance_time_ms' in df.columns:
                    total_ms_series = np.cumsum(df.latency_ms.fillna(0) + df.maintenance_time_ms.fillna(0))
                    if not total_ms_series.empty:
                        ax.plot(df.operation_number, total_ms_series, color=colour, marker=marker, lw=1.2)
                continue

            if ax_idx_val == IDX_SPL: # Splits and deletes
                if 'operation_number' in df.columns:
                    spl_series = df.n_splits.fillna(0) if 'n_splits' in df.columns else pd.Series(0, index=df.index)
                    del_series = df.n_deletes.fillna(0) if 'n_deletes' in df.columns else pd.Series(0, index=df.index)
                    if not df.empty:
                        if (spl_series > 0).any(): ax.step(df.operation_number, np.cumsum(spl_series), where="post", color=colour, ls="--", lw=1.2)
                        if (del_series > 0).any(): ax.step(df.operation_number, np.cumsum(del_series), where="post", color=colour, ls=":",  lw=1.2)
                continue

            # General case for other plots
            if isinstance(metric_name_or_list, str) and metric_name_or_list in df.columns:
                sub_df = df[condition_func(df)]
                if not sub_df.empty:
                    ax.plot(sub_df.operation_number, sub_df[metric_name_or_list], color=colour, marker=marker, lw=1.2)

    titles = {
        IDX_LAT_Q: "Latency – Query", IDX_LAT_I: "Latency – Insert",
        IDX_LAT_D: "Latency – Delete", IDX_LAT_M: "Latency – Maintain",
        IDX_PART:  "# Partitions", IDX_RES:   "Resident Vectors",
        IDX_REC:   "Recall", IDX_TOT:   "Running Total Time (ms)",
        IDX_SPL:   "Cumulative Splits / Deletes",
    }
    y_labels_map = {
        IDX_PART: "Count", IDX_RES: "# Vectors", IDX_REC: "Recall",
        IDX_TOT: "Cumulative Time (ms)", IDX_SPL: "Count"
    }
    for i, ax_val in enumerate(axs):
        ax_val.set_title(titles[i], fontsize=11)
        ax_val.grid(True, which="both", ls=":", alpha=0.7)
        ax_val.set_axisbelow(True)
        if i in y_labels_map: ax_val.set_ylabel(y_labels_map[i])
        # Set x-label only for the bottom row of plots
        if i // 3 == 2 : ax_val.set_xlabel("Operation #")

        is_latency_plot = i in [IDX_LAT_Q, IDX_LAT_I, IDX_LAT_D, IDX_LAT_M]
        if is_latency_plot: ax_val.set_ylabel("Latency (ms)")


    if max_ops_overall > 0:
        for ax_val in axs:
            ax_val.set_xlim(left=0, right=max_ops_overall)

    fig.legend(idx_handles, [h.get_label() for h in idx_handles],
               loc="upper center", bbox_to_anchor=(0.5, 1.035),
               ncol=min(4, len(idx_handles)),
               fontsize=9, title="Index Configuration", frameon=False)

    plt.tight_layout(rect=[0, 0.03, 1, 0.97])
    out_plot_path = out_dir / "unified_plot.png"
    plt.savefig(out_plot_path, dpi=150)
    log.info("Unified plot saved to %s", out_plot_path)
    plt.close(fig)


def make_time_breakdown(cfg: Dict[str, Any], out_dir: Path) -> None:
    categories = ["Search", "Insert", "Delete", "Maintain", "Total"]
    totals_data, recall_data = {}, {}
    cmap = get_cmap("tab10")

    for j, idx_cfg in enumerate(cfg.get("indexes", [])):
        name = idx_cfg["name"]
        csv_path = out_dir / name / "results.csv"
        if not csv_path.exists():
            log.warning("[time_breakdown] %s missing – skipped", csv_path)
            continue
        try:
            df = pd.read_csv(csv_path)
            if df.empty: raise pd.errors.EmptyDataError
        except pd.errors.EmptyDataError:
            log.warning(f"[time_breakdown] Empty or unreadable CSV: {csv_path}")
            continue

        totals_data[name] = [
            df[df.operation_type == "query"].latency_ms.sum() if 'operation_type' in df.columns else 0,
            df[df.operation_type == "insert"].latency_ms.sum() if 'operation_type' in df.columns else 0,
            df[df.operation_type == "delete"].latency_ms.sum() if 'operation_type' in df.columns else 0,
            df.maintenance_time_ms.fillna(0).sum() if 'maintenance_time_ms' in df.columns else 0,
        ]
        totals_data[name].append(sum(totals_data[name]))

        query_df = df[df.operation_type == "query"] if 'operation_type' in df.columns else pd.DataFrame()
        recall_data[name] = query_df.recall.mean() if not query_df.empty and 'recall' in query_df else np.nan


    if not totals_data:
        log.info("[time_breakdown] No data available for time breakdown plot.")
        return

    n_idx, n_cats = len(totals_data), len(categories)
    x_indices = np.arange(n_cats)
    bar_width = 0.8 / max(1, n_idx)

    fig, ax = plt.subplots(figsize=(max(10, n_idx * 1.5 + 2), 6))
    for j, (name, values) in enumerate(totals_data.items()):
        style = cfg.get("plot", {}).get("styles", {}).get(name, {})
        color = style.get("color", cmap(j % cmap.N))
        x_offset = x_indices + (j - (n_idx - 1) / 2) * bar_width
        ax.bar(x_offset, values, width=bar_width, label=name, color=color, edgecolor="black")
        current_recall = recall_data.get(name)
        if pd.notna(current_recall) and values[0] > 0:
            ax.text(x_offset[0], values[0] * 1.01, f"R={current_recall:.3f}",
                    ha="center", va="bottom", fontsize=8, rotation=90, color='dimgrey') # Standard color for text

    ax.set_xticks(x_indices)
    ax.set_xticklabels(categories, fontsize=10)
    ax.set_ylabel("Cumulative Time (ms)", fontsize=10)
    ax.set_title("Time Breakdown per Index Configuration", fontsize=12)
    ax.legend(title="Index Configuration", frameon=False, fontsize=9)
    ax.grid(True, axis='y', linestyle=':', alpha=0.7)
    plt.tight_layout()

    out_plot_path = out_dir / "time_breakdown.png"
    plt.savefig(out_plot_path, dpi=150)
    log.info("Time breakdown plot saved to %s", out_plot_path)
    plt.close(fig)


def produce_summary_table(cfg: Dict[str, Any], out_dir: Path) -> None:
    rows = []
    for idx_cfg in cfg.get("indexes", []):
        name = idx_cfg["name"]
        csv_path = out_dir / name / "results.csv"
        if not csv_path.exists():
            log.warning("[summary_table] %s missing – skipped", csv_path)
            continue
        try:
            df = pd.read_csv(csv_path)
            if df.empty: raise pd.errors.EmptyDataError
        except pd.errors.EmptyDataError:
            log.warning(f"[summary_table] Empty or unreadable CSV: {csv_path}")
            continue

        search_time = df[df.operation_type == "query"].latency_ms.sum() if 'operation_type' in df.columns else 0
        insert_time = df[df.operation_type == "insert"].latency_ms.sum() if 'operation_type' in df.columns else 0
        delete_time = df[df.operation_type == "delete"].latency_ms.sum() if 'operation_type' in df.columns else 0
        maintain_time = df.maintenance_time_ms.fillna(0).sum() if 'maintenance_time_ms' in df.columns else 0
        total_time = search_time + insert_time + delete_time + maintain_time

        query_df = df[df.operation_type == "query"] if 'operation_type' in df.columns else pd.DataFrame()
        recall_val = query_df.recall.mean() if not query_df.empty and 'recall' in query_df else np.nan

        n_list_series = df.n_list.dropna() if 'n_list' in df.columns else pd.Series(dtype=float) # ensure series exists
        n_partitions_val = n_list_series.iloc[-1] if not n_list_series.empty else np.nan

        rows.append(dict(
            Index=name, Search=int(search_time), Insert=int(insert_time),
            Delete=int(delete_time), Maintain=int(maintain_time), Total=int(total_time),
            Recall=f"{recall_val:.4f}" if pd.notna(recall_val) else "—",
            Partitions=int(n_partitions_val) if pd.notna(n_partitions_val) else "—"
        ))

    if not rows:
        log.info("[summary_table] No data for summary table.")
        return

    summary_df = pd.DataFrame(rows).sort_values("Index")
    summary_csv_path = out_dir / "summary_table.csv"
    common_utils.save_results_csv(summary_df, summary_csv_path) # Use common util

    summary_md_path = out_dir / "summary_table.md"
    md_content = tabulate(summary_df, headers="keys", tablefmt="github", showindex=False)
    summary_md_path.write_text(md_content + "\n")
    log.info("Summary table (Markdown) saved to %s", summary_md_path)
    log.info("\n%s", md_content)


# ── Multi-seed helpers ────────────────────────────────────────────────────────

def _extract_summary_row(name: str, csv_path: Path) -> Dict[str, Any] | None:
    """
    Extract a numeric summary dict for one index from its results.csv.
    Returns None (with a warning) if the file is missing or unreadable.
    """
    if not csv_path.exists():
        log.warning("[extract_summary] %s missing – skipped", csv_path)
        return None
    try:
        df = pd.read_csv(csv_path)
        if df.empty:
            raise pd.errors.EmptyDataError
    except Exception as exc:
        log.warning("[extract_summary] Could not read %s: %s", csv_path, exc)
        return None

    search_time  = df[df.operation_type == "query"].latency_ms.sum()  if 'operation_type' in df.columns else 0.0
    insert_time  = df[df.operation_type == "insert"].latency_ms.sum() if 'operation_type' in df.columns else 0.0
    delete_time  = df[df.operation_type == "delete"].latency_ms.sum() if 'operation_type' in df.columns else 0.0
    maintain_time = df.maintenance_time_ms.fillna(0).sum()            if 'maintenance_time_ms' in df.columns else 0.0
    total_time   = search_time + insert_time + delete_time + maintain_time

    query_df  = df[df.operation_type == "query"] if 'operation_type' in df.columns else pd.DataFrame()
    recall    = float(query_df.recall.mean()) if (not query_df.empty and 'recall' in query_df.columns) else np.nan

    n_list    = df.n_list.dropna() if 'n_list' in df.columns else pd.Series(dtype=float)
    partitions = float(n_list.iloc[-1]) if not n_list.empty else np.nan

    return dict(
        Index=name,
        Search=float(search_time),
        Insert=float(insert_time),
        Delete=float(delete_time),
        Maintain=float(maintain_time),
        Total=float(total_time),
        Recall=recall,
        Partitions=partitions,
    )


def produce_multiseed_summary(
    cfg: Dict[str, Any],
    main_output_dir: Path,
    seeds: List[int],
) -> None:
    """
    After all seeds finish, collect per-seed results and write:
      multiseed_raw.csv     — one row per (seed, index)
      multiseed_summary.csv — one row per index, mean and std columns
      multiseed_summary.md  — human-readable mean ± std table

    Missing result files are warned and skipped; the function does not crash.
    """
    raw_rows: List[Dict[str, Any]] = []

    for s in seeds:
        seed_dir = main_output_dir / f"seed_{s}"
        for idx_cfg in cfg.get("indexes", []):
            name = idx_cfg["name"]
            csv_path = seed_dir / name / "results.csv"
            row = _extract_summary_row(name, csv_path)
            if row is not None:
                row["seed"] = s
                raw_rows.append(row)

    if not raw_rows:
        log.warning("[multiseed_summary] No data collected across any seed — skipping aggregate.")
        return

    # ── Write raw CSV ──────────────────────────────────────────────────────────
    raw_df = pd.DataFrame(raw_rows)
    raw_csv_path = main_output_dir / "multiseed_raw.csv"
    raw_df.to_csv(raw_csv_path, index=False)
    log.info("Multi-seed raw data saved to %s", raw_csv_path)

    # ── Compute mean ± std per index ──────────────────────────────────────────
    agg_rows: List[Dict[str, Any]] = []
    for idx_cfg in cfg.get("indexes", []):          # preserve YAML ordering
        name = idx_cfg["name"]
        grp  = raw_df[raw_df["Index"] == name]
        if grp.empty:
            log.warning("[multiseed_summary] No rows for index '%s' – skipped", name)
            continue
        row: Dict[str, Any] = {"Index": name}
        for m in _METRICS:
            if m in grp.columns:
                vals = grp[m].dropna()
                row[f"{m}_mean"] = float(vals.mean())          if len(vals) >= 1 else np.nan
                row[f"{m}_std"]  = float(vals.std(ddof=1))     if len(vals) >= 2 else np.nan
            else:
                row[f"{m}_mean"] = np.nan
                row[f"{m}_std"]  = np.nan
        row["n_seeds"] = len(grp)
        agg_rows.append(row)

    if not agg_rows:
        log.warning("[multiseed_summary] Aggregation produced no rows.")
        return

    summary_df = pd.DataFrame(agg_rows)
    summary_csv_path = main_output_dir / "multiseed_summary.csv"
    summary_df.to_csv(summary_csv_path, index=False)
    log.info("Multi-seed summary (CSV) saved to %s", summary_csv_path)

    # ── Build readable mean ± std display table ────────────────────────────────
    display_df = summary_df[["Index"]].copy()
    for m in _METRICS:
        mean_col = f"{m}_mean"
        std_col  = f"{m}_std"
        if mean_col not in summary_df.columns:
            continue

        def _fmt(row: pd.Series, _m: str = m) -> str:
            mu  = row[f"{_m}_mean"]
            sig = row[f"{_m}_std"]
            if pd.isna(mu):
                return "—"
            if _m == "Recall":
                return f"{mu:.4f} ± {sig:.4f}" if pd.notna(sig) else f"{mu:.4f}"
            return f"{mu:.0f} ± {sig:.0f}" if pd.notna(sig) else f"{mu:.0f}"

        display_df[m] = summary_df.apply(_fmt, axis=1)

    display_df["n_seeds"] = summary_df["n_seeds"]

    summary_md_path = main_output_dir / "multiseed_summary.md"
    header = (
        f"# Multi-Seed Confirmation Summary\n"
        f"Seeds: {seeds} ({len(seeds)} runs per config)\n\n"
    )
    md_body = tabulate(display_df, headers="keys", tablefmt="github", showindex=False)
    summary_md_path.write_text(header + md_body + "\n")
    log.info("Multi-seed summary (Markdown) saved to %s", summary_md_path)
    log.info("\n%s", md_body)


def _run_single_seed(
    cfg: Dict[str, Any],
    seed: int,
    seed_dir: Path,
    current_mode: str,
    overwrite_workload: bool,
    overwrite_results: bool,
) -> None:
    """
    Run Phase 1 (workload generation), Phase 2 (index evaluation), and Phase 3
    (per-seed plots + summary table) for a single seed value.

    All workload files and index results are written under seed_dir.
    """
    seed_dir.mkdir(parents=True, exist_ok=True)
    log.info("── Seed %d  →  %s ──", seed, seed_dir)

    # Synthesize a workload_generator config with this seed substituted in.
    # The original may have 'seeds' (list); we produce a copy with 'seed' (int).
    wl_cfg_for_seed = dict(cfg["workload_generator"])
    wl_cfg_for_seed["seed"] = seed

    # Phase 1 — workload generation
    if current_mode in {"build", "run"}:
        common_utils.generate_dynamic_workload(
            dataset_main_cfg=cfg["dataset"],
            workload_generator_cfg=wl_cfg_for_seed,
            global_output_dir=seed_dir,
            overwrite_workload=overwrite_workload,
        )

    # Phase 2 — index evaluation
    if current_mode == "run":
        for index_conf in cfg.get("indexes", []):
            # Only Quake indexes perform maintenance; others return None.
            do_maint = (index_conf.get("index", "") == "Quake")
            common_utils.evaluate_index_on_dynamic_workload(
                index_config=index_conf,
                index_class_mapping=_INDEX_CLASS_MAP,
                workload_data_dir=seed_dir,
                experiment_main_output_dir=seed_dir,
                overwrite_idx_results=overwrite_results,
                do_maintenance_flag=do_maint,
            )

    # Phase 3 — per-seed plots and summary (inside seed_dir)
    if current_mode in {"run", "plot"}:
        any_results = any(
            (seed_dir / idx_cfg["name"] / "results.csv").exists()
            for idx_cfg in cfg.get("indexes", [])
        )
        if any_results:
            unified_plot(cfg, seed_dir)
            make_time_breakdown(cfg, seed_dir)
            produce_summary_table(cfg, seed_dir)
        else:
            log.warning("[seed %d] No results found — skipping per-seed plots.", seed)


def run_experiment(cfg_path_str: str, output_dir_str: str) -> None:
    cfg = common_utils.load_config(cfg_path_str)
    main_output_dir = Path(output_dir_str).expanduser()
    main_output_dir.mkdir(parents=True, exist_ok=True)

    current_mode = cfg.get("mode", "run")
    log.info(f"Running Maintenance Ablation experiment in mode: {current_mode}")

    wl_cfg          = cfg.get("workload_generator", {})
    overwrite_workload = cfg.get("overwrite", {}).get("workload", False)
    overwrite_results  = cfg.get("overwrite", {}).get("results", False)

    # ── Multi-seed path (triggered only when workload_generator.seeds is a list) ──
    if "seeds" in wl_cfg:
        seeds = list(wl_cfg["seeds"])
        log.info("Multi-seed mode activated: seeds = %s", seeds)

        for s in seeds:
            seed_dir = main_output_dir / f"seed_{s}"
            _run_single_seed(cfg, s, seed_dir, current_mode, overwrite_workload, overwrite_results)

        if current_mode in {"run", "plot"}:
            produce_multiseed_summary(cfg, main_output_dir, seeds)

        log.info("Maintenance Ablation experiment (multi-seed) finished for mode: %s", current_mode)
        return

    # ── Single-seed path (existing behaviour — unchanged) ─────────────────────
    workload_actual_dir = main_output_dir # Workload files are stored at the top level of main_output_dir

    # --- Phase 1: Dataset and Workload Generation ---
    if current_mode in {"build", "run"}:
        workload_actual_dir = common_utils.generate_dynamic_workload(
            dataset_main_cfg=cfg["dataset"],
            workload_generator_cfg=cfg["workload_generator"],
            global_output_dir=main_output_dir, # Pass main_output_dir as the place to store workload files
            overwrite_workload=cfg["overwrite"].get("workload", False)
        )

    # --- Phase 2: Index Evaluation ---
    if current_mode == "run":
        log.info("Starting index evaluation phase...")
        for index_conf in cfg.get("indexes", []):
            # Only Quake indexes perform maintenance; others return None.
            do_maint = (index_conf.get("index", "") == "Quake")
            common_utils.evaluate_index_on_dynamic_workload(
                index_config=index_conf,
                index_class_mapping=_INDEX_CLASS_MAP,
                workload_data_dir=workload_actual_dir,
                experiment_main_output_dir=main_output_dir,
                overwrite_idx_results=cfg["overwrite"].get("results", False),
                do_maintenance_flag=do_maint,
            )

    # --- Phase 3: Global Artifact Generation ---
    if current_mode in {"run", "plot"}:
        log.info("Generating global plots and summary tables...")
        any_results_exist = any(
            (main_output_dir / index_conf["name"] / "results.csv").exists()
            for index_conf in cfg.get("indexes", [])
        )

        if any_results_exist:
            unified_plot(cfg, main_output_dir)
            make_time_breakdown(cfg, main_output_dir)
            produce_summary_table(cfg, main_output_dir)
        else:
            log.warning("No results found to generate plots or summary tables. Skipping this step.")

    log.info("Maintenance Ablation experiment finished for mode: %s", current_mode)
