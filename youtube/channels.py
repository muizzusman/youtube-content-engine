import re

def extract_handle(channel_url: str) -> str:
    match = re.search(
        r"youtube\.com/@([^/?]+)",
        channel_url,
        re.IGNORECASE,
    )

    if not match:
        raise ValueError(
            f"Could not extract YouTube handle from: {channel_url}"
        )

    return f"@{match.group(1)}"

def get_channel_info(client, channel_url):
    handle = extract_handle(channel_url)

    response = client.get_channel_by_handle(handle)

    if not response.get("items"):
        raise ValueError(
            f"Channel not found: {channel_url}"
        )

    channel = response["items"][0]

    return {
        "channel_id": channel["id"],
        "channel_name": channel["snippet"]["title"],
        "subscriber_count": int(
            channel["statistics"].get("subscriberCount", 0)
        ),
        "uploads_playlist_id":
            channel["contentDetails"]
            ["relatedPlaylists"]
            ["uploads"]
    }