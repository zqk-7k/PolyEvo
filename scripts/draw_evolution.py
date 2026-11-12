"""Four-panel manuscript candidate: numerical and preparation development tracks."""
from __future__ import annotations

from collections import defaultdict
import csv
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np


HERE = Path(__file__).resolve().parent
import argparse
_parser = argparse.ArgumentParser()
_parser.add_argument("--data", type=Path, required=True)
_parser.add_argument("--output", type=Path, required=True)
_args = _parser.parse_args()
DATA = _args.data / "figures/figure2"
PROCESS_101 = DATA
OUT = _args.output
OUT.mkdir(parents=True, exist_ok=True)

INK = "#24313A"
MUTED = "#6D7880"
GRID = "#E7ECEF"
GREY = "#48525A"
RUST = "#B6634D"
KINDS = ["operation", "parameter", "order", "binding", "state"]
LABELS = ["Operations", "Parameters", "Order", "Sample and\nprocess links", "Material states"]
COLORS = ["#326F98", "#338E87", "#B0853D", "#BD6F63", "#786B97"]

mpl.rcParams.update({
    "font.family": "Arial",
    "font.sans-serif": ["Arial"],
    "font.size": 7,
    "axes.labelsize": 7.5,
    "xtick.labelsize": 6.8,
    "ytick.labelsize": 6.8,
    "axes.linewidth": 0.65,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "svg.fonttype": "none",
    "savefig.facecolor": "white",
})


def read(name, folder=DATA):
    with (folder / name).open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def style(ax):
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(INK)
    ax.spines["bottom"].set_color(INK)
    ax.tick_params(length=2.8, width=0.6, colors=INK, pad=3)


def heading(fig, x, y, letter, title):
    fig.text(x, y, letter, fontsize=9.1, fontweight="bold", color=INK,
             ha="left", va="top")
    fig.text(x + 0.024, y, title, fontsize=8.1, fontweight="bold",
             color=INK, ha="left", va="top")


def legend_item(fig, x, y, color, text):
    fig.add_artist(Line2D([x, x + 0.025], [y, y], transform=fig.transFigure,
                          color=color, linewidth=1.8))
    fig.text(x + 0.032, y, text, ha="left", va="center", fontsize=6.3,
             color=INK)


def paired_axes(ax):
    ax.plot([0, 100], [0, 100], color="#8D989F", linewidth=0.8,
            linestyle=(0, (4, 3)), zorder=0)
    ax.set(xlim=(-3, 103), ylim=(-3, 103),
           xticks=[0, 25, 50, 75, 100], yticks=[0, 25, 50, 75, 100])
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("Before (%)", labelpad=4)
    ax.set_ylabel("After (%)", labelpad=4)
    style(ax)


