import json
import os
import time

from groq import Groq, RateLimitError

DEFAULT_MODEL = "openai/gpt-oss-120b"


def get_client() -> Groq:
    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        raise RuntimeError("GROQ_API_KEY is missing from the environment.")

    return Groq(api_key=api_key)


def _parse_reset_value(value: str) -> float:
    value = (value or "").strip()
    total = 0.0
    num = ""

    for ch in value:
        if ch.isdigit() or ch == ".":
            num += ch
        elif ch == "m":
            total += float(num or 0) * 60
            num = ""
        elif ch == "s":
            total += float(num or 0)
            num = ""

    return total


def _proactive_pace(headers) -> None:
    try:
        remaining_tokens = int(headers.get("x-ratelimit-remaining-tokens", 999999))
        remaining_requests = int(headers.get("x-ratelimit-remaining-requests", 999999))

        reset_tokens = headers.get("x-ratelimit-reset-tokens")
        reset_requests = headers.get("x-ratelimit-reset-requests")

        if remaining_tokens < 1500 and reset_tokens:
            wait = _parse_reset_value(reset_tokens)
            if wait > 0:
                print(f"    [pacing] {remaining_tokens} tokens left, waiting {wait:.1f}s")
                time.sleep(wait)
                return

        if remaining_requests < 3 and reset_requests:
            wait = _parse_reset_value(reset_requests)
            if wait > 0:
                print(f"    [pacing] {remaining_requests} requests left, waiting {wait:.1f}s")
                time.sleep(wait)

    except Exception:
        pass


def ask_json(
    client: Groq,
    system_prompt: str,
    user_prompt: str,
    model: str = DEFAULT_MODEL,
    max_retries: int = 6,
) -> dict:
    last_error = None

    for attempt in range(max_retries):
        try:
            raw = client.chat.completions.with_raw_response.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.4,
            )

            completion = raw.parse()
            content = completion.choices[0].message.content

            _proactive_pace(raw.headers)

            try:
                return json.loads(content)
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"Model did not return valid JSON:\n{content}"
                ) from error

        except RateLimitError as error:
            last_error = error
            wait_time = 15

            try:
                wait_time = float(
                    error.response.headers.get("retry-after", wait_time)
                )
            except Exception:
                pass

            print(f"    Rate limited on {model}, waiting {wait_time:.1f}s (attempt {attempt + 1}/{max_retries})...")
            time.sleep(wait_time + 1)

    raise RuntimeError(
        f"Failed after {max_retries} retries on {model}: {last_error}"
    )

FALLBACK_MODELS = [
    "openai/gpt-oss-120b",
    "llama-3.3-70b-versatile",
    "openai/gpt-oss-20b",
    "llama-3.1-8b-instant",
]

def ask_json_resilient(
    client: Groq,
    system_prompt: str,
    user_prompt: str,
    models: list[str] = None,
) -> dict:
    """
    Tries each model in order. If one is fully exhausted (all retries
    within ask_json failed), moves to the next model instead of giving
    up entirely. This spreads load across separate rate-limit pools,
    since Groq's limits apply per-model, not per-account.
    """

    models = models or FALLBACK_MODELS
    last_error = None

    for model in models:
        try:
            return ask_json(
                client,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model=model,
            )
        except RuntimeError as error:
            last_error = error
            print(f"    [{model} exhausted, falling back to next model]")
            continue

    raise RuntimeError(
        f"All fallback models exhausted. Last error: {last_error}"
    )