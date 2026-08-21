import os
import time
from typing import Any

import requests

BASE_URL = "https://www.googleapis.com/youtube/v3"

# Transient failures worth retrying: rate limiting + server-side errors.
# Client errors like 400/403 indicate a bad request or key and are
# raised immediately.
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

MAX_ATTEMPTS = 4
BASE_DELAY_SECONDS = 2.0

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

        last_error: Exception | None = None
        retry_after: str | None = None

        for attempt in range(1, MAX_ATTEMPTS + 1):
            retry_after = None

            try:
                response = self.session.get(
                    url,
                    params=params,
                    timeout=30,
                )
            except requests.RequestException as error:
                last_error = YouTubeAPIError(
                    f"Network error calling {endpoint}: {error}"
                )
            else:
                if response.ok:
                    return response.json()

                try:
                    error_data = response.json()
                except ValueError:
                    error_data = response.text

                last_error = YouTubeAPIError(
                    f"YouTube API request failed "
                    f"({response.status_code}): {error_data}"
                )

                if response.status_code not in RETRYABLE_STATUS_CODES:
                    raise last_error

                # Honor the server's own backoff hint when present
                retry_after = response.headers.get("Retry-After")

            if attempt < MAX_ATTEMPTS:
                try:
                    delay = float(retry_after)
                except (TypeError, ValueError):
                    delay = BASE_DELAY_SECONDS * (2 ** (attempt - 1))

                print(
                    f"    {endpoint} failed, retrying in {delay:.0f}s "
                    f"(attempt {attempt}/{MAX_ATTEMPTS})..."
                )
                time.sleep(delay)

        raise last_error

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