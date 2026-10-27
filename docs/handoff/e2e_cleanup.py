"""Remove the throwaway walkthrough account and everything it created."""

import glob
import os
import sqlite3

DB = r"C:\Users\varun\Documents\Default Project\backend\socialboost.db"
ART = r"C:\Users\varun\Documents\Default Project\ml\artifacts"
EMAIL = "walkthrough+153958@signal.test"

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

user = con.execute("select id from users where email = ?", (EMAIL,)).fetchone()
if not user:
    print("user already gone")
    raise SystemExit(0)
uid = user["id"]

ws_rows = con.execute("select id from workspaces where owner_id = ?", (uid,)).fetchall()
ws_ids = [r["id"] for r in ws_rows]
print("user:", uid, "workspaces:", ws_ids)

WS_TABLES = [
    "videos", "analysis_jobs", "analysis_results", "historical_posts",
    "dataset_imports", "model_versions", "predictions", "drafts",
    "scheduled_posts", "social_accounts",
]

for ws in ws_ids:
    for t in WS_TABLES:
        cols = [r[1] for r in con.execute(f"PRAGMA table_info({t})")]
        if "workspace_id" not in cols:
            continue
        # analysis_jobs/results hang off video_id, not workspace_id
        if t == "analysis_results":
            con.execute(
                "delete from analysis_results where job_id in "
                "(select id from analysis_jobs where video_id in "
                "(select id from videos where workspace_id = ?))", (ws,))
            continue
        if t == "analysis_jobs":
            con.execute(
                "delete from analysis_jobs where video_id in "
                "(select id from videos where workspace_id = ?)", (ws,))
            continue
        con.execute(f"delete from {t} where workspace_id = ?", (ws,))

con.execute("delete from user_preferences where user_id = ?", (uid,))
con.execute("delete from workspaces where owner_id = ?", (uid,))
con.execute("delete from users where id = ?", (uid,))
con.commit()

for ws in ws_ids:
    for f in glob.glob(os.path.join(ART, f"*{ws}*.joblib")):
        os.remove(f)
        print("removed artifact:", os.path.basename(f))

con.execute("VACUUM")

print("\n=== FINAL STATE ===")
for t in ["users", "workspaces", "user_preferences", "videos", "analysis_jobs",
          "analysis_results", "historical_posts", "dataset_imports",
          "model_versions", "predictions", "drafts", "scheduled_posts",
          "social_accounts"]:
    print(f"  {t:<20} {con.execute(f'select count(*) from {t}').fetchone()[0]}")
print("\n=== REMAINING USERS ===")
for r in con.execute("select email, full_name from users order by created_at"):
    print("  ", r["email"], "/", r["full_name"])
print("\nml/artifacts:", os.listdir(ART) if os.path.isdir(ART) else "missing")
con.close()
