"""Print the metrics stored with each trained model artifact.

Usage:
    python ml/scripts/evaluate_models.py [--workspace <id>]
"""

import argparse
import json
import os
import sys

BASE = os.path.join(os.path.dirname(__file__), "..", "..")
sys.path.insert(0, os.path.join(BASE, "backend"))

from app import models  # noqa: E402,F401
from app.core.config import settings  # noqa: E402
from app.db.schema import ensure_schema  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.user import Workspace  # noqa: E402
from app.services.ml_service import model_status  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", default=None)
    args = parser.parse_args()

    ensure_schema()
    print(f"Artifact directory: {settings.MODEL_DIR}")

    db = SessionLocal()
    try:
        workspaces = (
            [db.query(Workspace).filter(Workspace.id == args.workspace).first()]
            if args.workspace
            else db.query(Workspace).all()
        )
        workspaces = [w for w in workspaces if w]
        if not workspaces:
            print("No workspaces found.")
            return 2

        for workspace in workspaces:
            status = model_status(workspace.id)
            print(f"\nWorkspace {workspace.id} ({workspace.name})")
            print(json.dumps(status, indent=2, default=str))
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
