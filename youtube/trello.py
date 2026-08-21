import os

import requests

BASE_URL = "https://api.trello.com/1"


def get_trello_credentials() -> dict:
    api_key = os.getenv("TRELLO_API_KEY")
    token = os.getenv("TRELLO_TOKEN")
    list_id = os.getenv("TRELLO_LIST_ID")

    missing = [
        name for name, value in [
            ("TRELLO_API_KEY", api_key),
            ("TRELLO_TOKEN", token),
            ("TRELLO_LIST_ID", list_id),
        ]
        if not value
    ]

    if missing:
        raise RuntimeError(
            f"Missing Trello environment variables: {', '.join(missing)}"
        )

    return {
        "api_key": api_key,
        "token": token,
        "list_id": list_id,
    }


def build_card_description(video: dict, label: str) -> str:
    return (
        f"**{label}**\n\n"
        f"**Original title:** {video['title']}\n"
        f"**Channel:** {video['channel_name']}\n"
        f"**Format:** {video['format']}\n"
        f"**Video:** {video['video_url']}\n\n"
        f"**Technique:** {video.get('technique_used', 'n/a')}\n"
        f"**Why it works:** {video.get('title_rationale', 'n/a')}\n\n"
        f"**Topic:** {video.get('topic', 'n/a')}\n"
        f"**Hook:** {video.get('hook', 'n/a')}\n"
        f"**Emotional driver:** {video.get('emotional_driver', 'n/a')}\n"
    )


def create_trello_card(video: dict, label: str) -> dict:
    creds = get_trello_credentials()

    response = requests.post(
        f"{BASE_URL}/cards",
        params={
            "key": creds["api_key"],
            "token": creds["token"],
            "idList": creds["list_id"],
            "name": video.get("optimized_title") or video["title"],
            "desc": build_card_description(video, label),
            "urlSource": video["video_url"],
        },
        timeout=30,
    )

    if not response.ok:
        raise RuntimeError(
            f"Trello card creation failed "
            f"({response.status_code}): {response.text}"
        )

    return response.json()


def push_winners_to_trello(
    performance_winner: dict,
    opportunity_winner: dict,
) -> None:
    print()
    print("Pushing winners to Trello...")

    perf_card = create_trello_card(performance_winner, "PERFORMANCE WINNER")
    print(f"  Created: {perf_card['name']}")
    print(f"  {perf_card['shortUrl']}")

    opp_card = create_trello_card(opportunity_winner, "OPPORTUNITY WINNER")
    print(f"  Created: {opp_card['name']}")
    print(f"  {opp_card['shortUrl']}")