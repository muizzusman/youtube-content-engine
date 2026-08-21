import statistics
from datetime import datetime, timezone

# Constant added to the engagement-rate denominator to dampen
# inflated rates on very low-view videos (see compute_video_metrics).
ENGAGEMENT_SMOOTHING_VIEWS = 100


def get_latest_snapshot(
    connection,
    video_id: str,
) -> dict | None:
    """
    Return the most recent snapshot row for a video,
    or None if no snapshot exists yet.
    """

    row = connection.execute(
        """
        SELECT views, likes, comments, checked_at
        FROM snapshots
        WHERE video_id = ?
        ORDER BY checked_at DESC
        LIMIT 1
        """,
        (video_id,),
    ).fetchone()

    if row is None:
        return None

    return dict(row)


def hours_since_published(published_at: str) -> float:
    """
    published_at is stored as an ISO 8601 string from the
    YouTube API, e.g. "2026-08-19T14:32:10Z".
    """

    published = datetime.fromisoformat(
        published_at.replace("Z", "+00:00")
    )

    now = datetime.now(timezone.utc)

    delta_hours = (now - published).total_seconds() / 3600

    # Guard against brand-new videos (avoid divide-by-zero
    # or absurdly inflated velocity for videos <1 hour old)
    return max(delta_hours, 0.5)


def compute_video_metrics(
    connection,
    video: dict,
) -> dict | None:
    """
    Compute normalized metrics for a single video row
    (as returned from the `videos` table).

    Returns None if there is no snapshot data yet for this video.
    """

    snapshot = get_latest_snapshot(connection, video["video_id"])

    if snapshot is None:
        return None

    views = snapshot["views"]
    likes = snapshot["likes"]
    comments = snapshot["comments"]

    age_hours = hours_since_published(video["published_at"])

    view_velocity = views / age_hours

    subscriber_count = max(video["subscriber_count"], 1)
    subscriber_adjusted_reach = views / subscriber_count

    # Laplace-style smoothing: a video with 12 views and 3 likes
    # would otherwise post a 25% engagement rate and dominate the
    # min-max normalization. Adding a constant to the denominator
    # dampens rates for low-view videos while barely moving the
    # needle for established ones.
    engagement_rate = (
        (likes + comments) / (views + ENGAGEMENT_SMOOTHING_VIEWS)
        if views >= 0
        else 0.0
    )

    return {
        "video_id": video["video_id"],
        "channel_id": video["channel_id"],
        "channel_name": video["channel_name"],
        "title": video["title"],
        "format": video["format"],
        "video_url": video["video_url"],
        "views": views,
        "likes": likes,
        "comments": comments,
        "age_hours": round(age_hours, 1),
        "view_velocity": round(view_velocity, 2),
        "subscriber_adjusted_reach": round(subscriber_adjusted_reach, 6),
        "engagement_rate": round(engagement_rate, 4),
    }


def attach_channel_baselines(metrics: list[dict]) -> list[dict]:
    """
    For each video, compute its performance relative to the
    median view count of *other videos from the same channel
    and same format* (Shorts compared to Shorts, long-form to
    long-form — never mixed).

    If a channel has fewer than 2 videos in a format, fall back
    to the median across all channels for that same format, so
    baseline_ratio stays meaningful even with one video per
    channel.
    """

    # Group view counts by (channel_id, format)
    groups: dict[tuple, list[int]] = {}

    # Group view counts by format only (cross-channel fallback)
    format_groups: dict[str, list[int]] = {}

    for item in metrics:
        key = (item["channel_id"], item["format"])
        groups.setdefault(key, []).append(item["views"])

        format_groups.setdefault(item["format"], []).append(item["views"])

    for item in metrics:
        key = (item["channel_id"], item["format"])
        group_views = groups[key]

        if len(group_views) >= 2:
            baseline = statistics.median(group_views)
        elif len(format_groups[item["format"]]) >= 2:
            baseline = statistics.median(format_groups[item["format"]])
        else:
            baseline = item["views"] or 1

        baseline = baseline or 1

        item["channel_baseline_views"] = round(baseline, 1)
        item["baseline_ratio"] = round(item["views"] / baseline, 2)

    return metrics


def compute_all_metrics(
    connection,
    videos: list[dict],
) -> list[dict]:
    """
    Main entry point for Stage 3.

    Takes the list of video dicts (as stored in `videos`) and
    returns a list of normalized metric dicts, with channel
    baseline comparisons attached.

    Videos with no snapshot yet are silently skipped — this can
    happen on the very first run before any snapshot exists.
    """

    metrics = []

    for video in videos:
        result = compute_video_metrics(connection, video)

        if result is not None:
            metrics.append(result)

    metrics = attach_channel_baselines(metrics)

    return metrics