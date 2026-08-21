from youtube.llm import BULK_MODELS, ask_json_resilient

PATTERN_SYSTEM_PROMPT_TEMPLATE = """
You are a YouTube trend analyst. You will receive a list of video titles
and topics from {channel_count} different channels.

Identify recurring patterns that appear independently across MULTIPLE
different channels — not patterns that only repeat within one channel.

For each pattern found, return:
- pattern_name: a short label for the pattern
- description: what the pattern is
- channels_involved: list of channel names showing this pattern
- example_titles: list of 2-4 example titles that fit this pattern
- strength: "emerging", "moderate", or "strong" based on how many
  channels show it

Respond ONLY with a JSON object with one field "patterns", which is
a list of pattern objects as described above. Return at most 5 patterns,
ranked by strength. If no clear cross-channel pattern exists, return
an empty list.
"""


def build_patterns_prompt(metrics: list[dict]) -> str:
    lines = []

    for m in metrics:
        topic = m.get("topic", "")
        lines.append(f"- [{m['channel_name']}] {m['title']} (topic: {topic})")

    return "\n".join(lines)


def build_patterns_system_prompt(metrics: list[dict]) -> str:
    channel_count = len({m["channel_name"] for m in metrics})

    return PATTERN_SYSTEM_PROMPT_TEMPLATE.format(
        channel_count=channel_count,
    )


def detect_cross_channel_patterns(client, metrics: list[dict]) -> list[dict]:
    result = ask_json_resilient(
        client,
        system_prompt=build_patterns_system_prompt(metrics),
        user_prompt=build_patterns_prompt(metrics),
        models=BULK_MODELS,
    )

    return result.get("patterns", [])