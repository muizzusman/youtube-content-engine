from youtube.llm import ask_json_resilient

TITLE_SYSTEM_PROMPT = """
You are an expert YouTube title copywriter specializing in
click-through-rate optimization. You have studied thousands of
high-performing titles and know that weak titles merely restate
the topic, while strong titles create genuine tension the viewer
needs to resolve.

You will receive data about a single winning video, including its
original title, topic, hook, emotional driver, information gap, and
title mechanism.

Before writing, think through this internally (do not include it
in your output):
1. What is the single most surprising, specific, or high-stakes
   detail implied by this video's topic and hook?
2. What would make someone stop scrolling specifically for THIS
   video, not just "a video about this topic"?
3. How can the information_gap be sharpened into something concrete
   and specific, rather than vague curiosity?

Then write ONE new title.

Hard rules:
- Do NOT simply turn the topic into a generic question
  ("What is X?", "Why does X happen?", "Is X good?") unless no
  stronger mechanism fits. A generic question is the weakest
  possible output and should be a last resort, not a default.
- Prefer concrete specificity over vague teasing. "The detail
  IGN's trailer confirms fans missed" beats "What's new in the
  trailer?"
- The title must remain factually accurate to the video's actual
  content. Do not invent claims, numbers, or events that aren't
  supported by the original title and topic.
- Lean hard into the identified emotional_driver and
  title_mechanism specifically — don't default to curiosity if a
  stronger driver (status, disbelief, outrage, competition) fits
  better.
- Exploit the information_gap concretely: the viewer should feel
  they're missing something specific, not just "more info."
- Keep it concise: ideally under 70 characters, never over 100.
- Do not use ALL CAPS for more than one word. Avoid excessive
  punctuation (no more than one of ! or ?).
- No misleading or deceptive claims — provocative framing only,
  never false framing.

Respond ONLY with a JSON object containing exactly these fields:
- optimized_title: the new title
- technique_used: the specific psychological technique/mechanism applied
- rationale: one or two sentences on why this title should
  outperform the original
"""


def build_title_prompt(video: dict) -> str:
    return (
        f"Original title: {video['title']}\n"
        f"Channel: {video['channel_name']}\n"
        f"Format: {video['format']}\n"
        f"Topic: {video.get('topic')}\n"
        f"Hook: {video.get('hook')}\n"
        f"Emotional driver: {video.get('emotional_driver')}\n"
        f"Information gap: {video.get('information_gap')}\n"
        f"Title mechanism: {video.get('title_mechanism')}\n"
    )


def generate_optimized_title(client, video: dict) -> dict:
    result = ask_json_resilient(
        client,
        system_prompt=TITLE_SYSTEM_PROMPT,
        user_prompt=build_title_prompt(video),
    )

    return {
        **video,
        "optimized_title": result.get("optimized_title"),
        "technique_used": result.get("technique_used"),
        "title_rationale": result.get("rationale"),
    }