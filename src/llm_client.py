"""
llm_client.py
Shared free-tier LLM call helper (Gemini or Groq) used by every module that
needs to call an LLM: generate_script.py, generate_flow_prompts.py,
generate_platform_metadata.py, and fetch_topics.py's reframing step.
"""

import os
import time
import requests


def call_llm(system_prompt, user_prompt, json_mode=True):
    provider = os.environ.get("LLM_PROVIDER", "gemini").lower()
    api_key = os.environ["LLM_API_KEY"]

    if provider == "gemini":
        return _call_gemini(system_prompt, user_prompt, api_key, json_mode)
    elif provider == "groq":
        return _call_groq(system_prompt, user_prompt, api_key, json_mode)
    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {provider}")


# Trimmed to model names that are ACTUALLY available on the free tier for
# this project (gemini-2.5-flash / gemini-2.0-flash consistently 404'd —
# not available on this key/region, so no point burning attempts on them).
GEMINI_MODEL_CANDIDATES = [
    "gemini-flash-latest",
    "gemini-pro-latest",
]

# On a 429 (rate limit), the model itself isn't broken — the free tier's
# per-minute quota is just temporarily exhausted. Waiting briefly and
# retrying the SAME model is far more likely to succeed than immediately
# jumping to a different model (which shares the same per-project quota
# anyway on Gemini's free tier).
RATE_LIMIT_BACKOFF_SECONDS = [15, 30]


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
                    break  # no point retrying a model that doesn't exist — move to next model

                if resp.status_code == 429:
                    last_error = f"429 for {model_name}"
                    if backoff_attempt < len(RATE_LIMIT_BACKOFF_SECONDS):
                        wait_s = RATE_LIMIT_BACKOFF_SECONDS[backoff_attempt]
                        print(f"[llm_client] Rate limited on '{model_name}', "
                              f"waiting {wait_s}s before retry ({backoff_attempt + 1}/{len(RATE_LIMIT_BACKOFF_SECONDS)})...")
                        time.sleep(wait_s)
                        continue  # retry the SAME model after waiting
                    else:
                        print(f"[llm_client] Still rate limited on '{model_name}' after backoff, trying next model...")
                        break

                resp.raise_for_status()
                data = resp.json()
                print(f"[llm_client] Used Gemini model: {model_name}")
                return data["candidates"][0]["content"]["parts"][0]["text"]

            except requests.exceptions.HTTPError as e:
                last_error = str(e)
                print(f"[llm_client] Model '{model_name}' failed ({e}), trying next candidate...")
                break

    raise RuntimeError(
        f"All Gemini model candidates failed. Last error: {last_error}. "
        f"Tried: {GEMINI_MODEL_CANDIDATES}"
    )


def _call_groq(system_prompt, user_prompt, api_key, json_mode):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.8,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


def clean_json_text(raw):
    """Strips markdown code fences some models add despite instructions not to."""
    return raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
