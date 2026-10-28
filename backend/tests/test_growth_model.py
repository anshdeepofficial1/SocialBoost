"""Regression tests for honest handling of missing provider metrics."""

import numpy as np
import pandas as pd

from app.services.growth_model import _percentile, build_target


def test_missing_engagement_metrics_are_not_treated_as_zero():
    views = pd.Series([100.0, 200.0, 300.0, 400.0])
    frame = pd.DataFrame({
        "views": views,
        "likes": [np.nan] * 4,
        "comments": [np.nan] * 4,
        "shares": [np.nan] * 4,
        "saves": [np.nan] * 4,
        "follows": [np.nan] * 4,
        "retention": [np.nan] * 4,
    })

    target, detail, coverage = build_target(frame)

    expected_reach = views / views.median()
    expected_target = _percentile(expected_reach)
    assert np.allclose(target.to_numpy(), expected_target.to_numpy())
    assert coverage.saves is False
    assert coverage.follows is False
    assert coverage.retention is False
    assert detail["engagement_rate_mean"] is None
    assert detail["save_rate_mean"] is None
    assert detail["follow_rate_mean"] is None


def test_real_zero_engagement_stays_a_valid_measurement():
    frame = pd.DataFrame({
        "views": [100.0, 200.0, 300.0, 400.0],
        "likes": [0.0, 1.0, 2.0, 3.0],
        "comments": [0.0, 0.0, 1.0, 1.0],
        "shares": [0.0, 0.0, 0.0, 1.0],
        "saves": [np.nan] * 4,
        "follows": [np.nan] * 4,
        "retention": [np.nan] * 4,
    })

    target, detail, coverage = build_target(frame)

    assert target.notna().all()
    assert detail["engagement_rate_mean"] is not None
    assert coverage.saves is False
