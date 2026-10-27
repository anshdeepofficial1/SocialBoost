"""Turn real platform exports into the canonical post schema.

Instagram and YouTube do not agree on column names, and YouTube Studio CSVs
carry a few preamble rows before the header. This module normalises both into
the columns the coach trains on, and reports exactly what it mapped so the
import screen can show the user which column became which field.

Nothing here guesses a value. A column that is absent stays absent, and the
feature builder treats it as missing rather than zero-filling a metric that was
never measured.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

# Canonical field -> accepted header spellings (lowercased, punctuation removed).
ALIASES: dict[str, list[str]] = {
    "post_id": ["post id", "id", "video id", "media id", "permalink", "url", "link", "shortcode"],
    "platform": ["platform", "network", "channel"],
    "published_at": [
        "published at", "publish time", "publish date", "published", "date", "created at",
        "time", "upload date", "video publish time", "posted at", "post date",
    ],
    "content_type": ["content type", "media type", "type", "post type", "format"],
    "duration_seconds": [
        "duration seconds", "duration", "length", "video duration", "duration s",
        "length seconds", "average view duration",
    ],
    "views": ["views", "video views", "plays", "impressions", "reach", "view count"],
    "likes": ["likes", "like count", "reactions"],
    "comments": ["comments", "comment count"],
    "shares": ["shares", "share count", "sends"],
    "saves": ["saves", "saved", "bookmarks"],
    "impressions": ["impressions", "impressions count", "displays"],
    "reach": ["reach", "accounts reached", "unique viewers"],
    "followers_at_publish": ["followers at publish", "followers", "subscribers", "subscriber count"],
    "follows": ["follows", "new followers", "followers gained", "subscribers gained", "subs gained"],
    "profile_visits": ["profile visits", "profile views", "channel views"],
    "avg_watch_seconds": ["average watch time", "avg watch time", "average view duration seconds", "watch time"],
    "retention": ["average percentage viewed", "retention", "avg view percentage", "view percentage"],
    "caption": ["caption", "description", "text", "post text", "video description"],
    "title": ["title", "video title", "name", "post title"],
    "hashtags": ["hashtags", "tags", "hashtag"],
    "content_category": ["content category", "category", "topic", "niche"],
}

REQUIRED = ("platform", "published_at", "views")

# Rows YouTube Studio puts above the real header.
_PREAMBLE_MARKERS = ("video title", "video publish time", "video id")

_PERCENT = re.compile(r"^\s*-?[\d.,]+\s*%\s*$")
_DURATION = re.compile(r"^\s*(?:(\d+):)?(\d{1,2}):(\d{2})(?:\.\d+)?\s*$")


def normalise_header(name: object) -> str:
    text = str(name).strip().lower()
    text = text.replace("\ufeff", "")
    text = re.sub(r"[%()\[\]]", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


@dataclass
class MappingReport:
    mapped: dict[str, str] = field(default_factory=dict)   # canonical -> original header
    missing: list[str] = field(default_factory=list)
    ignored: list[str] = field(default_factory=list)
    platform: str | None = None
    preamble_rows_skipped: int = 0
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "mapped": self.mapped,
            "missing": self.missing,
            "ignored": self.ignored,
            "detected_platform": self.platform,
            "preamble_rows_skipped": self.preamble_rows_skipped,
            "notes": self.notes,
        }


def _sniff_platform(filename: str, df: pd.DataFrame) -> str | None:
    name = (filename or "").lower()
    if "instagram" in name or "ig_" in name:
        return "instagram"
    if "youtube" in name or "yt_" in name or "shorts" in name:
        return "youtube"
    columns = {normalise_header(c) for c in df.columns}
    if {"video title", "video publish time"} & columns:
        return "youtube"
    if {"media type", "accounts reached", "profile visits"} & columns:
        return "instagram"
    return None


def _find_header_row(raw: str) -> tuple[int, int]:
    """Return (header_index, preamble_count) for a CSV that may have a preamble."""
    lines = raw.splitlines()
    for i, line in enumerate(lines[:15]):
        lowered = line.lower()
        if any(marker in lowered for marker in _PREAMBLE_MARKERS):
            return i, i
    return 0, 0


def read_csv_bytes(content: bytes, filename: str = "") -> tuple[pd.DataFrame, MappingReport]:
    """Parse an export, skipping a YouTube preamble and mapping its columns."""
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    header_index, preamble = _find_header_row(text)
    if preamble:
        lines = text.splitlines()[preamble:]
        text = "\n".join(lines)

    try:
        df = pd.read_csv(io.StringIO(text))
    except Exception as exc:  # noqa: BLE001 - surfaced to the caller as a 400
        raise ValueError(f"Could not parse CSV: {exc}") from exc

    if df.empty or not len(df.columns):
        raise ValueError("The CSV has no data rows")

    # YouTube Studio sometimes repeats the header after a totals row.
    first_col = df.columns[0]
    df = df[df[first_col].astype(str).str.lower() != normalise_header(first_col)]

    report = MappingReport(preamble_rows_skipped=preamble)
    canonical_by_header: dict[str, str] = {}
    for canonical, aliases in ALIASES.items():
        for alias in aliases:
            canonical_by_header.setdefault(alias, canonical)

    rename: dict[str, str] = {}
    used: set[str] = set()
    for column in df.columns:
        key = normalise_header(column)
        canonical = canonical_by_header.get(key)
        if canonical and canonical not in used:
            rename[column] = canonical
            report.mapped[canonical] = str(column)
            used.add(canonical)
        else:
            report.ignored.append(str(column))

    df = df.rename(columns=rename)
    report.missing = [c for c in ALIASES if c not in df.columns]
    report.platform = _sniff_platform(filename, df)

    if "platform" not in df.columns and report.platform:
        df["platform"] = report.platform
        report.notes.append(f"Platform inferred as {report.platform} from the file.")
    elif "platform" not in df.columns:
        report.notes.append("No platform column and the file name did not identify one.")

    if "views" not in df.columns and "reach" in df.columns:
        df["views"] = df["reach"]
        report.notes.append("Using 'reach' as views because no views column was present.")

    if "views" not in df.columns:
        raise ValueError(
            "CSV is missing required column(s): views. Also accepted under the names "
            "plays, impressions or reach."
        )

    return df, report


def _to_number(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float, np.integer, np.floating)):
        if pd.isna(value):
            return None
        return float(value)
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "-", "n/a", "na", "--"}:
        return None
    percent = bool(_PERCENT.match(text))
    text = text.replace(",", "").replace("\u00a0", "").replace("%", "").strip()
    text = re.sub(r"[^\d.\-]", "", text)
    if not text or text in {".", "-"}:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return number / 100 if percent else number


def parse_duration(value) -> float | None:
    """Accept 24, '24', '0:24', '1:02:03' and ISO-8601-ish 'PT45S'."""
    if value is None:
        return None
    if isinstance(value, (int, float, np.integer, np.floating)) and not pd.isna(value):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    iso = re.match(r"^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?$", text, re.I)
    if iso:
        h, m, s = (float(part) if part else 0.0 for part in iso.groups())
        return h * 3600 + m * 60 + s
    clock = _DURATION.match(text)
    if clock:
        h, m, s = clock.groups()
        return (float(h) if h else 0.0) * 3600 + float(m) * 60 + float(s)
    number = _to_number(text)
    return number


def _to_int(value) -> int | None:
    number = _to_number(value)
    if number is None:
        return None
    return int(round(number))


def _to_text(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()


def _clean_hashtags(row: pd.Series) -> str:
    explicit = _to_text(row.get("hashtags"))
    caption = _to_text(row.get("caption"))
    found: list[str] = []
    for text in (explicit, caption):
        for tag in re.findall(r"#\w+", text):
            if tag.lower() not in {t.lower() for t in found}:
                found.append(tag)
    return " ".join(found)


def _infer_platform(row: pd.Series, fallback: str | None) -> str | None:
    raw = _to_text(row.get("platform")).lower()
    if raw in {"instagram", "ig", "insta"}:
        return "instagram"
    if raw in {"youtube", "yt", "youtube shorts", "shorts"}:
        return "youtube"
    if raw in {"tiktok", "facebook", "twitter", "x", "linkedin"}:
        return None
    return fallback


def _infer_content_type(row: pd.Series, platform: str) -> str:
    raw = _to_text(row.get("content_type")).lower()
    mapping = {
        "reel": "reel", "reels": "reel", "short": "short", "shorts": "short",
        "video": "video", "long": "long", "carousel": "carousel", "image": "image",
        "story": "story",
    }
    for key, value in mapping.items():
        if key in raw:
            return value
    duration = parse_duration(row.get("duration_seconds"))
    if duration is not None and duration > 90:
        return "long"
    return "short" if platform == "youtube" else "reel"


@dataclass
class NormalisedRows:
    rows: list[dict]
    rejected: int
    duplicates: int
    report: MappingReport


def normalise(
    df: pd.DataFrame,
    report: MappingReport,
    *,
    existing_ids: set[str] | None = None,
    max_rows: int = 20000,
) -> NormalisedRows:
    """Convert a mapped frame into canonical post dicts."""
    existing_ids = existing_ids or set()
    seen: set[str] = set()
    rows: list[dict] = []
    rejected = 0
    duplicates = 0

    for _, row in df.head(max_rows).iterrows():
        platform = _infer_platform(row, report.platform)
        if platform is None:
            rejected += 1
            continue

        published = pd.to_datetime(row.get("published_at"), errors="coerce", utc=True)
        if pd.isna(published):
            rejected += 1
            continue

        views = _to_int(row.get("views"))
        if views is None or views < 0:
            rejected += 1
            continue

        post_id = _to_text(row.get("post_id"))
        if post_id:
            if post_id in existing_ids or post_id in seen:
                duplicates += 1
                continue
            seen.add(post_id)

        reach = _to_int(row.get("reach"))
        impressions = _to_int(row.get("impressions"))
        followers = _to_int(row.get("followers_at_publish"))
        retention = _to_number(row.get("retention"))
        if retention is not None and retention > 1.5:  # stored as 42 rather than 0.42
            retention = retention / 100

        rows.append(
            {
                "post_id": post_id,
                "platform": platform,
                "published_at": published.to_pydatetime().replace(tzinfo=None),
                "content_type": _infer_content_type(row, platform),
                "duration_seconds": parse_duration(row.get("duration_seconds")) or 0.0,
                "views": views,
                "likes": _to_int(row.get("likes")) or 0,
                "comments": _to_int(row.get("comments")) or 0,
                "shares": _to_int(row.get("shares")) or 0,
                "saves": _to_int(row.get("saves")) or 0,
                "impressions": impressions if impressions is not None else (reach or 0),
                "reach": reach if reach is not None else views,
                "followers_at_publish": followers or 0,
                "follows": _to_int(row.get("follows")) or 0,
                "profile_visits": _to_int(row.get("profile_visits")) or 0,
                "avg_watch_seconds": _to_number(row.get("avg_watch_seconds")) or 0.0,
                "retention": retention or 0.0,
                "caption": _to_text(row.get("caption")),
                "title": _to_text(row.get("title")),
                "hashtags": _clean_hashtags(row),
                "content_category": _to_text(row.get("content_category")),
            }
        )

    return NormalisedRows(rows=rows, rejected=rejected, duplicates=duplicates, report=report)
