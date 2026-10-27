"""Validate a historical-posts CSV before importing it.

Usage:
    python ml/scripts/validate_dataset.py [csv]
"""

import os
import sys

import pandas as pd

REQUIRED = ["platform", "published_at", "views"]
KNOWN = {
    "post_id", "platform", "published_at", "content_type", "duration_seconds",
    "views", "likes", "comments", "shares", "impressions", "followers_at_publish",
    "caption", "title", "hashtags", "content_category",
}


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else "ml/data/sample_history.csv"
    if not os.path.exists(path):
        print(f"File not found: {path}")
        return 2

    df = pd.read_csv(path)
    problems: list[str] = []

    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        problems.append(f"Missing required column(s): {', '.join(missing)}")

    if df.empty:
        problems.append("The file has no data rows")

    unknown = [c for c in df.columns if c not in KNOWN]
    if unknown:
        print(f"Note: unrecognised column(s) will be ignored: {', '.join(unknown)}")

    if "platform" in df.columns:
        bad_platform = df[~df["platform"].astype(str).str.lower().isin(["instagram", "youtube"])]
        if len(bad_platform):
            problems.append(f"{len(bad_platform)} row(s) have a platform other than instagram/youtube")

    if "published_at" in df.columns:
        parsed = pd.to_datetime(df["published_at"], errors="coerce", utc=True)
        unparseable = int(parsed.isna().sum())
        if unparseable:
            problems.append(f"{unparseable} row(s) have an unparseable published_at")

    if "views" in df.columns:
        views = pd.to_numeric(df["views"], errors="coerce")
        if int(views.isna().sum()):
            problems.append(f"{int(views.isna().sum())} row(s) have a non-numeric views value")
        if int((views < 0).sum()):
            problems.append(f"{int((views < 0).sum())} row(s) have negative views")

    print(f"Rows: {len(df)}")
    print(f"Columns: {', '.join(map(str, df.columns))}")
    print("\nMissing values per column:")
    print(df.isna().sum().to_string())

    if problems:
        print("\nProblems:")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    print("\nNo blocking problems found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
