import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

import json
from pathlib import Path

from dotenv import load_dotenv

from youtube.analysis import hours_since_published
from youtube.channels import get_channel_info
from youtube.concepts import analyze_concepts
from youtube.llm import get_client as get_llm_client
from youtube.parser import classify_format, parse_iso_duration
from youtube.titles import generate_optimized_title
from youtube.trello import push_winner_to_trello
from youtube.videos import YouTubeClient

BASE_DIR = Path(__file__).resolve().parent

CONFIG_PATH = BASE_DIR / "config.json"

# Videos younger than this are treated as if exactly this old:
# velocity in the first minutes is noise and would otherwise explode.
MIN_AGE_HOURS = 0.5

# velocity_index unit: views per hour per million subscribers.
SUBSCRIBER_SCALE = 1_000_000


def load_config() -> dict:
    with CONFIG_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def fetch_latest_upload(
    client: YouTubeClient,
    channel_url: str,
) -> dict | None:
    """
    Resolve a channel URL to its single most recent upload with full
    statistics, plus derived velocity metrics attached.

    Returns None if the channel has no uploads.
    """

    channel = get_channel_info(client, channel_url)

    print()
    print("-" * 70)
    print(f"Channel: {channel_url}")
    print(f"Name: {channel['channel_name']}")
    print(
        f"Subscribers: "
        f"{channel['subscriber_count']:,}"
    )

    uploads = client.get_uploads(
        channel["uploads_playlist_id"],
        limit=1,
    )

    upload_items = uploads.get("items", [])

    if not upload_items:
        print("No videos found.")
        return None

    video_id = upload_items[0]["contentDetails"]["videoId"]

    details = client.get_videos([video_id])

    detail_items = details.get("items", [])

    if not detail_items:
        print(f"Video {video_id} unavailable — skipping.")
        return None

    video = detail_items[0]

    statistics = video.get("statistics", {})
    content_details = video.get("contentDetails", {})
    snippet = video.get("snippet", {})

    duration_seconds = parse_iso_duration(
        content_details.get("duration", "PT0S")
    )

    thumbnail = snippet.get("thumbnails", {}).get("high", {})

    views = int(statistics.get("viewCount", 0))
    age_hours = hours_since_published(snippet["publishedAt"])

    # Views collected per hour since upload (raw momentum).
    view_velocity = views / age_hours

    # Same figure normalized by audience size, scaled for readability.
    # This is the ranking metric: it measures overperformance relative
    # to the channel's reach, so big channels don't win by default.
    subscriber_count = max(channel["subscriber_count"], 1)
    velocity_index = view_velocity / subscriber_count * SUBSCRIBER_SCALE

    video_data = {
        "video_id": video_id,
        "channel_id": channel["channel_id"],
        "channel_name": channel["channel_name"],
        "subscriber_count": channel["subscriber_count"],
        "title": snippet.get("title", ""),
        "published_at": snippet.get("publishedAt", ""),
        "duration_seconds": duration_seconds,
        "format": classify_format(
            duration_seconds,
            thumbnail_width=thumbnail.get("width"),
            thumbnail_height=thumbnail.get("height"),
            title=snippet.get("title", ""),
            description=snippet.get("description", ""),
        ),
        "thumbnail_url": thumbnail.get("url"),
        "video_url": f"https://www.youtube.com/watch?v={video_id}",
        "views": views,
        "likes": int(statistics.get("likeCount", 0)),
        "comments": int(statistics.get("commentCount", 0)),
        "age_hours": round(age_hours, 1),
        "view_velocity": view_velocity,
        "velocity_index": velocity_index,
    }

    print(
        f"[{video_data['format']:5}] "
        f"{video_data['views']:>12,} views | "
        f"{video_data['title']}"
    )

    return video_data


def print_leaderboard(ranked: list[dict]) -> None:
    print()
    print("=" * 100)
    print("LATEST-UPLOAD VELOCITY RANKING "
          "(views per hour per million subscribers)")
    print("=" * 100)

    for rank, v in enumerate(ranked, start=1):
        flag = " [SHORT]" if v["format"] == "short" else ""
        marker = "  <-- winner" if rank == 1 else ""
        print(
            f"{rank}. {v['channel_name']} ({v['subscriber_count']:,} subs){flag}{marker}\n"
            f"   {v['views']:>10,} views in {v['age_hours']:>7,.1f} h  |  "
            f"{v['view_velocity']:>9,.1f} views/hr raw  |  "
            f"index {v['velocity_index']:>8,.2f}\n"
            f"   {v['title']}"
        )


def main():
    load_dotenv()

    config = load_config()

    client = YouTubeClient()

    videos = []

    for channel_url in config["channels"]:
        try:
            video = fetch_latest_upload(client, channel_url)
        except Exception as error:
            # One bad channel shouldn't kill the whole run.
            print()
            print(f"[error] Skipping {channel_url}: {error}")
            continue

        if video is not None:
            videos.append(video)

    if not videos:
        print()
        print("No videos collected from any channel.")
        return

    ranked = sorted(
        videos,
        key=lambda v: v["velocity_index"],
        reverse=True,
    )

    winner = ranked[0]

    shorts_in_run = [v for v in ranked if v["format"] == "short"]

    if shorts_in_run:
        names = ", ".join(v["channel_name"] for v in shorts_in_run)
        print()
        print(
            "[note] Latest upload(s) from these channels are Shorts, which "
            f"collect views faster than long-form: {names}"
        )

    print_leaderboard(ranked)

    llm_client = get_llm_client()

    print()
    print("Analyzing winning concept...")

    try:
        winner = analyze_concepts(llm_client, [winner])[0]
    except Exception as error:
        print(f"  [warn] Concept analysis failed: {error}")

    print("Generating optimized title...")

    try:
        winner = generate_optimized_title(llm_client, winner)
    except Exception as error:
        print(f"  [warn] Title generation failed: {error}")

    push_winner_to_trello(winner)

    print()
    print("=" * 100)
    print("PERFORMANCE WINNER")
    print("=" * 100)
    print(f"{winner['channel_name']} | {winner['title']}")
    print(
        f"Velocity index: {winner['velocity_index']:,.2f} | "
        f"{winner['view_velocity']:,.1f} views/hr | "
        f"{winner['views']:,} views in {winner['age_hours']:,.1f} h | "
        f"{winner['video_url']}"
    )
    print(f"Format: {winner['format']}")

    optimized_title = winner.get("optimized_title")

    if optimized_title:
        print()
        print(f"  Optimized title: {optimized_title}")
        print(f"  Technique: {winner.get('technique_used')}")
        print(f"  Why: {winner.get('title_rationale')}")

    print()
    print("=" * 70)
    print(f"Compared latest uploads from {len(videos)} channels.")
    print("=" * 70)


if __name__ == "__main__":
    main()
