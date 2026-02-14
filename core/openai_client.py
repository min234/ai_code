# ai_code/core/openai_client.py
from __future__ import annotations

import os
import json
from typing import Any, Dict, Optional

from openai import OpenAI
from dotenv import load_dotenv

_client: OpenAI | None = None

load_dotenv(override=True)


def get_client() -> OpenAI:
    """
    Initializes and returns a singleton OpenAI client.
    It reads the API key from the "GPT40_API_KEY" or "OPENAI_API_KEY" environment variables.
    """
    global _client
    if _client is None:
        api_key = os.getenv("GPT40_API_KEY") or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY or GPT40_API_KEY environment variable is not set."
            )
        _client = OpenAI(api_key=api_key)
    return _client


def ask_model(
    system_prompt: str,
    user_prompt: str,
    model: str = "gpt-4o",
    response_format: Optional[str] = None,
) -> Dict[str, Any] | str:
    """
    Sends a request to the OpenAI API and returns the response.

    Args:
        system_prompt: The system message to set the context for the model.
        user_prompt: The user's message.
        model: The model to use for the request.
        response_format: The desired response format (e.g., "json_object").

    Returns:
        If response_format is "json_object", returns a dictionary.
        Otherwise, returns the text content of the response.
    """
    client = get_client()

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    request_params: dict[str, Any] = {"model": model, "messages": messages}

    if response_format == "json_object":
        request_params["response_format"] = {"type": "json_object"}

    response = client.chat.completions.create(**request_params)  # type: ignore[arg-type]

    content = response.choices[0].message.content
    if content is None:
        raise ValueError("Received an empty response from the model.")

    if response_format == "json_object":
        return json.loads(content)
    else:
        return content
