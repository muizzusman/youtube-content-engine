import os
from typing import Any

import requests

BASE_URL = "https://www.googleapis.com/youtube/v3"

class YouTubeAPIError(RuntimeError):
    """Raised when the YouTube API returns an error."""

class YouTubeClient:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("YOUTUBE_API_KEY")

        if not self.api_key:
            raise RuntimeError(
                "YOUTUBE_API_KEY is missing from the environment."
            )

        self.session = requests.Session()

    def get(
        self,
        endpoint: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        params = {
            **params,
            "key": self.api_key,
        }

        url = f"{BASE_URL}/{endpoint}"

        response = self.session.get(
            url,
            params=params,
            timeout=30,
        )

        if not response.ok:
            try:
                error_data = response.json()
            except ValueError:
                error_data = response.text

            raise YouTubeAPIError(
                f"YouTube API request failed "
                f"({response.status_code}): {error_data}"
            )

        return response.json()

    def get_channel_by_handle(self, handle: str) -> dict[str, Any]:
        return self.get(
            "channels",
            {
                "part": "snippet,contentDetails,statistics",
                "forHandle": handle,
            },
        )

    def get_uploads(
        self,
        uploads_playlist_id: str,
        limit: int = 10,
    ) -> dict[str, Any]:
        return self.get(
            "playlistItems",
            {
                "part": "snippet,contentDetails",
                "playlistId": uploads_playlist_id,
                "maxResults": limit,
            },
        )

    def get_videos(
        self,
        video_ids: list[str],
    ) -> dict[str, Any]:
        if not video_ids:
            return {"items": []}

        return self.get(
            "videos",
            {
                "part": "snippet,contentDetails,statistics",
                "id": ",".join(video_ids),
            },
        )