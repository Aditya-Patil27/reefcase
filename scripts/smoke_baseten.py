"""Quick smoke test: verify the Baseten API key works with the hackathon model.

Usage:
    uv run python scripts/smoke_baseten.py

Reads REEFCASE_LLM_AGENT_* from .env. Exits 0 on success, 1 on failure.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def main() -> None:
    base_url = os.environ.get("REEFCASE_LLM_AGENT_BASE_URL", "")
    api_key = os.environ.get("REEFCASE_LLM_AGENT_API_KEY", "")
    model = os.environ.get("REEFCASE_LLM_AGENT_MODEL", "")

    if not all([base_url, api_key, model]):
        print("ERROR: set REEFCASE_LLM_AGENT_{BASE_URL,API_KEY,MODEL} in .env")
        sys.exit(1)

    if api_key == "PASTE_YOUR_BASETEN_KEY_HERE":
        print("ERROR: replace the placeholder API key in .env with your real Baseten key")
        sys.exit(1)

    from openai import OpenAI

    client = OpenAI(base_url=base_url, api_key=api_key)

    print(f"Calling {model} at {base_url} ...")
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Say 'reef check ok' and nothing else."}],
            max_tokens=20,
        )
        text = response.choices[0].message.content or ""
        print(f"Response: {text}")
        print(f"Model: {response.model}")
        print(f"Tokens: {response.usage}")
        print("SUCCESS: Baseten key works.")
    except Exception as e:
        print(f"FAILED: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
