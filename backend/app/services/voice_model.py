"""Voice writer: a language model trained only on your own captions.

This is deliberately not a downloaded general-purpose LLM. It is a character
and word n-gram model plus a style profile fitted to the workspace's own
captions, titles and hooks. That means:

* it can only say things you have already said or close variants of them;
* it costs nothing to train and runs on a CPU in under a second;
* it is honest about its ceiling — with 30 captions it writes pastiche, with
  300 it starts to sound like you.

The style profile is what makes output usable: sentence length, emoji habit,
hashtag count, capitalisation, line-break rhythm, call-to-action style and the
opening patterns your best posts use.
"""

from __future__ import annotations

import math
import os
import random
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime

import joblib
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from ..core.config import settings
from ..models.calendar import HistoricalPost

MODEL_DIR = settings.resolved_model_dir
os.makedirs(MODEL_DIR, exist_ok=True)

MIN_CAPTIONS = 8

START = "\x02"
END = "\x03"

_EMOJI = re.compile(
    "[" "\U0001F300-\U0001FAFF" "\U00002600-\U000027BF" "\U0001F1E0-\U0001F1FF" "]+"
)
_WORD = re.compile(r"[A-Za-z0-9']+|[.,!?;:#]|[\U0001F300-\U0001FAFF]")

CTA_PATTERNS = (
    "follow", "comment", "share", "save", "subscribe", "link in bio", "link",
    "try this", "tell me", "which one", "drop a", "tag a", "watch",
)
HOOK_OPENERS = (
    "stop ", "why ", "how ", "nobody ", "the truth ", "here's ", "here is ",
    "if you ", "this is ", "i ", "you ", "what ", "3 ", "5 ", "the ",
)


def _safe_key(workspace_id: str | None) -> str:
    return "global" if not workspace_id else "".join(
        c for c in workspace_id if c.isalnum() or c in "-_"
    )


def artifact_path(workspace_id: str | None) -> str:
    return os.path.join(MODEL_DIR, f"voice_model_{_safe_key(workspace_id)}.joblib")


def tokenize(text: str) -> list[str]:
    return _WORD.findall(text or "")


@dataclass
class StyleProfile:
    avg_sentence_words: float = 12.0
    median_caption_chars: float = 120.0
    emoji_rate: float = 0.0
    hashtag_mean: float = 3.0
    line_break_rate: float = 0.3
    cta_rate: float = 0.5
    question_rate: float = 0.3
    exclamation_rate: float = 0.2
    capitalised_start_rate: float = 0.9
    vocabulary: list[str] = field(default_factory=list)
    hashtag_pool: list[str] = field(default_factory=list)
    opening_patterns: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "avg_sentence_words": round(self.avg_sentence_words, 1),
            "median_caption_chars": round(self.median_caption_chars, 1),
            "emoji_rate": round(self.emoji_rate, 2),
            "hashtag_mean": round(self.hashtag_mean, 1),
            "line_break_rate": round(self.line_break_rate, 2),
            "cta_rate": round(self.cta_rate, 2),
            "question_rate": round(self.question_rate, 2),
            "exclamation_rate": round(self.exclamation_rate, 2),
            "capitalised_start_rate": round(self.capitalised_start_rate, 2),
            "vocabulary_size": len(self.vocabulary),
            "hashtag_pool": self.hashtag_pool[:20],
            "opening_patterns": self.opening_patterns[:6],
        }


def _fit_style(captions: list[str], titles: list[str], hashtags: list[str]) -> StyleProfile:
    texts = [t for t in captions if t.strip()]
    if not texts:
        texts = [t for t in titles if t.strip()]
    if not texts:
        return StyleProfile()

    sentences = []
    for text in texts:
        sentences.extend(s for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip())
    sentence_lengths = [len(s.split()) for s in sentences] or [12]

    tags = Counter()
    for blob in hashtags:
        tags.update(t.lower() for t in re.findall(r"#\w+", blob or ""))
    for text in texts:
        tags.update(t.lower() for t in re.findall(r"#\w+", text))

    vocabulary = Counter()
    for text in texts:
        vocabulary.update(w.lower() for w in re.findall(r"[A-Za-z']{3,}", text))

    openers = []
    for text in texts:
        first = text.strip().split("\n")[0].strip()
        if not first:
            continue
        for pattern in HOOK_OPENERS:
            if first.lower().startswith(pattern.strip()):
                openers.append(pattern.strip())
                break
    opener_counts = Counter(openers).most_common(6)

    return StyleProfile(
        avg_sentence_words=float(np.mean(sentence_lengths)),
        median_caption_chars=float(np.median([len(t) for t in texts])),
        emoji_rate=float(np.mean([1.0 if _EMOJI.search(t) else 0.0 for t in texts])),
        hashtag_mean=float(np.mean([len(re.findall(r"#\w+", t)) for t in texts])),
        line_break_rate=float(np.mean([1.0 if "\n" in t else 0.0 for t in texts])),
        cta_rate=float(np.mean([1.0 if any(c in t.lower() for c in CTA_PATTERNS) else 0.0 for t in texts])),
        question_rate=float(np.mean([1.0 if "?" in t else 0.0 for t in texts])),
        exclamation_rate=float(np.mean([1.0 if "!" in t else 0.0 for t in texts])),
        capitalised_start_rate=float(np.mean([1.0 if t[:1].isupper() else 0.0 for t in texts])),
        vocabulary=[w for w, _ in vocabulary.most_common(120)],
        hashtag_pool=[t for t, _ in tags.most_common(30)],
        opening_patterns=[p for p, _ in opener_counts],
    )


