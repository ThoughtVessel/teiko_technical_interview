# Teiko Technical Interview

<!-- One or two sentences: what this repo contains and what the assignment was. -->

## Setup and Usage

Everything runs through the `Makefile`. From a fresh Codespace:

```bash
make setup       # install dependencies
make pipeline    # build the database and generate all outputs
make dashboard   # start the dashboard server
```

### Requirements

- Python 3.9 or newer.
- `make setup` installs the packages in `requirements.txt` (`dash`, `plotly`,
  `pandas`). These are needed only by the dashboard.
- The pipeline itself is standard-library only, so `make pipeline` reproduces
  every output file even if `make setup` has not been run.

The `Makefile` invokes `python3`, which exists in Codespaces and on macOS
alike. Override it if your environment differs:

```bash
make pipeline PYTHON=python
```

### Running the pipeline

```bash
make pipeline
```

This runs `load_data.py` followed by `run_analysis.py`, and prints:

```
python3 load_data.py

created cell_count.db
  project          3 rows
  subject      3,500 rows
  sample      10,500 rows
  foreign key check: passed
python3 run_analysis.py
Generating analysis outputs

Part 2  cell frequencies       52,500 rows (10,500 samples x 5 populations)
        -> outputs/cell_frequencies.csv

Done.
```

It produces two things:

| Path | Contents |
| --- | --- |
| `cell_count.db` | SQLite database, in the repository root |
| `outputs/cell_frequencies.csv` | Part 2 summary table, 52,500 rows |

The load is idempotent: every run drops and rebuilds the tables, so repeated
runs are safe and always yield the same database.

### Running the dashboard

```bash
make dashboard
```

The server listens on port **8050**. In Codespaces the port is forwarded
automatically — click **Open in Browser** on the notification, or open the
**Ports** tab and follow the URL for port 8050. Locally, visit
<http://localhost:8050>.

If port 8050 is already taken, choose another:

```bash
PORT=8060 make dashboard
```

Run `make pipeline` first: the dashboard reads from `cell_count.db` and will
show a "Database not found" notice if it is missing.

Use the tabs along the bottom of the screen to move between Parts 2, 3 and 4.

### Running the steps individually

The scripts take no arguments and resolve their own paths, so they can be run
from any working directory:

```bash
python3 load_data.py      # Part 1: create cell_count.db and load the CSV
python3 run_analysis.py   # Parts 2-4: write outputs/
python3 app.py            # dashboard, equivalent to `make dashboard`
```

### Starting over

```bash
make clean
```

Removes `cell_count.db`, `outputs/` and `__pycache__/`. Rerun `make pipeline`
to regenerate them.

## Database Schema

<!-- Diagram or table listing the three tables and their columns. -->

### Design rationale

<!-- Why three tables: project, subject, sample.
     - What functional dependencies were verified against the CSV, and how.
     - Why project is referenced from sample rather than subject.
     - Why response sits on subject (best overall response = one endpoint per patient).
     - Why cell counts are stored wide rather than long, and what that trades away.
     - What the CHECK constraints and the UNIQUE constraint each protect against. -->

### Scaling considerations

<!-- Hundreds of projects, thousands of samples, varied analytics:
     - Where the current design holds up and where it strains first.
     - Indexing strategy for the common query shapes.
     - The wide-vs-long cell count question at scale (adding a sixth population).
     - When to split treatment into its own table (multi-line therapy).
     - When SQLite stops being the right choice, and what replaces it. -->

## Code Structure

| File | Role |
| --- | --- |
| `load_data.py` | Part 1: defines the schema and loads `cell-count.csv` into `cell_count.db` |
| `analysis.py` | Analysis queries; Part 2 is a single SQL statement |
| `run_analysis.py` | Runs each part in turn and writes the results to `outputs/` |
| `app.py` | Dash dashboard, one tab per part |
| `profile_data.py` | Standalone data profiler used to verify the functional dependencies behind the schema |
| `Makefile` | `setup`, `pipeline`, `dashboard`, `clean` targets |
| `requirements.txt` | Dashboard dependencies |

<!-- Add or remove rows as the remaining parts land. -->

### Design decisions

<!-- Why it is laid out this way:
     - Stdlib-only, no dependency install step for the reviewer.
     - Paths resolved from __file__ so it runs from any working directory.
     - Idempotent rebuild rather than incremental load.
     - Separation of read / transform / load, and why that is testable.
     - Part 2 computed in SQL, so the CSV and the dashboard cannot disagree.
     - Pipeline is stdlib-only; only the dashboard needs installed packages.
     - The post-load verification summary and what it proves. -->

## Dashboard

<!-- Link goes here, plus a sentence on what it shows. -->
