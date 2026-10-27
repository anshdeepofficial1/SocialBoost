"""Import a CSV of historical posts and train the workspace model.

Usage:
    python ml/scripts/train_models.py [csv] [--workspace <id>]

Without ``--workspace`` the first workspace in the database is used, which is
what the local demo account resolves to. The CSV must contain at least the
``platform``, ``published_at`` and ``views`` columns.
"""

import argparse
import os
import sys

import pandas as pd

BASE = os.path.join(os.path.dirname(__file__), "..", "..")
sys.path.insert(0, os.path.join(BASE, "backend"))

from app import models  # noqa: E402,F401
from app.db.schema import ensure_schema  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.calendar import HistoricalPost  # noqa: E402
from app.models.user import User, Workspace  # noqa: E402
from app.services.ml_service import train_models  # noqa: E402

REQUIRED = {"platform", "published_at", "views"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", nargs="?", default=os.path.join(BASE, "ml", "data", "sample_history.csv"))
    parser.add_argument("--workspace", default=None, help="Workspace id to import into")
    args = parser.parse_args()

    ensure_schema()
    df = pd.read_csv(args.csv)

    missing = REQUIRED - set(df.columns)
    if missing:
        print(f"CSV is missing required column(s): {', '.join(sorted(missing))}")
        return 2

    db = SessionLocal()
    try:
        if args.workspace:
            workspace = db.query(Workspace).filter(Workspace.id == args.workspace).first()
            if not workspace:
                print(f"No workspace with id {args.workspace}")
                return 2
        else:
            workspace = db.query(Workspace).first()
            if not workspace:
                user = User(email="demo@local", hashed_password="x")
                db.add(user)
                db.commit()
                db.refresh(user)
                workspace = Workspace(owner_id=user.id, name="Demo")
                db.add(workspace)
                db.commit()
                db.refresh(workspace)

        imported = 0
        for _, row in df.iterrows():
            platform = str(row.get("platform", "")).strip().lower()
            if platform not in ("instagram", "youtube"):
                continue
            published = pd.to_datetime(row.get("published_at"), errors="coerce", utc=True)
            if pd.isna(published):
                continue

            db.add(HistoricalPost(
                workspace_id=workspace.id,
                post_id=str(row.get("post_id", "") or ""),
                platform=platform,
                published_at=published.to_pydatetime().replace(tzinfo=None),
                content_type=str(row.get("content_type", "short") or "short"),
                duration_seconds=float(row.get("duration_seconds", 0) or 0),
                views=int(float(row.get("views", 0) or 0)),
                likes=int(float(row.get("likes", 0) or 0)),
                comments=int(float(row.get("comments", 0) or 0)),
                shares=int(float(row.get("shares", 0) or 0)),
                impressions=int(float(row.get("impressions", 0) or 0)),
                followers_at_publish=int(float(row.get("followers_at_publish", 0) or 0)),
                caption=str(row.get("caption", "") or ""),
                title=str(row.get("title", "") or ""),
                hashtags=str(row.get("hashtags", "") or ""),
                content_category=str(row.get("content_category", "") or ""),
            ))
            imported += 1
        db.commit()

        print(f"Imported {imported} row(s) into workspace {workspace.id}")
        print(train_models(db, workspace.id))
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
