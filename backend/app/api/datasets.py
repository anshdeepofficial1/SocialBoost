import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..db.session import get_db
from ..models.calendar import DatasetImport, HistoricalPost
from ..services.dataset_adapter import normalise, read_csv_bytes
from .deps import get_current_user, get_workspace_id

router = APIRouter(prefix="/datasets", tags=["datasets"])

MAX_ROWS = 20000


@router.post("/import")
def import_csv(file: UploadFile = File(...), user=Depends(get_current_user), db: Session = Depends(get_db)):
    ws_id = get_workspace_id(user, db)

    if file.filename and not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "Upload a .csv file")

    content = file.file.read()
    if not content:
        raise HTTPException(400, "The uploaded file is empty")

    try:
        df, report = read_csv_bytes(content, file.filename or "")
    except ValueError as exc:
        raise HTTPException(400, str(exc))

    if len(df) > MAX_ROWS:
        raise HTTPException(400, f"CSV has {len(df)} rows; the limit is {MAX_ROWS}")

    existing_ids = {
        pid
        for (pid,) in db.query(HistoricalPost.post_id)
        .filter(HistoricalPost.workspace_id == ws_id, HistoricalPost.post_id != "")
        .all()
    }

    result = normalise(df, report, existing_ids=existing_ids, max_rows=MAX_ROWS)
    warnings: list[str] = list(report.notes)

    if result.duplicates:
        warnings.append(f"{result.duplicates} row(s) skipped because their post_id was already imported.")
    if result.rejected:
        warnings.append(f"{result.rejected} row(s) rejected: unknown platform, unreadable date or missing views.")

    if not result.rows:
        db.rollback()
        raise HTTPException(
            400,
            "No valid rows found. Each row needs a platform (instagram/youtube), a readable "
            "published_at date and a non-negative views value. "
            f"Columns detected: {', '.join(map(str, df.columns))}",
        )

    for row in result.rows:
        with db.begin_nested():
            db.add(HistoricalPost(workspace_id=ws_id, **row))

    db.add(
        DatasetImport(
            workspace_id=ws_id,
            filename=file.filename or "data.csv",
            rows_imported=len(result.rows),
            rows_rejected=result.rejected,
            columns=[str(c) for c in df.columns],
            warnings=warnings,
        )
    )
    db.commit()

    return {
        "rows_imported": len(result.rows),
        "rows_rejected": result.rejected,
        "rows_duplicate": result.duplicates,
        "columns": [str(c) for c in df.columns],
        "warnings": warnings,
        "total_rows_in_file": int(len(df)),
        # What the importer understood, so a mismatched export is visible
        # instead of silently training on the wrong columns.
        "mapping": report.as_dict(),
    }


@router.get("/imports")
def list_imports(user=Depends(get_current_user), db: Session = Depends(get_db)):
    ws_id = get_workspace_id(user, db)
    rows = (
        db.query(DatasetImport)
        .filter(DatasetImport.workspace_id == ws_id)
        .order_by(DatasetImport.created_at.desc())
        .limit(50)
        .all()
    )
    return [
        {
            "id": r.id,
            "filename": r.filename,
            "rows_imported": r.rows_imported,
            "rows_rejected": r.rows_rejected,
            "columns": r.columns,
            "warnings": r.warnings,
            "created_at": r.created_at,
        }
        for r in rows
    ]


@router.get("/template")
def template(user=Depends(get_current_user)):
    """The canonical header, plus the growth columns the coach uses."""
    from fastapi.responses import PlainTextResponse

    header = (
        "post_id,platform,published_at,duration_seconds,views,likes,comments,shares,saves,"
        "impressions,reach,followers_at_publish,follows,profile_visits,avg_watch_seconds,retention,"
        "content_type,caption,title,hashtags,content_category"
    )
    example = (
        "ig_001,instagram,2026-01-15T18:30:00Z,24,18400,920,64,31,210,26000,17200,5400,96,310,18.4,0.71,reel,"
        '"Editing a reel in 30 seconds",Reel speedrun,#editing #reels,education'
    )
    return PlainTextResponse(header + "\n" + example + "\n", media_type="text/csv")
