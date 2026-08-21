def normalize_min_max(values: list[float]) -> list[float]:
    """
    Scales a list of numbers to the 0-1 range.
    If all values are identical, everyone gets 0.5
    (avoids divide-by-zero and avoids falsely scoring 0).
    """

    if not values:
        return []

    lo = min(values)
    hi = max(values)

    if hi == lo:
        return [0.5 for _ in values]

    return [(v - lo) / (hi - lo) for v in values]


def _quantile(ordered: list[float], q: float) -> float:
    """Linear-interpolated quantile of an already-sorted list."""

    position = q * (len(ordered) - 1)
    lower_index = int(position)
    upper_index = min(lower_index + 1, len(ordered) - 1)
    fraction = position - lower_index

    return (
        ordered[lower_index] * (1 - fraction)
        + ordered[upper_index] * fraction
    )


def clip_outliers(values: list[float], k: float = 1.5) -> list[float]:
    """
    Clips values to Tukey fences ([Q1 - k·IQR, Q3 + k·IQR]) before
    normalization, so one extreme outlier (e.g. a single 30x
    baseline_ratio) doesn't compress every other video's normalized
    score into a narrow band.

    Unlike fixed-percentile clipping, Tukey fences leave well-behaved
    data completely untouched regardless of run size — only genuine
    outliers are pulled in.
    """

    if len(values) < 4:
        return list(values)

    ordered = sorted(values)

    q1 = _quantile(ordered, 0.25)
    q3 = _quantile(ordered, 0.75)
    iqr = q3 - q1

    if iqr == 0:
        return list(values)

    lo = q1 - k * iqr
    hi = q3 + k * iqr

    return [min(max(v, lo), hi) for v in values]


def compute_breakout_scores(metrics: list[dict]) -> list[dict]:
    """
    Takes the list of metric dicts from analysis.py and attaches
    a normalized 0-1 breakout_score to each, based on a weighted
    blend of baseline_ratio, view_velocity, and engagement_rate.
    """

    if not metrics:
        return metrics

    baseline_values = clip_outliers([m["baseline_ratio"] for m in metrics])
    velocity_values = clip_outliers([m["view_velocity"] for m in metrics])
    engagement_values = clip_outliers([m["engagement_rate"] for m in metrics])

    baseline_norm = normalize_min_max(baseline_values)
    velocity_norm = normalize_min_max(velocity_values)
    engagement_norm = normalize_min_max(engagement_values)

    WEIGHT_BASELINE = 0.45
    WEIGHT_VELOCITY = 0.35
    WEIGHT_ENGAGEMENT = 0.20

    for i, m in enumerate(metrics):
        score = (
            baseline_norm[i] * WEIGHT_BASELINE
            + velocity_norm[i] * WEIGHT_VELOCITY
            + engagement_norm[i] * WEIGHT_ENGAGEMENT
        )

        m["baseline_norm"] = round(baseline_norm[i], 3)
        m["velocity_norm"] = round(velocity_norm[i], 3)
        m["engagement_norm"] = round(engagement_norm[i], 3)
        m["breakout_score"] = round(score, 4)

    return metrics


def select_performance_winner(metrics: list[dict]) -> dict | None:
    """
    The video with the single highest breakout_score,
    or None if there are no metrics at all.
    """

    if not metrics:
        return None

    return max(metrics, key=lambda m: m["breakout_score"])


def select_opportunity_winner(
    metrics: list[dict],
    exclude_video_id: str,
) -> dict | None:
    """
    Most replicable concept among the non-winner videos.
    Falls back to highest engagement when no video has a
    replicability score. Returns None if the performance
    winner is the only candidate.
    """

    candidates = [
        m for m in metrics
        if m["video_id"] != exclude_video_id
        and m.get("replicability") is not None
    ]

    if candidates:
        return max(
            candidates,
            key=lambda m: (m["replicability"], m["engagement_norm"]),
        )

    fallback = [m for m in metrics if m["video_id"] != exclude_video_id]

    if not fallback:
        return None

    return max(fallback, key=lambda m: m["engagement_norm"])