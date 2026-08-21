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


def compute_breakout_scores(metrics: list[dict]) -> list[dict]:
    """
    Takes the list of metric dicts from analysis.py and attaches
    a normalized 0-1 breakout_score to each, based on a weighted
    blend of baseline_ratio, view_velocity, and engagement_rate.
    """

    if not metrics:
        return metrics

    baseline_values = [m["baseline_ratio"] for m in metrics]
    velocity_values = [m["view_velocity"] for m in metrics]
    engagement_values = [m["engagement_rate"] for m in metrics]

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


def select_performance_winner(metrics: list[dict]) -> dict:
    """
    The video with the single highest breakout_score.
    """

    return max(metrics, key=lambda m: m["breakout_score"])


def select_opportunity_winner(
    metrics: list[dict],
    exclude_video_id: str,
) -> dict:
    candidates = [
        m for m in metrics
        if m["video_id"] != exclude_video_id
        and m.get("replicability") is not None
    ]

    if not candidates:
        candidates = [m for m in metrics if m["video_id"] != exclude_video_id]
        return max(candidates, key=lambda m: m["engagement_norm"])

    return max(
        candidates,
        key=lambda m: (m["replicability"], m["engagement_norm"]),
    )