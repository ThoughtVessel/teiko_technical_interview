#!/usr/bin/env python3
"""Analysis queries against cell_count.db.

Filtering and aggregation stay in SQL so that the same logic backs both the
generated CSV files and the live dashboard, and the two can never disagree.
Only the hypothesis tests in Part 3 are done in Python, where SQLite has
nothing to offer.
"""

import csv
import sqlite3
import statistics
from pathlib import Path

from scipy import stats

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


# --- Part 3: responders vs non-responders --------------------------------
#
# Melanoma patients on miraclib, PBMC samples only. Subjects contribute three
# samples each, so see the note on independence in compare_responders().

RESPONDER_COHORT = """
    u.condition = 'melanoma'
    AND u.treatment = 'miraclib'
    AND s.sample_type = 'PBMC'
    AND u.response IN ('yes', 'no')
"""

RESPONDER_FREQUENCY_QUERY = f"""
WITH cohort AS (
    SELECT s.sample_id, s.subject_id, u.response,
           s.time_from_treatment_start,
           {' + '.join(f's.{p}' for p in POPULATIONS)} AS total_count,
           {', '.join(f's.{p}' for p in POPULATIONS)}
    FROM sample s
    JOIN subject u ON u.subject_id = s.subject_id
    WHERE {RESPONDER_COHORT}
      {{extra_filter}}
)
{{unpivot}}
ORDER BY sample_id, population
"""


def _cohort_unpivot():
    return "\n    UNION ALL ".join(
        f"""SELECT sample_id, subject_id, response, time_from_treatment_start,
           '{p}' AS population,
           ROUND(100.0 * {p} / total_count, 4) AS percentage
    FROM cohort"""
        for p in POPULATIONS
    )


def responder_frequencies(conn, baseline_only=False):
    """Relative frequencies for the Part 3 cohort, one row per sample and
    population."""
    # The filter belongs in the cohort CTE: a WHERE appended after a UNION ALL
    # chain would bind to the final SELECT only, silently filtering one
    # population out of five.
    query = RESPONDER_FREQUENCY_QUERY.format(
        unpivot=_cohort_unpivot(),
        extra_filter="AND s.time_from_treatment_start = 0" if baseline_only else "",
    )
    return [dict(row) for row in conn.execute(query)]


def benjamini_hochberg(pvalues):
    """Return BH-adjusted p-values (q-values), controlling the false discovery
    rate across the five populations tested."""
    n = len(pvalues)
    ordered = sorted(range(n), key=lambda i: pvalues[i])
    adjusted = [0.0] * n
    previous = 1.0
    for rank, index in enumerate(reversed(ordered), start=1):
        value = pvalues[index] * n / (n - rank + 1)
        previous = min(previous, value, 1.0)
        adjusted[index] = previous
    return adjusted


def compare_responders(conn, baseline_only=False, alpha=0.05):
    """Test each population for a difference in relative frequency between
    responders and non-responders.

    Mann-Whitney U, two-sided: the frequencies are bounded percentages with no
    guarantee of normality, so a rank test is the safer choice over a t-test.
    Reported alongside a rank-biserial effect size, since with these group
    sizes a tiny difference can still clear significance.

    p-values are corrected across the five populations with Benjamini-Hochberg.

    Note on independence: each subject contributes three samples (day 0, 7 and
    14), so samples within a subject are correlated and the test's independence
    assumption is not strictly met. Pass baseline_only=True for the day-0
    sensitivity analysis, where every subject appears exactly once.
    """
    rows = responder_frequencies(conn, baseline_only=baseline_only)

    grouped = {population: {"yes": [], "no": []} for population in POPULATIONS}
    subjects = {"yes": set(), "no": set()}
    for row in rows:
        grouped[row["population"]][row["response"]].append(row["percentage"])
        subjects[row["response"]].add(row["subject_id"])

    results = []
    for population in POPULATIONS:
        responders = grouped[population]["yes"]
        non_responders = grouped[population]["no"]
        test = stats.mannwhitneyu(responders, non_responders, alternative="two-sided")
        # Rank-biserial correlation: 0 means no separation, +/-1 complete.
        effect = 2 * test.statistic / (len(responders) * len(non_responders)) - 1
        results.append({
            "population": population,
            "n_responder_samples": len(responders),
            "n_non_responder_samples": len(non_responders),
            "median_responder": round(statistics.median(responders), 4),
            "median_non_responder": round(statistics.median(non_responders), 4),
            "median_difference": round(
                statistics.median(responders) - statistics.median(non_responders), 4
            ),
            "mean_responder": round(statistics.fmean(responders), 4),
            "mean_non_responder": round(statistics.fmean(non_responders), 4),
            "u_statistic": test.statistic,
            "p_value": test.pvalue,
            "rank_biserial": round(effect, 4),
        })

    for result, q in zip(results, benjamini_hochberg([r["p_value"] for r in results])):
        result["p_value_adjusted"] = q
        result["significant"] = "yes" if q < alpha else "no"

    return results, {
        "n_responder_subjects": len(subjects["yes"]),
        "n_non_responder_subjects": len(subjects["no"]),
        "n_samples": len(rows) // len(POPULATIONS),
    }


