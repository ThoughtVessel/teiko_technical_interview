#!/usr/bin/env python3
"""Profile cell-count.csv: per-column statistics, key/dependency checks, and
per-sample cell-population frequencies.

Usage:  python3 profile_data.py [path/to/cell-count.csv]
"""

import csv
import statistics
import sys
from collections import Counter, defaultdict

CELL_POPULATIONS = ["b_cell", "cd8_t_cell", "cd4_t_cell", "nk_cell", "monocyte"]
MAX_CATEGORIES_SHOWN = 12


def load(path):
    with open(path, newline="") as fh:
        return list(csv.DictReader(fh))


def as_number(value):
    """Return value as int/float, or None if it isn't numeric."""
    try:
        return int(value)
    except ValueError:
        try:
            return float(value)
        except ValueError:
            return None


def is_numeric_column(values):
    present = [v for v in values if v != ""]
    return bool(present) and all(as_number(v) is not None for v in present)


def rule(title):
    print(f"\n{'=' * 72}\n{title}\n{'=' * 72}")


def profile_numeric(name, values):
    nums = sorted(as_number(v) for v in values if v != "")
    missing = len(values) - len(nums)
    q1, median, q3 = (
        statistics.quantiles(nums, n=4) if len(nums) > 1 else (nums[0],) * 3
    )
    print(f"\n{name}  [numeric]")
    print(f"  count {len(nums):>10,}   missing {missing:>6,}   distinct {len(set(nums)):>7,}")
    print(f"  min   {nums[0]:>10,.2f}   q1      {q1:>10,.2f}   median {median:>10,.2f}")
    print(f"  max   {nums[-1]:>10,.2f}   q3      {q3:>10,.2f}   iqr    {q3 - q1:>10,.2f}")
    print(f"  mean  {statistics.fmean(nums):>10,.2f}   stdev   "
          f"{statistics.pstdev(nums) if len(nums) > 1 else 0:>10,.2f}   sum    {sum(nums):>10,}")


def profile_categorical(name, values):
    counts = Counter(values)
    missing = counts.pop("", 0)
    total = len(values)
    print(f"\n{name}  [categorical]")
    print(f"  count {total - missing:>10,}   missing {missing:>6,}   distinct {len(counts):>7,}")
    if len(counts) > MAX_CATEGORIES_SHOWN:
        # High-cardinality identifier column: a value listing tells you nothing.
        repeats = Counter(counts.values())
        print("    (identifier-like; value counts omitted) rows per value: "
              + ", ".join(f"{v}x{n:,}" for v, n in sorted(repeats.items())))
        return
    shown = counts.most_common(MAX_CATEGORIES_SHOWN)
    for value, n in shown:
        bar = "#" * round(40 * n / total)
        print(f"    {value[:28]:<28} {n:>7,}  {n / total:>6.1%}  {bar}")
    if len(counts) > len(shown):
        print(f"    ... and {len(counts) - len(shown):,} more values")


def functional_dependency(rows, determinant, dependents):
    """Report whether determinant -> each dependent holds across all rows."""
    grouped = defaultdict(lambda: defaultdict(set))
    for row in rows:
        for dep in dependents:
            grouped[row[determinant]][dep].add(row[dep])
    for dep in dependents:
        violations = {k: v[dep] for k, v in grouped.items() if len(v[dep]) > 1}
        if violations:
            key, seen = next(iter(violations.items()))
            print(f"  {determinant} -> {dep:<28} VIOLATED by {len(violations):,} "
                  f"key(s), e.g. {key}: {sorted(seen)[:4]}")
        else:
            print(f"  {determinant} -> {dep:<28} holds")


def profile_frequencies(rows):
    """Per-sample relative frequency of each cell population."""
    totals = []
    per_population = defaultdict(list)
    for row in rows:
        counts = {p: as_number(row[p]) for p in CELL_POPULATIONS}
        total = sum(counts.values())
        totals.append(total)
        for population, n in counts.items():
            per_population[population].append(n / total if total else 0.0)

    print(f"\ntotal cells per sample: min {min(totals):,}  median "
          f"{statistics.median(totals):,.0f}  max {max(totals):,}")
    print(f"\n  {'population':<14}{'mean %':>9}{'median %':>10}{'min %':>9}{'max %':>9}")
    for population in CELL_POPULATIONS:
        fractions = per_population[population]
        print(f"  {population:<14}{statistics.fmean(fractions):>8.2%}"
              f"{statistics.median(fractions):>10.2%}"
              f"{min(fractions):>9.2%}{max(fractions):>9.2%}")


def main(path):
    rows = load(path)
    columns = list(rows[0].keys())
    print(f"{path}: {len(rows):,} rows x {len(columns)} columns")

    rule("COLUMN STATISTICS")
    for column in columns:
        values = [row[column] for row in rows]
        if is_numeric_column(values):
            profile_numeric(column, values)
        else:
            profile_categorical(column, values)

    rule("KEYS & FUNCTIONAL DEPENDENCIES")
    for column in columns:
        if len({row[column] for row in rows}) == len(rows):
            print(f"  candidate key: {column}")
    print()
    functional_dependency(
        rows, "subject",
        ["project", "condition", "age", "sex", "treatment", "response"],
    )

    rule("CELL POPULATION FREQUENCIES")
    profile_frequencies(rows)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "cell-count.csv")
