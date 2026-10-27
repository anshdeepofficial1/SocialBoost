from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..db.session import get_db
from ..models.calendar import HistoricalPost
from ..models.video import AnalysisJob, Video
from .deps import get_current_user, get_workspace_id

router = APIRouter(prefix="/analytics", tags=["analytics"])

PLATFORMS = ("instagram", "youtube")


def _engagement(views: int, likes: int, comments: int, shares: int) -> float:
    return round((likes + comments + shares) / views, 4) if views else 0.0


@router.get("/summary")
def summary(user=Depends(get_current_user), db: Session = Depends(get_db)):
    ws_id = get_workspace_id(user, db)
    videos = db.query(Video).filter(Video.workspace_id == ws_id).count()
    posts = db.query(HistoricalPost).filter(HistoricalPost.workspace_id == ws_id).all()
    jobs = db.query(AnalysisJob).join(Video).filter(Video.workspace_id == ws_id)
    jobs_total = jobs.count()
    jobs_done = jobs.filter(AnalysisJob.status == "done").count()

    total_views = sum(p.views or 0 for p in posts)
    total_likes = sum(p.likes or 0 for p in posts)
    total_comments = sum(p.comments or 0 for p in posts)
    total_shares = sum(p.shares or 0 for p in posts)

    by_platform = {}
    for platform in PLATFORMS:
        rows = [p for p in posts if p.platform == platform]
        views = sum(p.views or 0 for p in rows)
        likes = sum(p.likes or 0 for p in rows)
        comments = sum(p.comments or 0 for p in rows)
        shares = sum(p.shares or 0 for p in rows)
        by_platform[platform] = {
            "posts": len(rows),
            "views": views,
            "likes": likes,
            "comments": comments,
            "shares": shares,
            "avg_views": int(views / len([row for row in rows if row.views is not None])) if any(row.views is not None for row in rows) else 0,
            "engagement_rate": _engagement(views, likes, comments, shares),
        }

    return {
        "videos": videos,
        "analyses": jobs_total,
        "analyses_completed": jobs_done,
        "historical_posts": len(posts),
        "total_views": total_views,
        "total_likes": total_likes,
        "total_comments": total_comments,
        "total_shares": total_shares,
        # Engagement is likes + comments + shares over views, consistently
        # everywhere in the product.
        "engagement_rate": _engagement(total_views, total_likes, total_comments, total_shares),
        "by_platform": by_platform,
        "source": "Imported historical posts" if posts else "No history imported yet",
    }


@router.get("/posts")
def posts(
    limit: int = Query(default=1000, ge=1, le=5000),
    offset: int = Query(default=0, ge=0),
    platform: str | None = None,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ws_id = get_workspace_id(user, db)
    q = db.query(HistoricalPost).filter(HistoricalPost.workspace_id == ws_id)
    if platform:
        if platform not in PLATFORMS:
            from fastapi import HTTPException

            raise HTTPException(400, "platform must be 'instagram' or 'youtube'")
        q = q.filter(HistoricalPost.platform == platform)
    rows = q.order_by(HistoricalPost.published_at.desc()).offset(offset).limit(limit).all()
    return [
        {
            "id": r.id,
            "platform": r.platform,
            "published_at": r.published_at,
            "views": r.views,
            "likes": r.likes,
            "comments": r.comments,
            "shares": r.shares,
            "engagement_rate": _engagement(r.views or 0, r.likes or 0, r.comments or 0, r.shares or 0),
        }
        for r in rows
    ]
