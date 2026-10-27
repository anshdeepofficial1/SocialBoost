"""Deterministic text heuristics.

These helpers score captions and opening lines with a transparent rule set.
Every adjustment is returned so the caller can see exactly why a score changed.
No language model is involved and no number is invented.
"""

import re

STOPWORDS = {
    "the", "and", "for", "with", "this", "that", "you", "your", "have", "from",
    "are", "was", "were", "will", "just", "about", "into", "they", "them", "then",
    "than", "when", "what", "which", "while", "there", "here", "very", "much",
}

CTA_KEYWORDS = ["follow", "comment", "share", "save", "subscribe", "link", "watch", "click"]
TRIGGER_WORDS = ["stop", "why", "how", "secret", "mistake", "never", "nobody", "truth", "wrong"]


def _keywords(text: str, limit: int = 8) -> list[str]:
    words = re.findall(r"[a-zA-Z]{4,}", text.lower())
    unique: list[str] = []
    for w in words:
        if w in STOPWORDS or w in unique:
            continue
        unique.append(w)
    return unique[:limit]


def analyze_caption(caption: str, platform: str = "instagram") -> dict:
    text = (caption or "").strip()
    words = text.split()
    length = len(text)
    hashtags = re.findall(r"#\w+", text)
    has_cta = any(k in text.lower() for k in CTA_KEYWORDS)

    score = 60
    adjustments: list[dict] = []
    if 50 <= length <= 300:
        score += 10
        adjustments.append({"rule": "Length 50–300 characters", "delta": 10})
    elif length and length < 50:
        score -= 5
        adjustments.append({"rule": "Shorter than 50 characters", "delta": -5})
    elif length > 300:
        score -= 5
        adjustments.append({"rule": "Longer than 300 characters", "delta": -5})

    if len(hashtags) >= 3:
        score += 10
        adjustments.append({"rule": "Three or more hashtags", "delta": 10})
    elif len(hashtags) == 0:
        adjustments.append({"rule": "No hashtags", "delta": 0})

    if has_cta:
        score += 10
        adjustments.append({"rule": "Contains a call to action", "delta": 10})

    if len(words) < 5:
        score -= 15
        adjustments.append({"rule": "Fewer than five words", "delta": -15})

    issues = []
    if not has_cta:
        issues.append("No call to action — viewers have no next step.")
    if len(hashtags) < 3:
        issues.append(f"Only {len(hashtags)} hashtag(s); 3–5 tends to help discovery.")
    if length > 300:
        issues.append("Caption may be truncated in feed.")
    if len(words) < 5:
        issues.append("Caption is very short; add context in the first line.")

    improved = text
    if not has_cta:
        improved = (improved + " Save this for later.").strip()

    alternative_titles: list[str] = []
    if platform == "youtube" and text:
        head = text[:60]
        alternative_titles = [head, f"How to {text[:40]}", f"{text[:40]} (explained)"]

    return {
        "caption_score": max(0, min(100, score)),
        "length": length,
        "word_count": len(words),
        "hashtag_count": len(hashtags),
        "has_cta": has_cta,
        "adjustments": adjustments,
        "issues": issues,
        "improved_caption": improved,
        "alternative_titles": alternative_titles,
        "hashtags_suggested": ["#content", "#creator", "#growth"],
        "keywords": _keywords(text),
    }


def analyze_hook(text: str, duration: float = 3.0) -> dict:
    body = (text or "").strip()
    word_count = len(body.split())
    triggers = [w for w in TRIGGER_WORDS if w in body.lower()]

    score = 50
    reasons: list[str] = []
    adjustments: list[dict] = []

    if len(body) > 20:
        score += 10
        reasons.append("Opening has substantive text.")
        adjustments.append({"rule": "More than 20 characters", "delta": 10})
    if "?" in body:
        score += 5
        reasons.append("Question increases curiosity.")
        adjustments.append({"rule": "Contains a question", "delta": 5})
    if triggers:
        score += 8
        reasons.append(f"Strong trigger word present ({', '.join(triggers)}).")
        adjustments.append({"rule": f"Trigger word: {triggers[0]}", "delta": 8})
    if duration > 4:
        score -= 10
        reasons.append("Hook window longer than 4 seconds.")
        adjustments.append({"rule": "Window longer than 4s", "delta": -10})
    if word_count < 4:
        score -= 10
        reasons.append("Opening is very short.")
        adjustments.append({"rule": "Fewer than 4 words", "delta": -10})
    if word_count > 30:
        score -= 6
        reasons.append("Opening is long for a 3 second window.")
        adjustments.append({"rule": "More than 30 words", "delta": -6})

    score = max(0, min(100, score))
    trimmed = body[:40] if body else "your topic"
    alternatives = [
        f"Stop doing this if you want better results: {trimmed}",
        f"Here's what nobody tells you about {trimmed}",
        f"In 3 seconds: {trimmed}",
    ]

    return {
        "hook_score": score,
        "reasons": reasons,
        "adjustments": adjustments,
        "alternatives": alternatives,
        "opening_duration": duration,
        "word_count": word_count,
        "band": "strong" if score >= 70 else "workable" if score >= 50 else "weak",
    }
