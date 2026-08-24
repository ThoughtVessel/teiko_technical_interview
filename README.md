# Teiko Technical Interview

Analysis of immune cell population counts from a clinical trial dataset:
a SQLite schema and loader, the frequency and statistical analyses, and an
interactive dashboard presenting the results.

## Setup and Usage

Everything runs through the `Makefile`. From a fresh Codespace:

```bash
make setup       # install dependencies
make pipeline    # build the database and generate all outputs
make dashboard   # start the dashboard server
```

### Requirements

- Python 3.9 or newer.
- `make setup` installs the packages in `requirements.txt`: `scipy` and
  `matplotlib` for the Part 3 statistics and boxplot, and `dash`, `plotly` and
  `pandas` for the dashboard.
- Run `make setup` before `make pipeline`. Parts 1 and 2 need only the standard
  library, but Part 3 does not.

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
| `outputs/cell_frequencies.csv` | Part 2: frequency summary table, 52,500 rows |
| `outputs/part3_responder_stats.csv` | Part 3: per-population test results |
| `outputs/part3_responder_stats_baseline.csv` | Part 3: baseline-only sensitivity analysis |
| `outputs/part3_boxplot.png` | Part 3: responder vs non-responder boxplot |
| `outputs/part4_baseline_samples.csv` | Part 4: the 656 filtered baseline samples |
| `outputs/part4_summary.csv` | Part 4: project, response and sex breakdowns |
| `outputs/part4_b_cell_average.csv` | Part 4: average B cell count answer |

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

Three tables, defined in `load_data.py`:

```
project                subject                        sample
-------                -------                        ------
project_id (PK)        subject_id (PK)                sample_id (PK)
                       condition                      subject_id (FK -> subject)
                       age                            project_id (FK -> project)
                       sex                            sample_type
                       treatment                      time_from_treatment_start
                       response                       b_cell
                                                      cd8_t_cell
                                                      cd4_t_cell
                                                      nk_cell
                                                      monocyte
```

| Table | Rows | Grain |
| --- | --- | --- |
| `project` | 3 | one study |
| `subject` | 3,500 | one patient |
| `sample` | 10,500 | one specimen |

### Design rationale

**The split is driven by verified functional dependencies, not by eye.**
Before writing any DDL, `profile_data.py` checked every candidate dependency
against all 10,500 rows. `subject` determines `condition`, `age`, `sex`,
`treatment` and `response` with zero violations, so those columns move to a
`subject` table without losing information. In the flat CSV they are
transitively dependent on the key (`sample -> subject -> sex`), which is a
2NF violation; splitting them out brings the model to 3NF.

**A dependency that holds is not always one worth modelling.** `subject` also
determines `sample_type` in this dataset — every patient's three specimens are
all PBMC or all whole blood. That is an artefact of how the data was generated,
not a clinical fact: PBMC versus whole blood is a property of the specimen and
the assay, and drawing both from one patient must not break the schema. It
stays on `sample` deliberately. Functional dependency tests describe the
snapshot in front of you, not the domain.

**`project` is referenced from `sample`.** A project is a data collection
effort, so it attaches naturally to the specimen. Hanging it off `subject`
instead would assert that a patient belongs to exactly one study forever;
referencing it from `sample` leaves room for a patient enrolled in a second
study later.

**`response` sits on `subject` as a best overall response** — one trial
endpoint per patient, NULL for the 474 untreated subjects. The alternative
reading is that response is assessed per visit and can change between them, in
which case it belongs on `sample`. The data cannot distinguish the two: response
is constant within every subject here. The endpoint reading was chosen because
it keeps `treatment` and `response` together, and because a per-visit column on
`sample` would be partially dependent on the `(subject, timepoint)` candidate
key and could store contradictory values for two specimens drawn on the same day.

**Cell counts are stored wide**, as five columns on `sample`. This keeps the
model at three tables and mirrors the source file. It is the design's weakest
point: see below.

**Constraints encode what was verified.** `CHECK` constraints pin the
categorical vocabularies, and `UNIQUE (subject_id, sample_type,
time_from_treatment_start)` rejects duplicate specimens — a constraint that was
confirmed to hold across all 10,500 rows before being declared.

