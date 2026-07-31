"""
llm_client.py
Shared free-tier LLM call helper (Gemini or Groq) used by every module that
needs to call an LLM: generate_script.py, generate_flow_prompts.py, and
generate_platform_metadata.py.
"""

import os
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


# Tried in order — if Google renames/retires one, the next is tried
# automatically instead of the whole pipeline failing.
GEMINI_MODEL_CANDIDATES = [
    "gemini-flash-latest",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-pro-latest",
]


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
        try:
            resp = requests.post(url, json=payload, timeout=60)
            if resp.status_code == 404:
                print(f"[llm_client] Model '{model_name}' not found, trying next candidate...")
                last_error = f"404 for {model_name}"
                continue
            resp.raise_for_status()
            data = resp.json()
            print(f"[llm_client] Used Gemini model: {model_name}")
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except requests.exceptions.HTTPError as e:
            last_error = str(e)
            print(f"[llm_client] Model '{model_name}' failed ({e}), trying next candidate...")
            continue

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