def _ngram_counts(texts: list[str], order: int) -> tuple[dict, dict]:
    forward: dict[tuple, Counter] = defaultdict(Counter)
    starters: Counter = Counter()
    for text in texts:
        tokens = [START] * (order - 1) + tokenize(text) + [END]
        if len(tokens) <= order:
            continue
        starters[tuple(tokens[: order - 1])] += 1
        for i in range(len(tokens) - order + 1):
            gram = tuple(tokens[i : i + order - 1])
            forward[gram][tokens[i + order - 1]] += 1
    return dict(forward), starters


def train(db: Session, workspace_id: str | None = None) -> dict:
    query = db.query(HistoricalPost)
    if workspace_id:
        query = query.filter(HistoricalPost.workspace_id == workspace_id)
    rows = query.all()

    captions = [r.caption or "" for r in rows if (r.caption or "").strip()]
    titles = [r.title or "" for r in rows if (r.title or "").strip()]
    hashtags = [r.hashtags or "" for r in rows]

    if len(captions) + len(titles) < MIN_CAPTIONS:
        return {
            "status": "insufficient_data",
            "n_captions": len(captions),
            "required": MIN_CAPTIONS,
            "message": (
                f"The voice model needs at least {MIN_CAPTIONS} of your own captions or titles. "
                f"Found {len(captions)} captions and {len(titles)} titles. Import a CSV that includes "
                "your captions."
            ),
        }

    # Weight the model toward writing that actually performed. Repeated text
    # makes the n-gram counts favour the phrasing you use when it works.
    corpus = list(captions) + list(titles)
    views = [float(r.views or 0) for r in rows if (r.caption or "").strip()]
    if views:
        median = float(np.median(views)) or 1.0
        weighted: list[str] = []
        for r in rows:
            text = (r.caption or "").strip()
            if not text:
                continue
            weight = 1 + int(min(3, (float(r.views or 0) / median)))
            weighted.extend([text] * weight)
        corpus = weighted + list(titles)

    style = _fit_style(captions, titles, hashtags)
    forward3, starters3 = _ngram_counts(corpus, 3)
    forward2, starters2 = _ngram_counts(corpus, 2)
    forward1, _ = _ngram_counts(corpus, 1)

    version = datetime.utcnow().strftime("voice-%Y%m%d%H%M%S")
    path = artifact_path(workspace_id)
    artifact = {
        "forward3": forward3,
        "forward2": forward2,
        "forward1": forward1,
        "starters3": starters3,
        "starters2": starters2,
        "style": style,
        "version": version,
        "trained_at": datetime.utcnow().isoformat(),
        "n_captions": len(captions),
        "n_titles": len(titles),
        "n_corpus": len(corpus),
        "samples": [t for t in captions[:40]],
    }
    joblib.dump(artifact, path)

    from ..models.model_version import ModelVersion

    db.add(
        ModelVersion(
            workspace_id=workspace_id,
            name="voice_writer",
            version=version,
            metrics={
                "n_captions": len(captions),
                "n_titles": len(titles),
                "vocabulary_size": len(style.vocabulary),
                "hashtags_learned": len(style.hashtag_pool),
            },
            path=path,
        )
    )
    db.commit()

    return {
        "status": "trained",
        "version": version,
        "n_captions": len(captions),
        "n_titles": len(titles),
        "style": style.as_dict(),
        "note": (
            "This model writes from your own phrasing only. It cannot invent a new content "
            "strategy; it reproduces the voice of the captions you imported."
        ),
    }


