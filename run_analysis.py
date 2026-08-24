#!/usr/bin/env python3
"""Generate every analysis output into outputs/.

Run after load_data.py; `make pipeline` runs both in order.
"""

import csv

import matplotlib
matplotlib.use("Agg")  # No display in Codespaces; render straight to file.
import matplotlib.pyplot as plt

import analysis

RESPONDER_BLUE = "#1d4ed8"
NON_RESPONDER_BLUE = "#93c5fd"


def part2(conn):
    rows = analysis.cell_frequencies(conn)
    path = analysis.write_csv(
        rows, analysis.OUTPUT_DIR / "cell_frequencies.csv", analysis.FREQUENCY_COLUMNS
    )
    samples = len({row["sample"] for row in rows})
    print(f"Part 2  cell frequencies      {len(rows):>7,} rows "
          f"({samples:,} samples x {len(analysis.POPULATIONS)} populations)")
    print(f"        -> {path.relative_to(analysis.ROOT)}")


def boxplot(conn, path):
    """Responder vs non-responder relative frequencies, one pair per
    population."""
    rows = analysis.responder_frequencies(conn)
    grouped = {p: {"yes": [], "no": []} for p in analysis.POPULATIONS}
    for row in rows:
        grouped[row["population"]][row["response"]].append(row["percentage"])

    figure, axes = plt.subplots(figsize=(11, 6))
    positions, labels = [], []
    for index, population in enumerate(analysis.POPULATIONS):
        left, right = index * 3, index * 3 + 1
        for offset, response, colour in (
            (left, "yes", RESPONDER_BLUE),
            (right, "no", NON_RESPONDER_BLUE),
        ):
            axes.boxplot(
                grouped[population][response], positions=[offset], widths=0.8,
                patch_artist=True, showfliers=False,
                boxprops={"facecolor": colour, "edgecolor": "#0b2545"},
                medianprops={"color": "#0b2545", "linewidth": 2},
                whiskerprops={"color": "#0b2545"}, capprops={"color": "#0b2545"},
            )
        positions.append(left + 0.5)
        labels.append(population)

    axes.set_xticks(positions)
    axes.set_xticklabels(labels)
    axes.set_ylabel("Relative frequency (%)")
    axes.set_title("Cell population frequencies: responders vs non-responders\n"
                   "Melanoma patients on miraclib, PBMC samples", fontsize=12)
    axes.legend(
        handles=[
            plt.Rectangle((0, 0), 1, 1, facecolor=RESPONDER_BLUE, edgecolor="#0b2545"),
            plt.Rectangle((0, 0), 1, 1, facecolor=NON_RESPONDER_BLUE, edgecolor="#0b2545"),
        ],
        labels=["Responder", "Non-responder"], frameon=False,
    )
    axes.spines[["top", "right"]].set_visible(False)
    axes.grid(axis="y", alpha=0.3)
    figure.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=150)
    plt.close(figure)
    return path


def part3(conn):
    results, meta = analysis.compare_responders(conn)
    stats_path = analysis.write_csv(
        results, analysis.OUTPUT_DIR / "part3_responder_stats.csv",
        analysis.COMPARISON_COLUMNS,
    )
    baseline, _ = analysis.compare_responders(conn, baseline_only=True)
    baseline_path = analysis.write_csv(
        baseline, analysis.OUTPUT_DIR / "part3_responder_stats_baseline.csv",
        analysis.COMPARISON_COLUMNS,
    )
    plot_path = boxplot(conn, analysis.OUTPUT_DIR / "part3_boxplot.png")

    significant = [r["population"] for r in results if r["significant"] == "yes"]
    print(f"\nPart 3  responder comparison  {meta['n_samples']:,} PBMC samples "
          f"({meta['n_responder_subjects']} responder / "
          f"{meta['n_non_responder_subjects']} non-responder subjects)")
    for result in results:
        print(f"        {result['population']:<11} "
              f"median {result['median_responder']:>6.2f}% vs "
              f"{result['median_non_responder']:>6.2f}%  "
              f"p={result['p_value']:.4f}  q={result['p_value_adjusted']:.4f}  "
              f"{'SIGNIFICANT' if result['significant'] == 'yes' else ''}")
    print(f"        significant after correction: "
          f"{', '.join(significant) if significant else 'none'}")
    for path in (stats_path, baseline_path, plot_path):
        print(f"        -> {path.relative_to(analysis.ROOT)}")


def part4(conn):
    samples = analysis.baseline_samples(conn)
    samples_path = analysis.write_csv(
        samples, analysis.OUTPUT_DIR / "part4_baseline_samples.csv",
        analysis.BASELINE_COLUMNS,
    )

    breakdowns = analysis.baseline_breakdowns(conn)
    summary_rows = [
        {"breakdown": name, "category": entry["category"], "count": entry["count"]}
        for name, entries in breakdowns.items()
        for entry in entries
    ]
    summary_path = analysis.write_csv(
        summary_rows, analysis.OUTPUT_DIR / "part4_summary.csv",
        ["breakdown", "category", "count"],
    )

    b_cell = analysis.male_melanoma_baseline_b_cell(conn)
    b_cell_path = analysis.write_csv(
        [b_cell], analysis.OUTPUT_DIR / "part4_b_cell_average.csv",
        ["n_samples", "n_subjects", "average_b_cell"],
    )

    print(f"\nPart 4  baseline subset       {len(samples):,} melanoma PBMC samples "
          f"at day 0 on miraclib")
    for name, entries in breakdowns.items():
        joined = ", ".join(f"{e['category']}: {e['count']:,}" for e in entries)
        print(f"        {name.replace('_', ' '):<22} {joined}")
    print(f"        average b_cell for male melanoma responders at day 0: "
          f"{b_cell['average_b_cell']:.2f} (n={b_cell['n_samples']:,} samples)")
    for path in (samples_path, summary_path, b_cell_path):
        print(f"        -> {path.relative_to(analysis.ROOT)}")


def main():
    conn = analysis.connect()
    try:
        print("Generating analysis outputs\n")
        part2(conn)
        part3(conn)
        part4(conn)
        print("\nDone.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
