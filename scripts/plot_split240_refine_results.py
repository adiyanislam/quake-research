#!/usr/bin/env python3
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt


RESULTS = Path(
    "test/experiments/osdi2025/maintenance_ablation/results/"
    "sift1m_split240_refine_sweep/summary_table.csv"
)


def main() -> None:
    df = pd.read_csv(RESULTS)

    numeric_cols = ["Search", "Insert", "Delete", "Maintain", "Total", "Recall", "Partitions"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    quake = df[df["Index"] == "Quake"].copy()
    split_only = df[df["Index"] == "Quake-NoRefine-Split240"].copy()
    sweep = df[df["Index"].str.contains("Quake-Split240-Refine", na=False)].copy()

    def refine_key(name: str) -> int:
        return int(name.split("Refine")[-1])

    sweep["refine_level"] = sweep["Index"].map(refine_key)
    sweep = sweep.sort_values("refine_level")

    out_dir = RESULTS.parent

    # Recall vs maintenance
    plt.figure(figsize=(8, 6))
    plt.plot(sweep["Recall"], sweep["Maintain"], marker="o", label="Split240 + refine sweep")
    for _, row in sweep.iterrows():
        plt.annotate(str(int(row["refine_level"])), (row["Recall"], row["Maintain"]), fontsize=8)

    if not quake.empty:
        plt.scatter(quake["Recall"], quake["Maintain"], s=90, label="Quake")
        for _, row in quake.iterrows():
            plt.annotate(row["Index"], (row["Recall"], row["Maintain"]), fontsize=8)

    if not split_only.empty:
        plt.scatter(split_only["Recall"], split_only["Maintain"], s=90, label="Split240 no refine")
        for _, row in split_only.iterrows():
            plt.annotate(row["Index"], (row["Recall"], row["Maintain"]), fontsize=8)

    plt.xlabel("Recall")
    plt.ylabel("Maintenance Time")
    plt.title("Recall vs Maintenance Time")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_dir / "recall_vs_maintain_split240_refine.png", dpi=200)
    plt.close()

    # Recall vs search
    plt.figure(figsize=(8, 6))
    plt.plot(sweep["Recall"], sweep["Search"], marker="o", label="Split240 + refine sweep")
    for _, row in sweep.iterrows():
        plt.annotate(str(int(row["refine_level"])), (row["Recall"], row["Search"]), fontsize=8)

    if not quake.empty:
        plt.scatter(quake["Recall"], quake["Search"], s=90, label="Quake")
        for _, row in quake.iterrows():
            plt.annotate(row["Index"], (row["Recall"], row["Search"]), fontsize=8)

    if not split_only.empty:
        plt.scatter(split_only["Recall"], split_only["Search"], s=90, label="Split240 no refine")
        for _, row in split_only.iterrows():
            plt.annotate(row["Index"], (row["Recall"], row["Search"]), fontsize=8)

    plt.xlabel("Recall")
    plt.ylabel("Search Time")
    plt.title("Recall vs Search Time")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_dir / "recall_vs_search_split240_refine.png", dpi=200)
    plt.close()

    # Recall vs total
    plt.figure(figsize=(8, 6))
    plt.plot(sweep["Recall"], sweep["Total"], marker="o", label="Split240 + refine sweep")
    for _, row in sweep.iterrows():
        plt.annotate(str(int(row["refine_level"])), (row["Recall"], row["Total"]), fontsize=8)

    if not quake.empty:
        plt.scatter(quake["Recall"], quake["Total"], s=90, label="Quake")
        for _, row in quake.iterrows():
            plt.annotate(row["Index"], (row["Recall"], row["Total"]), fontsize=8)

    if not split_only.empty:
        plt.scatter(split_only["Recall"], split_only["Total"], s=90, label="Split240 no refine")
        for _, row in split_only.iterrows():
            plt.annotate(row["Index"], (row["Recall"], row["Total"]), fontsize=8)

    plt.xlabel("Recall")
    plt.ylabel("Total Time")
    plt.title("Recall vs Total Time")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_dir / "recall_vs_total_split240_refine.png", dpi=200)
    plt.close()

    print("Wrote plots to:", out_dir)


if __name__ == "__main__":
    main()