def load(workspace_id: str | None) -> dict | None:
    path = artifact_path(workspace_id)
    if not os.path.exists(path):
        return None
    try:
        return joblib.load(path)
    except Exception:
        return None


def status(workspace_id: str | None) -> dict:
    artifact = load(workspace_id)
    if not artifact:
        return {"available": False}
    return {
        "available": True,
        "version": artifact.get("version"),
        "trained_at": artifact.get("trained_at"),
        "n_captions": artifact.get("n_captions"),
        "n_titles": artifact.get("n_titles"),
        "style": artifact["style"].as_dict(),
    }


def _weighted_choice(counter: Counter, temperature: float, rng: random.Random) -> str:
    if not counter:
        return END
    tokens = list(counter.keys())
    counts = np.array([counter[t] for t in tokens], dtype=float)
    # Temperature reshapes the distribution without ever making a token impossible.
    weights = np.power(counts, 1.0 / max(0.2, temperature))
    weights = weights / weights.sum()
    return rng.choices(tokens, weights=weights, k=1)[0]


def _starter_for_topic(
    artifact: dict,
    topic: str | None,
    rng: random.Random,
    avoid: set[str] | None = None,
) -> tuple[list[str], list[str]]:
    """Pick an opening context and the words to keep from it.

    Seeding with a bare word gives a context the model has rarely seen, which
    terminates after two tokens. Starting from the opening of a real post that
    mentions the topic keeps the output fluent and on-subject. The opening
    words are returned as output too, so a caption never begins mid-sentence.

    ``avoid`` holds openers already used for this request, so a short corpus
    still produces different starting points instead of one repeated caption.
    """
    avoid = avoid or set()
    order = 2
    samples = artifact.get("samples") or []
    if topic:
        lowered = topic.lower()
        matching = [s for s in samples if lowered in s.lower()]
        unused = [s for s in matching if s.split()[0].lower() not in avoid] or matching
        if unused:
            tokens = tokenize(rng.choice(unused))
            prefix = tokens[:1]
            return [START] * order + prefix, prefix
        # No post mentions it: keep the topic as the opening word so the result
        # stays about what was asked.
        prefix = [topic.split()[0]]
        return [START] * order + prefix, prefix

    starters = artifact.get("starters3") or {}
    if starters:
        options = list(starters.keys())
        weights = np.array([starters[o] for o in options], dtype=float)
        context = list(rng.choices(options, weights=weights / weights.sum(), k=1)[0])
        return context, [t for t in context if t not in (START, END)]
    return [START, START], []


