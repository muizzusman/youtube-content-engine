import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

import json
from pathlib import Path
from youtube.analysis import compute_all_metrics
from youtube.database import get_all_videos
from youtube.concepts import analyze_all_concepts
from youtube.patterns import detect_cross_channel_patterns
from youtube.llm import get_client as get_llm_client
from youtube.titles import generate_optimized_title
from youtube.trello import push_winners_to_trello

from dotenv import load_dotenv

from youtube.channels import get_channel_info
from youtube.database import (
    close_connection,
    get_connection,
    initialize_database,
    save_snapshot,
    save_video,
)
from youtube.parser import (
    classify_format,
    parse_iso_duration,
)
from youtube.videos import YouTubeClient

from youtube.scoring import (
    compute_breakout_scores,
    select_performance_winner,
    select_opportunity_winner,
)

BASE_DIR = Path(__file__).resolve().parent

CONFIG_PATH = BASE_DIR / "config.json"


def load_config() -> dict:
    with CONFIG_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def process_channel(
    client: YouTubeClient,
    connection,
    channel_url: str,
    videos_per_channel: int,
) -> list[dict]:

    print()
    print("-" * 70)
    print(f"Channel: {channel_url}")

    channel = get_channel_info(
        client,
        channel_url,
    )

    print(
        f"Name: {channel['channel_name']}"
    )

    print(
        f"Subscribers: "
        f"{channel['subscriber_count']:,}"
    )

    uploads = client.get_uploads(
        channel["uploads_playlist_id"],
        limit=videos_per_channel,
    )

    upload_items = uploads.get(
        "items",
        []
    )

    if not upload_items:
        print("No videos found.")

        return []

    video_ids = [
        item["contentDetails"]["videoId"]
        for item in upload_items
    ]

    details = client.get_videos(
        video_ids
    )

    details_by_id = {
        item["id"]: item
        for item in details.get(
            "items",
            []
        )
    }

    results = []

    for upload in upload_items:

        video_id = upload[
            "contentDetails"
        ]["videoId"]

        video = details_by_id.get(
            video_id
        )

        if video is None:
            continue

        statistics = video.get(
            "statistics",
            {}
        )

        content_details = video.get(
            "contentDetails",
            {}
        )

        snippet = video.get(
            "snippet",
            {}
        )

        duration = content_details.get(
            "duration",
            "PT0S"
        )

        duration_seconds = (
            parse_iso_duration(duration)
        )

        video_data = {
            "video_id": video_id,

            "channel_id":
                channel["channel_id"],

            "channel_name":
                channel["channel_name"],

            "subscriber_count":
                channel["subscriber_count"],

            "title":
                snippet.get(
                    "title",
                    ""
                ),

            "published_at":
                snippet.get(
                    "publishedAt",
                    ""
                ),

            "duration_seconds":
                duration_seconds,

            "format":
                classify_format(
                    duration_seconds
                ),

            "thumbnail_url":
                snippet
                .get("thumbnails", {})
                .get("high", {})
                .get("url"),

            "video_url":
                f"https://www.youtube.com/watch?v={video_id}",

            "views":
                int(
                    statistics.get(
                        "viewCount",
                        0
                    )
                ),

            "likes":
                int(
                    statistics.get(
                        "likeCount",
                        0
                    )
                ),

            "comments":
                int(
                    statistics.get(
                        "commentCount",
                        0
                    )
                ),
        }

        save_video(
            connection,
            video_data
        )

        save_snapshot(
            connection,
            video_data
        )

        results.append(
            video_data
        )

        print(
            f"[{video_data['format']:5}] "
            f"{video_data['views']:>12,} views | "
            f"{video_data['title']}"
        )

    connection.commit()

    return results


def main():
    load_dotenv()

    config = load_config()

    client = YouTubeClient()
    connection = get_connection()
    initialize_database(connection)

    all_videos = []

    try:
        for channel_url in config["channels"]:
            videos = process_channel(
                client=client,
                connection=connection,
                channel_url=channel_url,
                videos_per_channel=config["videos_per_channel"],
            )

            all_videos.extend(videos)

        connection.commit()

        # --- Stage 3: performance normalization ---
        stored_videos = get_all_videos(connection)
        metrics = compute_all_metrics(connection, stored_videos)
        metrics = compute_breakout_scores(metrics)
        llm_client = get_llm_client()

        print()
        print("Running concept analysis (this may take a minute)...")
        metrics = analyze_all_concepts(llm_client, metrics)    

        print("Detecting cross-channel patterns...")
        patterns = detect_cross_channel_patterns(llm_client, metrics)

        performance_winner = select_performance_winner(metrics)
        opportunity_winner = select_opportunity_winner(
            metrics,
            exclude_video_id=performance_winner["video_id"]
            )
        print()
        print("Generating optimized titles...")

        performance_winner = generate_optimized_title(llm_client, performance_winner)
        opportunity_winner = generate_optimized_title(llm_client, opportunity_winner)
        push_winners_to_trello(performance_winner, opportunity_winner)

        print()
        print("=" * 100)
        print("NORMALIZED PERFORMANCE METRICS")
        print("=" * 100)

        metrics_sorted = sorted(
            metrics,
            key=lambda m: m["breakout_score"],
            reverse=True,
            )

        for m in metrics_sorted:
            print(
                f"score {m['breakout_score']:.3f} | "
                f"[{m['format']:5}] "
                f"baseline x{m['baseline_ratio']:>5.2f} | "
                f"velocity {m['view_velocity']:>8.1f} v/hr | "
                f"engagement {m['engagement_rate']*100:>5.2f}% | "
                f"{m['channel_name']} | {m['title'][:60]}"
                )
        
        print()
        print("=" * 100)
        print("PERFORMANCE WINNER")
        print("=" * 100)
        print(f"{performance_winner['channel_name']} | {performance_winner['title']}")
        print(f"Score: {performance_winner['breakout_score']} | {performance_winner['video_url']}")
        print()
        print(f"  Optimized title: {performance_winner['optimized_title']}")
        print(f"  Technique: {performance_winner['technique_used']}")
        print(f"  Why: {performance_winner['title_rationale']}")

        print()
        print("=" * 100)
        print("OPPORTUNITY WINNER")
        print("=" * 100)
        print(f"{opportunity_winner['channel_name']} | {opportunity_winner['title']}")
        print(f"Replicability: {opportunity_winner.get('replicability')}/10 | Engagement: {opportunity_winner['engagement_rate']*100:.2f}% | {opportunity_winner['video_url']}")
        print()
        print(f"  Optimized title: {opportunity_winner['optimized_title']}")
        print(f"  Technique: {opportunity_winner['technique_used']}")
        print(f"  Why: {opportunity_winner['title_rationale']}")

        print()
        print("=" * 100)
        print("CROSS-CHANNEL PATTERNS")
        print("=" * 100)

        if not patterns:
            print("No clear cross-channel patterns detected.")
        else:
            for p in patterns:
                print(f"\n[{p['strength'].upper()}] {p['pattern_name']}")
                print(f"  {p['description']}")
                print(f"  Channels: {', '.join(p['channels_involved'])}")
            for example in p.get('example_titles', []):
                print(f"    - {example}")

    finally:
        close_connection(connection)

    print()
    print("=" * 70)
    print(f"Collected {len(all_videos)} videos.")
    print("=" * 70)


if __name__ == "__main__":
    main()