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

def classify_format(
    duration_seconds: int,
) -> str:
    """
    Initial practical classifier.

    We will improve Shorts detection later.
    """

    if duration_seconds <= 180:
        return "short"

    return "long"