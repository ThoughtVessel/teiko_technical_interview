#!/usr/bin/env python3
"""Initialize the SQLite database and load cell-count.csv into it.

Run with no arguments from anywhere:

    python load_data.py

Creates cell_count.db in the repository root. Re-running rebuilds the tables
from scratch, so the load is idempotent.

Schema (3 tables):
    project  - one row per study; referenced by sample
    subject  - one row per patient, including their treatment and response
    sample   - one row per specimen, with its five cell-population counts
"""

import csv
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CSV_PATH = ROOT / "cell-count.csv"
DB_PATH = ROOT / "cell_count.db"

CELL_POPULATIONS = ["b_cell", "cd8_t_cell", "cd4_t_cell", "nk_cell", "monocyte"]

SCHEMA = """
DROP TABLE IF EXISTS sample;
DROP TABLE IF EXISTS subject;
DROP TABLE IF EXISTS project;

CREATE TABLE project (
    project_id TEXT PRIMARY KEY
);

CREATE TABLE subject (
    subject_id TEXT    PRIMARY KEY,
    condition  TEXT    NOT NULL CHECK (condition IN ('melanoma', 'carcinoma', 'healthy')),
    age        INTEGER NOT NULL CHECK (age BETWEEN 0 AND 120),
    sex        TEXT    NOT NULL CHECK (sex IN ('M', 'F')),
    treatment  TEXT    NOT NULL CHECK (treatment IN ('miraclib', 'phauximab', 'none')),
    response   TEXT             CHECK (response IN ('yes', 'no'))
);

CREATE TABLE sample (
    sample_id                 TEXT    PRIMARY KEY,
    subject_id                TEXT    NOT NULL REFERENCES subject(subject_id),
    project_id                TEXT    NOT NULL REFERENCES project(project_id),
    sample_type               TEXT    NOT NULL CHECK (sample_type IN ('PBMC', 'WB')),
    time_from_treatment_start INTEGER NOT NULL CHECK (time_from_treatment_start >= 0),
    b_cell                    INTEGER NOT NULL CHECK (b_cell >= 0),
    cd8_t_cell                INTEGER NOT NULL CHECK (cd8_t_cell >= 0),
    cd4_t_cell                INTEGER NOT NULL CHECK (cd4_t_cell >= 0),
    nk_cell                   INTEGER NOT NULL CHECK (nk_cell >= 0),
    monocyte                  INTEGER NOT NULL CHECK (monocyte >= 0),
    -- A subject is sampled at most once per specimen type per timepoint.
    UNIQUE (subject_id, sample_type, time_from_treatment_start)
);

CREATE INDEX idx_sample_subject ON sample(subject_id);
CREATE INDEX idx_sample_project ON sample(project_id);
CREATE INDEX idx_sample_timepoint ON sample(time_from_treatment_start);
"""


def blank_to_none(value):
    """Empty CSV cells become SQL NULL rather than the empty string."""
    value = value.strip()
    return value if value else None


def read_csv(path):
    if not path.exists():
        sys.exit(f"error: {path.name} not found in {path.parent}")
    with open(path, newline="") as fh:
        return list(csv.DictReader(fh))


def collect(rows):
    """Split the flat rows into the three tables, de-duplicating as we go.

    dict keys preserve insertion order, so projects and subjects load in the
    order they first appear in the CSV.
    """
    projects = {}
    subjects = {}
    samples = []

    for row in rows:
        projects[row["project"]] = (row["project"],)

        subjects[row["subject"]] = (
            row["subject"],
            row["condition"],
            int(row["age"]),
            row["sex"],
            row["treatment"],
            blank_to_none(row["response"]),
        )

        samples.append((
            row["sample"],
            row["subject"],
            row["project"],
            row["sample_type"],
            int(row["time_from_treatment_start"]),
            *(int(row[population]) for population in CELL_POPULATIONS),
        ))

    return list(projects.values()), list(subjects.values()), samples


def load(conn, projects, subjects, samples):
    conn.executemany("INSERT INTO project VALUES (?)", projects)
    conn.executemany("INSERT INTO subject VALUES (?, ?, ?, ?, ?, ?)", subjects)
    conn.executemany(
        f"INSERT INTO sample VALUES ({', '.join('?' * 10)})", samples
    )


def summarize(conn):
    print(f"\ncreated {DB_PATH.name}")
    for table in ("project", "subject", "sample"):
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table:<10} {count:>7,} rows")

    orphans = conn.execute("PRAGMA foreign_key_check").fetchall()
    print(f"  foreign key check: {'passed' if not orphans else f'{len(orphans)} orphaned rows'}")


def main():
    rows = read_csv(CSV_PATH)
    projects, subjects, samples = collect(rows)

    conn = sqlite3.connect(DB_PATH)
    try:
        # Must be set outside a transaction, so before the DDL runs.
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(SCHEMA)
        with conn:
            load(conn, projects, subjects, samples)
        summarize(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
