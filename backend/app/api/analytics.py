from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..db.session import get_db
from ..models.calendar import HistoricalPost
from ..models.video import AnalysisJob, Video
from .deps import get_current_user, get_workspace_id

router = APIRouter(prefix="/analytics", tags=["analytics"])

PLATFORMS = ("instagram", "youtube")


def _sum_known(rows: list[HistoricalPost], field: str) -> int | None:
    """Sum a metric only when at least one row actually contains that metric."""
    values = [getattr(row, field, None) for row in rows]
    known = [int(value) for value in values if value is not None]
    return sum(known) if known else None


def _engagement(views: int | None, likes: int, comments: int, shares: int) -> float | None:
    if views is None:
        return None
    return round((likes + comments + shares) / views, 4) if views else 0.0


def _platform_metrics(rows: list[HistoricalPost]) -> dict:
    known_view_rows = [row for row in rows if row.views is not None]
    views = _sum_known(rows, "views")
    likes = _sum_known(rows, "likes")
    comments = _sum_known(rows, "comments")
    shares = _sum_known(rows, "shares")
    engagement_rows = [
        row for row in known_view_rows
        if row.likes is not None and row.comments is not None and row.shares is not None
    ]
    engagement_views = sum(int(row.views) for row in engagement_rows) if engagement_rows else None
    engagement_rate = (
        _engagement(
            engagement_views,
            sum(int(row.likes) for row in engagement_rows),
            sum(int(row.comments) for row in engagement_rows),
            sum(int(row.shares) for row in engagement_rows),
        )
        if engagement_rows else None
    )
    return {
        "posts": len(rows),
        "posts_with_views": len(known_view_rows),
        "views": views,
        "likes": likes,
        "comments": comments,
        "shares": shares,
        "saves": _sum_known(rows, "saves"),
        "reach": _sum_known(rows, "reach"),
        "impressions": _sum_known(rows, "impressions"),
        "follows": _sum_known(rows, "follows"),
        "profile_visits": _sum_known(rows, "profile_visits"),
        "avg_views": int(views / len(known_view_rows)) if views is not None and known_view_rows else None,
        "engagement_rate": engagement_rate,
        "engagement_sample_size": len(engagement_rows),
    }


@router.get("/summary")
def summary(user=Depends(get_current_user), db: Session = Depends(get_db)):
    ws_id = get_workspace_id(user, db)
    videos = db.query(Video).filter(Video.workspace_id == ws_id).count()
    posts = db.query(HistoricalPost).filter(HistoricalPost.workspace_id == ws_id).all()
    jobs = db.query(AnalysisJob).join(Video).filter(Video.workspace_id == ws_id)
    jobs_total = jobs.count()
    jobs_done = jobs.filter(AnalysisJob.status == "done").count()

    by_platform = {
        platform: _platform_metrics([row for row in posts if row.platform == platform])
        for platform in PLATFORMS
    }
    aggregate = _platform_metrics(posts)

    return {
        "videos": videos,
        "analyses": jobs_total,
        "analyses_completed": jobs_done,
        "historical_posts": len(posts),
        "total_views": aggregate["views"],
        "total_likes": aggregate["likes"],
        "total_comments": aggregate["comments"],
        "total_shares": aggregate["shares"],
        "total_saves": aggregate["saves"],
        "total_reach": aggregate["reach"],
        "total_impressions": aggregate["impressions"],
        "total_follows": aggregate["follows"],
        "profile_visits": aggregate["profile_visits"],
        "engagement_rate": aggregate["engagement_rate"],
        "by_platform": by_platform,
        "source": "Imported and provider-synced posts" if posts else "No imported or synced posts yet",
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
            "id": row.id,
            "platform": row.platform,
            "published_at": row.published_at,
            "title": row.title,
            "caption": row.caption,
            "content_type": row.content_type,
            "duration_seconds": row.duration_seconds,
            "views": row.views,
            "likes": row.likes,
            "comments": row.comments,
            "shares": row.shares,
            "saves": row.saves,
            "reach": row.reach,
            "impressions": row.impressions,
            "engagement_rate": _engagement(
                row.views,
                row.likes,
                row.comments,
                row.shares,
            ) if row.views is not None and row.likes is not None and row.comments is not None and row.shares is not None else None,
        }
        for row in rows
    ]
