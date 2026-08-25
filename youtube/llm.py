import json
import os
import random
import time

from google import genai
from google.genai import types
from google.genai.errors import APIError, ClientError


# ============================================================
# MODEL CONFIGURATION
# ============================================================

# Used for quality-sensitive calls such as title generation.
# Quality is prioritized over request volume.
CREATIVE_MODELS = [
    "models/gemini-3.7-flash",
    "models/gemini-3.6-flash",
]


# Used for high-volume calls such as concept extraction,
# pattern detection, classification, etc.
#
# Keep the lightweight models on the normal bulk path.
# Higher-capability Flash models are intentionally NOT included
# here so bulk processing does not unnecessarily consume them.
BULK_MODELS = [
    "models/gemini-3.5-flash-lite",
    "models/gemini-3.1-flash-lite",
    "models/gemini-2.5-flash-lite",
]


# Maximum delay between retries.
MAX_BACKOFF_SECONDS = 30


# ============================================================
# CLIENT
# ============================================================

def get_client() -> genai.Client:
    """
    Create and return a Gemini API client using GEMINI_API_KEY.
    """

    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is missing from the environment."
        )

    return genai.Client(api_key=api_key)


# ============================================================
# ERROR HELPERS
# ============================================================

def _get_status_code(error: Exception):
    """
    Safely extract the HTTP status code from a Gemini API error.
    """

    code = getattr(error, "code", None)

    # Some SDK versions may expose a nested response/code structure.
    if code is not None:
        try:
            return int(code)
        except (TypeError, ValueError):
            pass

    return None


def _classify_api_error(error: Exception) -> str:
    """
    Classify a Gemini API error.

    Returns one of:
        - "rate_limit"       -> 429 / quota exhaustion
        - "service_unavailable" -> 503
        - "retryable"        -> other transient-looking errors
        - "fatal"            -> should not be retried
    """

    status_code = _get_status_code(error)
    error_text = str(error).upper()

    # 429: rate limit / quota exhaustion.
    if (
        status_code == 429
        or "RESOURCE_EXHAUSTED" in error_text
        or "RATE LIMIT" in error_text
        or "TOO MANY REQUESTS" in error_text
    ):
        return "rate_limit"

    # 503: Gemini backend temporarily unavailable/overloaded.
    if (
        status_code == 503
        or "503" in error_text
        or "SERVICEUNAVAILABLE" in error_text
        or "SERVICE UNAVAILABLE" in error_text
        or "UNAVAILABLE" in error_text
        or "OVERLOADED" in error_text
    ):
        return "service_unavailable"

    # A few server-side errors can also be transient.
    # Don't immediately abandon a model for these.
    if status_code in (500, 502, 504):
        return "retryable"

    return "fatal"


def _backoff_delay(attempt: int) -> float:
    """
    Exponential backoff with jitter.

    attempt=0 -> ~1 second
    attempt=1 -> ~2 seconds
    attempt=2 -> ~4 seconds
    attempt=3 -> ~8 seconds

    Capped at MAX_BACKOFF_SECONDS.
    """

    base_delay = 2 ** attempt
    jitter = random.uniform(0, 1)

    return min(
        base_delay + jitter,
        MAX_BACKOFF_SECONDS,
    )


# ============================================================
# JSON REQUEST
# ============================================================

def ask_json(
    client: genai.Client,
    system_prompt: str,
    user_prompt: str,
    model: str = CREATIVE_MODELS[0],
    max_retries: int = 4,
) -> dict:
    """
    Send a request to Gemini and return parsed JSON.

    Retry behavior:

        429 -> exponential backoff + retry
        503 -> exponential backoff + retry
        500/502/504 -> exponential backoff + retry
        other API errors -> immediately raise

    Once retries for a model are exhausted, the exception is
    propagated to ask_json_resilient(), which can try the next
    model in the fallback chain.
    """

    last_error = None

    for attempt in range(max_retries):
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

            # Gemini should return JSON because response_mime_type
            # is explicitly set to application/json.
            try:
                return json.loads(response.text)

            except json.JSONDecodeError as error:
                raise ValueError(
                    "Model did not return valid JSON.\n"
                    f"Raw response:\n{response.text}"
                ) from error

        except (ClientError, APIError) as error:
            last_error = error

            error_type = _classify_api_error(error)

            # ------------------------------------------------
            # FATAL ERROR
            # ------------------------------------------------
            #
            # Examples:
            # 400 invalid request
            # 401 authentication problem
            # 403 permission problem
            # 404 model/resource not found
            #
            # Retrying won't fix these.
            if error_type == "fatal":
                raise

            # ------------------------------------------------
            # RETRIES EXHAUSTED
            # ------------------------------------------------

            if attempt >= max_retries - 1:
                break

            # ------------------------------------------------
            # EXPONENTIAL BACKOFF
            # ------------------------------------------------

            delay = _backoff_delay(attempt)

            if error_type == "service_unavailable":
                message = (
                    f"    503 ServiceUnavailable on {model}. "
                    f"Retrying in {delay:.1f}s "
                    f"(attempt {attempt + 1}/{max_retries})..."
                )

            elif error_type == "rate_limit":
                message = (
                    f"    429 Rate/Quota limit on {model}. "
                    f"Retrying in {delay:.1f}s "
                    f"(attempt {attempt + 1}/{max_retries})..."
                )

            else:
                message = (
                    f"    Temporary Gemini error on {model}. "
                    f"Retrying in {delay:.1f}s "
                    f"(attempt {attempt + 1}/{max_retries})..."
                )

            print(message)

            time.sleep(delay)

    # --------------------------------------------------------
    # THIS MODEL IS EXHAUSTED
    # --------------------------------------------------------

    raise RuntimeError(
        f"{model} failed after {max_retries} attempts.\n"
        f"Last error: {last_error}"
    ) from last_error


# ============================================================
# RESILIENT MODEL FALLBACK
# ============================================================

def ask_json_resilient(
    client: genai.Client,
    system_prompt: str,
    user_prompt: str,
    models: list[str] | None = None,
) -> dict:
    """
    Try the supplied models in order.

    Every model gets its own retry cycle inside ask_json().

    Example:

        Model A
          -> retry 503
          -> retry 503
          -> retry 503
          -> retry 503
          -> exhausted

        Model B
          -> retry if necessary
          -> success

    This prevents a single temporary 503 from immediately
    causing the request to jump to another model.
    """

    # Creative callers default to quality-first models.
    # Bulk callers should explicitly pass BULK_MODELS.
    models = models or CREATIVE_MODELS

    if not models:
        raise ValueError("No Gemini models were supplied.")

    last_error = None

    for model in models:
        try:
            print(f"    Trying {model}...")

            return ask_json(
                client=client,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model=model,
            )

        except ValueError:
            # Invalid JSON is a model-response problem rather than
            # an API availability problem. Try the next model.
            last_error = None
            print(
                f"    [{model} returned invalid JSON, "
                f"falling back to next model]"
            )
            continue

        except (RuntimeError, ClientError, APIError) as error:
            last_error = error

            print(
                f"    [{model} failed or was exhausted, "
                f"falling back to next model]"
            )

            continue

    raise RuntimeError(
        "All fallback models exhausted.\n"
        f"Last error: {last_error}"
    ) from last_error