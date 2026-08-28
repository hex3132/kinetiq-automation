"""
llm_client.py
Shared free-tier LLM call helper used by every module that needs an LLM.

Automatic fallback: if LLM_PROVIDER is "gemini" and Gemini fails entirely
(daily quota exhausted, servers down, timeouts, etc.) AND a GROQ_API_KEY
secret is also set, this automatically retries the same request on Groq.

Both Gemini and Groq model candidate lists are tried in order and skip
past any model that's been renamed/deprecated (404), rejects the request
(400), or is too large for the free tier (413), so a provider retiring or
restricting a model doesn't break the whole pipeline.
"""

import os
import time
import requests


def call_llm(system_prompt, user_prompt, json_mode=True):
    provider = os.environ.get("LLM_PROVIDER", "gemini").lower()
    api_key = os.environ["LLM_API_KEY"]

    if provider == "gemini":
        try:
            return _call_gemini(system_prompt, user_prompt, api_key, json_mode)
        except Exception as e:
            groq_key = os.environ.get("GROQ_API_KEY")
            if groq_key:
                print(f"[llm_client] Gemini failed entirely ({e}), falling back to Groq...")
                return _call_groq(system_prompt, user_prompt, groq_key, json_mode)
            raise
    elif provider == "groq":
        return _call_groq(system_prompt, user_prompt, api_key, json_mode)
    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {provider}")


GEMINI_MODEL_CANDIDATES = [
    "gemini-flash-latest",
    "gemini-pro-latest",
]

RETRYABLE_STATUS_CODES = {429, 503}
RATE_LIMIT_BACKOFF_SECONDS = [20, 40, 40]


def _call_gemini(system_prompt, user_prompt, api_key, json_mode):
    generation_config = {"temperature": 0.8}
    if json_mode:
        generation_config["response_mime_type"] = "application/json"

    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"parts": [{"text": user_prompt}]}],
        "generationConfig": generation_config,
    }

    last_error = None
    for model_name in GEMINI_MODEL_CANDIDATES:
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model_name}:generateContent?key={api_key}"
        )

        for backoff_attempt in range(len(RATE_LIMIT_BACKOFF_SECONDS) + 1):
            try:
                resp = requests.post(url, json=payload, timeout=60)

                if resp.status_code == 404:
                    print(f"[llm_client] Model '{model_name}' not found, trying next candidate...")
                    last_error = f"404 for {model_name}"
                    break

                if resp.status_code in RETRYABLE_STATUS_CODES:
                    last_error = f"{resp.status_code} for {model_name}"
                    if backoff_attempt < len(RATE_LIMIT_BACKOFF_SECONDS):
                        wait_s = RATE_LIMIT_BACKOFF_SECONDS[backoff_attempt]