### Scaling considerations

**What holds up.** The three-table split scales cleanly in the row dimension.
`sample` grows linearly, `subject` and `project` stay small, and the foreign
keys keep joins cheap. Indexes already exist on `subject_id`, `project_id` and
`time_from_treatment_start`, which cover the cohort filters every analysis here
performs. At hundreds of projects and hundreds of thousands of samples, a
composite index on the common filter shape — condition, treatment, sample type,
timepoint — would be the next addition.

**What strains first: the wide cell count columns.** Adding a sixth population
means an `ALTER TABLE`, a schema migration, a loader change and an edit to every
query that names the five columns. A long `cell_count(sample_id, population,
count)` table would make that an `INSERT`, let panels differ between projects,
and turn the frequency query into a `GROUP BY` instead of five hand-written
column references. With hundreds of projects running different panels, the wide
form stops working: projects would need columns they do not measure. The long
form is the first change to make.

**Second: treatment.** `treatment` on `subject` asserts one therapy per patient
for all time. Second-line therapy or a crossover arm breaks it. The fix is a
`treatment_episode` table between subject and sample, carrying the drug,
the response endpoint and the treatment start date that
`time_from_treatment_start` is measured against. It is declined here because it
buys nothing against this dataset, where every subject has exactly one drug.

**Third: the categorical `CHECK` constraints.** Hardcoded drug and condition
vocabularies catch typos at load time, but a fourth drug means a migration. At
scale they become lookup tables with foreign keys.

**When SQLite stops being right.** SQLite is a good fit here: a single-writer,
read-mostly analytical dataset that a grader can rebuild in seconds with no
server. It stops fitting when several projects need to load concurrently, since
SQLite serialises writers. At that point Postgres is the natural move. If the
workload stays analytical but the row count grows past tens of millions, a
columnar engine such as DuckDB would serve the aggregate-heavy queries better
than either, while keeping the same SQL.

## Code Structure

| File | Role |
| --- | --- |
| `load_data.py` | Part 1: defines the schema and loads `cell-count.csv` into `cell_count.db` |
| `analysis.py` | Queries and statistics for Parts 2-4 |
| `run_analysis.py` | Runs each part in turn and writes results and plots to `outputs/` |
| `app.py` | Dash dashboard, one tab per part |
| `profile_data.py` | Standalone data profiler used to verify the functional dependencies behind the schema |
| `Makefile` | `setup`, `pipeline`, `dashboard`, `clean` targets |
| `requirements.txt` | Dashboard dependencies |

<!-- Add or remove rows as the remaining parts land. -->

### Design decisions

**Data and presentation are separated.** `analysis.py` returns plain Python
data structures and knows nothing about files, figures or HTML. `run_analysis.py`
writes CSVs and renders the boxplot; `app.py` renders the dashboard. Both
consume the same functions, so the generated files and the dashboard cannot
report different numbers — a class of bug that is otherwise easy to ship and
hard to notice.

**Filtering and aggregation live in SQL.** The database is the single definition
of each cohort. Only the hypothesis tests are done in Python, where SQLite has
nothing useful to offer.

**Scripts take no arguments and resolve their own paths** from `__file__`, so
they behave identically whether run by `make`, by a grader, or from another
directory.

**The load is idempotent.** Every run drops and rebuilds the tables rather than
appending, so re-running is always safe and the database is a pure function of
the CSV.

**The loader verifies itself.** After loading it prints per-table row counts and
runs `PRAGMA foreign_key_check`, so a failed or partial load is visible
immediately rather than surfacing later as a confusing analysis result.

## Dashboard

<!-- If deploying publicly, put the link here. -->

Run locally with `make dashboard`, then open port 8050.

The dashboard has one tab per part, selected from the bar along the bottom of
the screen:

- **Part 2** — every sample and population, sortable and paginated, with a
  search box that filters by sample ID.
- **Part 3** — the responder comparison: cohort size, an interactive boxplot,
  the full test results, and a plain statement of what is and is not
  significant.
- **Part 4** — the baseline cohort with its project, response and sex
  breakdowns, the average B cell count, and the underlying sample list.
