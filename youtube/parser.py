import re

def parse_iso_duration(
    duration: str,
) -> int:
    """
    Convert an ISO 8601 YouTube duration into seconds.

    Examples:

    PT45S
    -> 45

    PT1M30S
    -> 90

    PT1H2M10S
    -> 3730

    P0D
    -> 0
    (unstarted premieres / some live streams report duration
    as "0 days" instead of a PT... time value)
    """

    day_match = re.fullmatch(r"P(\d+)D", duration)
    if day_match:
        return int(day_match.group(1)) * 86400

    match = re.fullmatch(
        r"PT"
        r"(?:(\d+)H)?"
        r"(?:(\d+)M)?"
        r"(?:(\d+)S)?",
        duration,
    )

    if not match:
        raise ValueError(
            f"Unsupported duration: {duration}"
        )

    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)

    return (
        hours * 3600
        + minutes * 60
        + seconds
    )

SHORTS_MAX_SECONDS = 180


def classify_format(
    duration_seconds: int,
    thumbnail_width: int | None = None,
    thumbnail_height: int | None = None,
    title: str = "",
    description: str = "",
) -> str:
    """
    Classify a video as "short" or "long" using every signal the
    Data API gives us, since there is no `is_short` field:

    1. Duration — Shorts are capped at 3 minutes (180s), so anything
       longer can never be a Short.
    2. Aspect ratio — Shorts are vertical (or square). A landscape
       video is a regular upload even if it's under 3 minutes, so
       it does not belong in the Shorts baseline group.
    3. Hashtag — creators often tag #shorts / #short explicitly.

    If thumbnail dimensions are unavailable we fall back to the old
    duration-only behavior so classification never gets worse.
    """

    if duration_seconds > SHORTS_MAX_SECONDS:
        return "long"

    text = f"{title} {description}".lower()

    if "#shorts" in text or "#short" in text:
        return "short"

    has_dimensions = (
        thumbnail_width is not None
        and thumbnail_height is not None
        and thumbnail_width > 0
        and thumbnail_height > 0
    )

    if not has_dimensions:
        # No aspect-ratio signal: keep legacy duration-only result
        return "short"

    # Vertical (h > w) or square (h == w) thumbnails indicate a
    # Short; landscape means it's just a short regular video.
    if thumbnail_height >= thumbnail_width:
        return "short"

    return "long"