COMPARISON_COLUMNS = [
    "population", "n_responder_samples", "n_non_responder_samples",
    "median_responder", "median_non_responder", "median_difference",
    "mean_responder", "mean_non_responder", "u_statistic",
    "p_value", "p_value_adjusted", "rank_biserial", "significant",
]


# --- Part 4: baseline subset ---------------------------------------------

BASELINE_COHORT = """
    u.condition = 'melanoma'
    AND u.treatment = 'miraclib'
    AND s.sample_type = 'PBMC'
    AND s.time_from_treatment_start = 0
"""

BASELINE_SAMPLES_QUERY = f"""
SELECT s.sample_id AS sample, s.project_id AS project, s.subject_id AS subject,
       u.condition, u.age, u.sex, u.treatment, u.response,
       s.sample_type, s.time_from_treatment_start,
       {', '.join(f's.{p}' for p in POPULATIONS)}
FROM sample s
JOIN subject u ON u.subject_id = s.subject_id
WHERE {BASELINE_COHORT}
ORDER BY s.sample_id
"""

BASELINE_COLUMNS = [
    "sample", "project", "subject", "condition", "age", "sex", "treatment",
    "response", "sample_type", "time_from_treatment_start", *POPULATIONS,
]


def baseline_samples(conn):
    """Part 4: melanoma PBMC samples at baseline from miraclib-treated
    patients."""
    return [dict(row) for row in conn.execute(BASELINE_SAMPLES_QUERY)]


def _baseline_breakdown(conn, column, count_subjects):
    """Counts within the baseline cohort, grouped by one column.

    Samples are counted for projects and subjects for the demographic splits,
    matching how each question is posed.
    """
    measure = "COUNT(DISTINCT s.subject_id)" if count_subjects else "COUNT(*)"
    return [
        dict(row)
        for row in conn.execute(f"""
            SELECT {column} AS category, {measure} AS count
            FROM sample s
            JOIN subject u ON u.subject_id = s.subject_id
            WHERE {BASELINE_COHORT}
            GROUP BY category
            ORDER BY category
        """)
    ]


def baseline_breakdowns(conn):
    return {
        "samples_per_project": _baseline_breakdown(conn, "s.project_id", False),
        "subjects_by_response": _baseline_breakdown(conn, "u.response", True),
        "subjects_by_sex": _baseline_breakdown(conn, "u.sex", True),
    }


MALE_MELANOMA_B_CELL_QUERY = """
SELECT COUNT(*) AS n_samples,
       COUNT(DISTINCT s.subject_id) AS n_subjects,
       ROUND(AVG(s.b_cell), 2) AS average_b_cell
FROM sample s
JOIN subject u ON u.subject_id = s.subject_id
WHERE u.condition = 'melanoma'
  AND u.sex = 'M'
  AND u.response = 'yes'
  AND s.time_from_treatment_start = 0
"""


def male_melanoma_baseline_b_cell(conn):
    """Average B cell count for male melanoma responders at baseline.

    Deliberately not restricted by sample type or treatment: the question asks
    for males "of all sample and treatment types", unlike the cohort above.
    """
    return dict(conn.execute(MALE_MELANOMA_B_CELL_QUERY).fetchone())
