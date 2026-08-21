import json
import os
import time

from google import genai
from google.genai import types
from google.genai.errors import APIError, ClientError

# Title generation runs at most twice per run, so it leads with the
# strongest model and treats quality as the priority.
CREATIVE_MODELS = [
    "models/gemini-3.7-flash",  # newest, most capable Flash
    "models/gemini-3.6-flash",  # well-established, replaces deprecated 2.5-flash
]

# Concept extraction and pattern detection issue many calls per run, so
# they lead with lightweight variants that carry higher free-tier daily
# quotas, keeping the flagship model off the hot path.
BULK_MODELS = [
    "models/gemini-3.5-flash-lite",  # newest lightweight, high free-tier quota
    "models/gemini-3.1-flash-lite",  # lightweight, well-established
    "models/gemini-2.5-flash-lite",  # older lightweight safety net
    "models/gemini-3.6-flash",       # mid-tier fallback
    "models/gemini-3.7-flash",       # last resort
]

RATE_LIMIT_WAIT_SECONDS = 10


def get_client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is missing from the environment.")

    return genai.Client(api_key=api_key)


def ask_json(
    client: genai.Client,
    system_prompt: str,
    user_prompt: str,
    model: str = CREATIVE_MODELS[0],
    max_retries: int = 2,
) -> dict:
    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            response = client.models.generate_content(
                model=model,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    response_mime_type="application/json",
                    temperature=0.4,
                ),
            )

            try:
                return json.loads(response.text)
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"Model did not return valid JSON:\n{response.text}"
                ) from error

        # Fix: Catch generic APIError alongside ClientError for better safety
        except (ClientError, APIError) as error:
            last_error = error

            # google-genai errors expose the HTTP status as an int on .code;
            # RESOURCE_EXHAUSTED covers gRPC-style messages without a code.
            status_code = getattr(error, "code", None)
            is_rate_limited = (
                status_code == 429
                or "RESOURCE_EXHAUSTED" in str(error)
            )

            # Structural errors (403/404) bubble up immediately so the
            # caller can fall through to the next model. On rate limits,
            # retry once with a short wait, then give up on this model —
            # long per-model waits only burn wall time when the daily
            # quota (not the per-minute window) is exhausted.
            if not is_rate_limited:
                raise

            if attempt < max_retries:
                print(
                    f"    Rate limited on {model}, retrying in "
                    f"{RATE_LIMIT_WAIT_SECONDS}s "
                    f"(attempt {attempt}/{max_retries})..."
                )
                time.sleep(RATE_LIMIT_WAIT_SECONDS)

    raise RuntimeError(
        f"Rate limited on {model} after {max_retries} attempts: {last_error}"
    )


def ask_json_resilient(
    client: genai.Client,
    system_prompt: str,
    user_prompt: str,
    models: list[str] = None,
) -> dict:
    # Creative calls (titles) default to the quality-first chain; bulk
    # callers pass BULK_MODELS explicitly.
    models = models or CREATIVE_MODELS
    last_error = None

    for model in models:
        try:
            return ask_json(client, system_prompt, user_prompt, model=model)
        # Fix: Catch both RuntimeError and ClientError so invalid model names 
        # or auth errors don't instantly kill the script before checking fallbacks
        except (RuntimeError, ClientError, APIError) as error:
            last_error = error
            print(f"    [{model} failed or exhausted, falling back to next model]")
            continue

    raise RuntimeError(
        f"All fallback models exhausted. Last error: {last_error}"
    )
