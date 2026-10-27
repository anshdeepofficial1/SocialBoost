"""Score a hypothetical post with a workspace model.

Usage:
    python ml/scripts/predict.py [--workspace <id>] [--platform instagram|youtube]
                                 [--duration 15] [--caption "..."] [--hashtags "#a #b"]
"""

import argparse
import json
import os
import sys

BASE = os.path.join(os.path.dirname(__file__), "..", "..")
sys.path.insert(0, os.path.join(BASE, "backend"))

from app import models  # noqa: E402,F401
from app.db.schema import ensure_schema  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.user import Workspace  # noqa: E402
from app.services.ml_service import predict  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", default=None)
    parser.add_argument("--platform", default="instagram", choices=["instagram", "youtube"])
    parser.add_argument("--duration", type=float, default=15.0)
    parser.add_argument("--caption", default="")
    parser.add_argument("--title", default="")
    parser.add_argument("--hashtags", default="")
    args = parser.parse_args()

    ensure_schema()
    db = SessionLocal()
    try:
        if args.workspace:
            workspace = db.query(Workspace).filter(Workspace.id == args.workspace).first()
        else:
            workspace = db.query(Workspace).first()
        if not workspace:
            print("No workspace found. Run train_models.py first.")
            return 2

        features = {
            "duration_seconds": args.duration,
            "caption": args.caption,
            "title": args.title,
            "hashtags": args.hashtags,
        }
        result = predict(features, args.platform, db, workspace.id)
        print(json.dumps(result, indent=2, default=str))
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
