from youtube.llm import BULK_MODELS, ask_json_resilient

BATCH_SYSTEM_PROMPT = """
You are a YouTube content strategist analyzing video titles and metadata.

You will receive a list of videos, each with a video_id. For EACH video
in the list, identify:
- topic: what the video is actually about, in plain terms
- hook: what makes the premise immediately interesting
- emotional_driver: one of curiosity, fear, aspiration, disbelief,
  competition, outrage, surprise, status, novelty, nostalgia, or humor
- information_gap: what the viewer wants to know but isn't told by the title
- title_mechanism: one of challenge, contradiction, curiosity_gap,
  unexpected_result, confession, transformation, extreme_comparison,
  countdown, warning, reveal
- replicability: a 1-10 score for how easily another creator could
  build a similar video around this concept

Respond ONLY with a JSON object with one field "results", which is
a list of objects, ONE PER INPUT VIDEO, in any order, each containing
EXACTLY these fields: video_id, topic, hook, emotional_driver,
information_gap, title_mechanism, replicability.

Every video_id you were given must appear exactly once in "results".
"""


def build_batch_prompt(videos: list[dict]) -> str:
    lines = []

    for v in videos:
        lines.append(
            f"video_id: {v['video_id']} | "
            f"channel: {v['channel_name']} | "
            f"title: {v['title']} | "
            f"format: {v['format']} | "
            f"views: {v['views']}"
        )

    return "\n".join(lines)


def analyze_concepts(client, videos: list[dict]) -> list[dict]:
    """
    Analyze a small list of videos in a single LLM request and merge
    the concept fields into each video dict.
    """

    result = ask_json_resilient(
        client,
        system_prompt=BATCH_SYSTEM_PROMPT,
        user_prompt=build_batch_prompt(videos),
        models=BULK_MODELS,
    )

    by_id = {}

    for item in result.get("results", []):
        video_id = item.get("video_id")
        if video_id:
            by_id[video_id] = item

    return [
        {**video, **by_id.get(video["video_id"], {})}
        for video in videos
    ]
