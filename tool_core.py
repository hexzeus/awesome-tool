import os
import random
import httpx
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Default Claude key (your private one) — loaded from environment
CLAUDE_KEY = os.getenv("ANTHROPIC_API_KEY")

CTAS = [
    "Save this post — you’ll need it.",
    "Tag someone who needs this.",
    "Follow for daily frameworks."
]

HASHTAGS = "#LinkedIn #Growth #2025"


def generate_output(
    prompt: str,
    style: str = "professional",
    user_ai_key: str | None = None,
    preferred_model: str = "claude-3-5-sonnet-20240620"
):
    """
    Main text-generation function.
    - If the user provides their own AI key, use it.
    - Otherwise use your server-side Anthropic key safely loaded from .env.
    """

    # Choose which key to use
    key_to_use = user_ai_key or CLAUDE_KEY

    if not key_to_use:
        return "Error: No AI key available. Add ANTHROPIC_API_KEY to your .env file."

    print(f"POSTFORGE: Using {'user' if user_ai_key else 'server'} Claude key")

    # Anthropic API call
    try:
        response = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": key_to_use,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
                "anthropic-beta": "max-tokens-3-5-sonnet-2024-07-15"
            },
            json={
                "model": preferred_model,
                "max_tokens": 1500,
                "temperature": 0.9,
                "system": (
                    "You are the best LinkedIn ghostwriter alive. "
                    "You write viral, bold, high-engagement posts with story hooks, "
                    "controversial takes, and powerful CTAs."
                ),
                "messages": [
                    {
                        "role": "user",
                        "content": f"Write a viral LinkedIn post about: {prompt}. "
                                   f"Style: {style}. Make it go absolutely nuclear."
                    }
                ]
            },
            timeout=40.0
        )

        if response.status_code == 200:
            result = response.json()["content"][0]["text"]
            return (
                result
                + "\n\n"
                + random.choice(CTAS)
                + "\n\n"
                + f"{HASHTAGS} — POSTFORGE NUCLEAR EDITION"
            )

        else:
            return f"Claude error {response.status_code}: {response.text}"

    except Exception as e:
        return f"Request failed: {str(e)}"
