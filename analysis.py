#!/usr/bin/env python3
"""Analysis queries against cell_count.db.

Part 2 is implemented here as a single SQL query. Keeping the computation in
SQL rather than in Python means the same logic backs both the generated CSV
and the live dashboard, so the two can never disagree.

Stdlib only, so the pipeline reproduces without installing anything.
"""

import csv
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "cell_count.db"
OUTPUT_DIR = ROOT / "outputs"

POPULATIONS = ["b_cell", "cd8_t_cell", "cd4_t_cell", "nk_cell", "monocyte"]

# Unpivot the five wide count columns into one row per (sample, population).
_UNPIVOT = "\n    UNION ALL ".join(
    f"SELECT sample_id, '{population}' AS population, {population} AS cell_count FROM sample"
    for population in POPULATIONS
)

FREQUENCY_QUERY = f"""
WITH totals AS (
    SELECT sample_id, {' + '.join(POPULATIONS)} AS total_count
    FROM sample
),
per_population AS (
    {_UNPIVOT}
)
SELECT
    p.sample_id                                     AS sample,
    t.total_count                                   AS total_count,
    p.population                                    AS population,
    p.cell_count                                    AS count,
    ROUND(100.0 * p.cell_count / t.total_count, 4)  AS percentage
FROM per_population p
JOIN totals t ON t.sample_id = p.sample_id
ORDER BY p.sample_id, p.population
"""

FREQUENCY_COLUMNS = ["sample", "total_count", "population", "count", "percentage"]


def connect(db_path=DB_PATH):
    if not db_path.exists():
        raise FileNotFoundError(
            f"{db_path.name} not found. Run `python load_data.py` first."
        )
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def cell_frequencies(conn):
    """Part 2: relative frequency of each cell population within each sample.

    Returns one row per (sample, population) as a list of dicts.
    """
    return [dict(row) for row in conn.execute(FREQUENCY_QUERY)]


def write_csv(rows, path, columns):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    return path