def _generate_text(
    artifact: dict,
    seed: str | None,
    max_tokens: int,
    temperature: float,
    rng: random.Random,
    avoid: set[str] | None = None,
) -> str:
    forward3 = artifact["forward3"]
    forward2 = artifact["forward2"]
    forward1 = artifact["forward1"]

    tokens, prefix = _starter_for_topic(artifact, seed, rng, avoid)
    out: list[str] = list(prefix)

    for _ in range(max_tokens):
        # Back off from trigram to bigram to unigram, the standard way to keep
        # a sparse model generating instead of stalling.
        context3 = tuple(tokens[-2:])
        context2 = tuple(tokens[-1:])
        if len(context3) == 2 and context3 in forward3:
            nxt = _weighted_choice(forward3[context3], temperature, rng)
        elif len(context2) == 1 and context2 in forward2:
            nxt = _weighted_choice(forward2[context2], temperature, rng)
        else:
            # Unigram fallback. END appears once per caption in this table, so
            # it is often the most common token; letting it win here would stop
            # every generation at the first step.
            pool = Counter(forward1.get((), Counter()))
            pool.pop(END, None)
            nxt = _weighted_choice(pool, temperature, rng)
        if nxt == END:
            break
        if nxt in (START,):
            continue
        tokens.append(nxt)
        out.append(nxt)

    text = " ".join(out)
    text = re.sub(r"\s+([.,!?;:])", r"\1", text)
    text = re.sub(r"\s*#\s*", " #", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _shape(text: str, style: StyleProfile, rng: random.Random) -> str:
    """Apply the learned style so output reads like the account, not a token stream."""
    if not text:
        return ""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    target = max(4, int(style.avg_sentence_words))
    shaped: list[str] = []
    for sentence in sentences:
        words = sentence.split()
        while len(words) > target * 1.8:
            shaped.append(" ".join(words[:target]))
            words = words[target:]
        if words:
            shaped.append(" ".join(words))
    body = " ".join(shaped).strip()
    body = body[:1].upper() + body[1:] if style.capitalised_start_rate > 0.5 and body else body

    if style.line_break_rate > 0.5 and "\n" not in body:
        parts = body.split(". ")
        if len(parts) > 1:
            body = ".\n".join(parts).replace("\n\n", "\n")

    if style.emoji_rate > 0.4 and not _EMOJI.search(body):
        pool = [e for e in ["🔥", "✨", "👇", "💡", "🎯"] ]
        body = f"{body} {rng.choice(pool)}"

    return body.strip()


def _hashtags_for(artifact: dict, topic: str, count: int) -> list[str]:
    style: StyleProfile = artifact["style"]
    pool = style.hashtag_pool or ["#content", "#creator", "#growth"]
    topic_tags = [f"#{w.lower()}" for w in re.findall(r"[A-Za-z]{4,}", topic or "")][:3]
    chosen: list[str] = []
    for tag in topic_tags + pool:
        if tag not in chosen:
            chosen.append(tag)
    return chosen[: max(0, count)]


def generate(
    workspace_id: str | None,
    *,
    topic: str = "",
    platform: str = "instagram",
    kind: str = "caption",
    count: int = 3,
    temperature: float = 0.8,
) -> dict:
    artifact = load(workspace_id)
    if not artifact:
        return {
            "available": False,
            "variants": [],
            "note": (
                f"No voice model for this workspace. Import at least {MIN_CAPTIONS} of your own "
                "captions, then train the writer on the Coach screen."
            ),
        }

    style: StyleProfile = artifact["style"]
    rng = random.Random(f"{workspace_id}-{topic}-{kind}-{count}")
    variants: list[dict] = []
    seen: set[str] = set()

    # With a small corpus the model will happily replay a training caption.
    # Those are rejected, and later attempts sample hotter so the output varies.
    originals = {s.strip().lower() for s in (artifact.get("samples") or [])}
    original_openers = {s.split()[0].lower() for s in originals if s.split()}
    attempts = max(1, min(count, 6)) * 8
    used_openers: set[str] = set()
    used_starts: set[str] = set()

    def content_tokens(text: str) -> list[str]:
        """Words only: hashtags and punctuation make a copy look different."""
        return [t for t in tokenize(text) if re.search(r"[A-Za-z0-9]", t)]

    def too_close(body: str) -> bool:
        """True when the variant is a near-copy of a caption already in the corpus."""
        lowered = body.lower()
        if lowered in originals or lowered in seen:
            return True
        tokens = content_tokens(lowered)
        if len(tokens) < 4:
            return True
        head = " ".join(tokens[:5])
        if head in used_starts:
            return True
        for original in originals:
            source = content_tokens(original)
            if not source:
                continue
            overlap = len(set(tokens) & set(source)) / max(1, len(set(tokens)))
            if overlap > 0.7:
                return True
        return False

    for attempt in range(attempts):
        if len(variants) >= count:
            break
        heat = temperature + 0.15 * (attempt // max(1, count))
        seed = topic.strip() or None
        raw = _generate_text(
            artifact, seed, max_tokens=70, temperature=heat, rng=rng, avoid=used_openers
        )
        body = _shape(raw, style, rng)
        if len(body) < 25 or too_close(body):
            # Remember the rejected opener so the next attempt starts elsewhere.
            first = body.split()[0].lower() if body.split() else ""
            if first in original_openers:
                used_openers.add(first)
            continue
        tokens = tokenize(body.lower())
        used_starts.add(" ".join(tokens[:6]))
        used_openers.add(body.split()[0].lower())
        if topic and topic.lower() not in body.lower() and seed:
            # A seeded generation that drifts away from the topic is not useful.
            body = f"{topic.strip().rstrip('.')} — {body}"
        seen.add(body.lower())

        tags = _hashtags_for(artifact, topic, int(round(style.hashtag_mean)))
        variants.append(
            {
                "text": body,
                "hashtags": tags,
                "characters": len(body),
                "in_your_style": {
                    "avg_sentence_words": round(style.avg_sentence_words, 1),
                    "has_cta": any(c in body.lower() for c in CTA_PATTERNS),
                    "emoji": bool(_EMOJI.search(body)),
                    "line_breaks": body.count("\n"),
                },
            }
        )

    if not variants:
        # Fall back to reusing a proven hook frame with the new subject in it.
        fallback = _adapt_existing(artifact, topic, int(round(style.hashtag_mean)), count)
        return {
            "available": True,
            "kind": kind,
            "platform": platform,
            "trained_on": artifact.get("n_captions"),
            "style": style.as_dict(),
            "variants": fallback,
            "note": (
                "The generator could not produce wording that differed enough from your training "
                "captions. These reuse a hook frame that worked for you, with your topic substituted "
                "in. Import more captions to get original sentences."
            )
            if fallback
            else (
                "The model could not produce a new sentence from your corpus. Add more captions "
                "that mention this topic and retrain."
            ),
        }

    return {
        "available": True,
        "kind": kind,
        "platform": platform,
        "trained_on": artifact.get("n_captions"),
        "style": style.as_dict(),
        "variants": variants,
        "note": (
            "Generated from an n-gram model fitted to your own captions. Longer, more varied "
            "captions in the training data produce more varied output."
        ),
    }


def _adapt_existing(artifact: dict, topic: str, hashtag_count: int, count: int) -> list[dict]:
    """Reuse a proven hook frame with a new topic substituted in.

    With a handful of captions an n-gram model cannot invent new wording. What
    it can do is take a frame that demonstrably worked for this account
    ("Stop editing like this") and swap the subject ("Stop filming like this").
    That is a real iteration tactic, and the response labels it as a frame
    substitution rather than pretending it is original generation.
    """
    samples = [s for s in (artifact.get("samples") or []) if s.strip()]
    if not samples or not topic:
        return []

    rng = random.Random(f"frame-{topic}-{count}")
    style: StyleProfile = artifact["style"]
    subject = topic.strip().lower()
    frames: list[str] = []

    # Frames that generalise: keep the sentence, replace the content word.
    patterns = [
        (r"\b(this|that)\b", f"this {subject}"),
        (r"\b(editing|posting|filming|making|creating)\b", subject),
        (r"\b(hooks?|reels?|videos?|content)\b", subject),
    ]

    for sample in samples:
        head = sample.split("\n")[0].strip()
        if not head:
            continue
        for pattern, replacement in patterns:
            candidate, changed = re.subn(pattern, replacement, head, count=1, flags=re.I)
            if changed and candidate.lower() != head.lower():
                frames.append(candidate)
                break

    variants: list[dict] = []
    seen: set[str] = set()
    for candidate in frames:
        if len(variants) >= count:
            break
        if candidate.lower() in seen:
            continue
        seen.add(candidate.lower())
        variants.append(
            {
                "text": candidate,
                "hashtags": _hashtags_for(artifact, topic, hashtag_count),
                "characters": len(candidate),
                "frame_substitution": True,
                "in_your_style": {
                    "avg_sentence_words": round(style.avg_sentence_words, 1),
                    "has_cta": any(c in candidate.lower() for c in CTA_PATTERNS),
                    "emoji": bool(_EMOJI.search(candidate)),
                    "line_breaks": candidate.count("\n"),
                },
            }
        )
    rng.shuffle(variants)
    return variants


def hook_ideas(workspace_id: str | None, topic: str = "", count: int = 5) -> dict:
    """Opening lines built from the account's own best-performing openers."""
    artifact = load(workspace_id)
    if not artifact:
        return {
            "available": False,
            "hooks": [],
            "note": f"No voice model trained yet. Import at least {MIN_CAPTIONS} captions first.",
        }

    style: StyleProfile = artifact["style"]
    rng = random.Random(f"hooks-{workspace_id}-{topic}")
    samples = artifact.get("samples") or []
    openers = [s.split("\n")[0].strip() for s in samples if s.strip()]

    hooks: list[dict] = []
    seen: set[str] = set()

    # Prefer patterns the account actually opens with, then the model's own text.
    for pattern in style.opening_patterns:
        for opener in openers:
            if opener.lower().startswith(pattern) and opener.lower() not in seen:
                hooks.append({"text": opener, "source": "your own post"})
                seen.add(opener.lower())
                if len(hooks) >= max(1, count // 2):
                    break
        if len(hooks) >= max(1, count // 2):
            break

    for _ in range(max(1, count) * 3):
        if len(hooks) >= count:
            break
        raw = _generate_text(artifact, topic or None, max_tokens=18, temperature=0.9, rng=rng)
        text = _shape(raw, style, rng)
        if len(text.split()) < 3 or text.lower() in seen:
            continue
        seen.add(text.lower())
        hooks.append({"text": text, "source": "model"})

    return {
        "available": True,
        "hooks": hooks[:count],
        "note": "Openers come from your own posts where possible; the rest are generated from your phrasing.",
    }
