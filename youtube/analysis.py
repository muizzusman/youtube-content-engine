from datetime import datetime, timezone


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