def main(process_scope="101"):
    assert process_scope in {"101", "31"}
    property_traj = read("property_trajectory_31.csv")
    property_pair = [r for r in read("property_paired_31.csv")
                     if int(r["denominator"]) > 0]
    process_pair = []
    if process_scope == "101":
        process_traj = read("recorded_checkpoints.csv", PROCESS_101)
        process_records = read("paired_article_coverage.csv", PROCESS_101)
        by_paper = defaultdict(list)
        for row in process_records:
            by_paper[row["reference_no"]].append(row)
        assert len(by_paper) == 101
        for pid, records in by_paper.items():
            assert {r["kind"] for r in records} == set(KINDS)
            den = sum(int(r["denominator"]) for r in records)
            bef = sum(int(r["before_hits"]) for r in records)
            aft = sum(int(r["after_hits"]) for r in records)
            process_pair.append((pid, den, 100 * bef / den, 100 * aft / den))
        percent_field, n_process, expected_d = "coverage_percent", 101, 11226
        expected_gains = (60, 41)
        stem = OUT / "Figure_numerical_and_preparation_evolution_v2"
    else:
        process_traj = read("process_trajectory_31.csv")
        for row in read("process_paired_31.csv"):
            if row["kind"] == "pooled":
                process_pair.append((row["reference_no"], int(row["denominator"]),
                                     float(row["before_percent"]), float(row["after_percent"])))
        percent_field, n_process, expected_d = "percent", 31, 2889
        expected_gains = (4, 27)
        stem = OUT / "Figure_numerical_and_preparation_same31_v2"
    assert len(property_pair) == 29 and len(process_traj) == 730
    assert len(process_pair) == n_process
    assert sum(p[1] for p in process_pair) == expected_d
    assert (sum(p[3] > p[2] for p in process_pair),
            sum(p[3] == p[2] for p in process_pair)) == expected_gains
    assert sum(p[3] < p[2] for p in process_pair) == 0

    fig = plt.figure(figsize=(7.20, 6.55))  # 183 x 166 mm
    ax_a = fig.add_axes([0.095, 0.594, 0.380, 0.266])
    ax_b = fig.add_axes([0.592, 0.594, 0.380, 0.266])
    ax_c = fig.add_axes([0.115, 0.087, 0.358, 0.393])
    ax_d = fig.add_axes([0.612, 0.087, 0.358, 0.393])

    heading(fig, 0.095, 0.972, "a", "Numerical recall evolution")
    heading(fig, 0.592, 0.972, "b", "Preparation coverage evolution")
    legend_item(fig, 0.095, 0.916, GREY, "Structured stages")
    legend_item(fig, 0.285, 0.916, RUST, "Final output")
    for x, y, i in [(0.592, 0.925, 0), (0.705, 0.925, 1),
                    (0.839, 0.925, 2), (0.592, 0.893, 3),
                    (0.800, 0.893, 4)]:
        legend_item(fig, x, y, COLORS[i], LABELS[i])

    for metric, color in [("all_stage", GREY), ("released", RUST)]:
        series = sorted((r for r in property_traj if r["metric"] == metric),
                        key=lambda r: int(r["update"]))
        xx = np.array([int(r["update"]) for r in series])
        yy = np.array([float(r["percent"]) for r in series])
        assert len(series) == 19 and np.array_equal(xx, np.arange(19))
        ax_a.plot(xx, yy, color=color, linewidth=1.6, marker="o",
                  markersize=2.0, markeredgewidth=0, zorder=3)
    ax_a.set(xlim=(-0.3, 18.3), ylim=(0, 102),
             xticks=[0, 6, 12, 18], yticks=[0, 25, 50, 75, 100])
    ax_a.set_xlabel("Recorded evaluation", labelpad=4)
    ax_a.set_ylabel("Recall (%)", labelpad=4)
    ax_a.grid(axis="y", color=GRID, linewidth=0.5, zorder=0)
    style(ax_a)

    for kind, color in zip(KINDS, COLORS):
        series = sorted((r for r in process_traj if r["kind"] == kind),
                        key=lambda r: int(r["step"]))
        candidate_ids = np.array([int(r["step"]) for r in series])
        xx = np.arange(len(series))
        yy = np.array([float(r[percent_field]) for r in series])
        assert len(series) == 146 and candidate_ids[0] == 0 and candidate_ids[-1] == 158
        assert np.array_equal(xx, np.arange(146))
        ax_b.plot(xx, yy, color=color, linewidth=1.28, zorder=2)
        ax_b.plot([xx[0], xx[-1]], [yy[0], yy[-1]], "o", color=color,
                  markersize=2.4, markeredgewidth=0, zorder=3)
    ax_b.set(xlim=(-2, 147), ylim=(0, 102),
             xticks=[0, 30, 60, 90, 120, 145], yticks=[0, 25, 50, 75, 100])
    ax_b.set_xlabel("Recorded evaluation", labelpad=4)
    ax_b.set_ylabel("Preparation coverage (%)", labelpad=4)
    ax_b.grid(axis="y", color=GRID, linewidth=0.5, zorder=0)
    style(ax_b)

    heading(fig, 0.095, 0.539, "c", "Paired final recall")
    heading(fig, 0.592, 0.539, "d", "Paired preparation coverage")
    paired_axes(ax_c)
    paired_axes(ax_d)
    for row in property_pair:
        den = int(row["denominator"])
        ax_c.scatter(float(row["before_percent"]), float(row["after_percent"]),
                     s=10 + 2.0 * np.sqrt(den), facecolor=RUST,
                     edgecolor="white", linewidth=0.35, alpha=0.77, zorder=3)
    for _, den, before, after in process_pair:
        ax_d.scatter(before, after, s=10 + 2.0 * np.sqrt(den),
                     facecolor=COLORS[0], edgecolor="white",
                     linewidth=0.25, alpha=0.55, zorder=3)

    # A shared key applies to both paired panels and sits below the axes.
    fig.add_artist(Line2D([0.095, 0.124], [0.025, 0.025],
                          transform=fig.transFigure, color="#8D989F",
                          linewidth=0.8, linestyle=(0, (4, 3))))
    fig.text(0.131, 0.025, "No change", fontsize=6.7, color=INK,
             ha="left", va="center")
    fig.savefig(stem.with_suffix(".pdf"))
    fig.savefig(stem.with_suffix(".svg"))
    fig.savefig(stem.with_suffix(".png"), dpi=300)
    fig.savefig(stem.with_suffix(".tiff"), dpi=600,
                pil_kwargs={"compression": "tiff_lzw"})
    plt.close(fig)


if __name__ == "__main__":
    main("101")
