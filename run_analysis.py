#!/usr/bin/env python3
"""Generate every analysis output into outputs/.

Run after load_data.py; `make pipeline` runs both in order.
"""

import analysis


def part2(conn):
    rows = analysis.cell_frequencies(conn)
    path = analysis.write_csv(
        rows, analysis.OUTPUT_DIR / "cell_frequencies.csv", analysis.FREQUENCY_COLUMNS
    )
    samples = len({row["sample"] for row in rows})
    print(f"Part 2  cell frequencies      {len(rows):>7,} rows "
          f"({samples:,} samples x {len(analysis.POPULATIONS)} populations)")
    print(f"        -> {path.relative_to(analysis.ROOT)}")


def main():
    conn = analysis.connect()
    try:
        print("Generating analysis outputs\n")
        part2(conn)
        print("\nDone.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
