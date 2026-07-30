"""
llm_client.py
Shared free-tier LLM call helper (Gemini or Groq) used by every module that
needs to call an LLM: generate_script.py, generate_flow_prompts.py, and
generate_platform_metadata.py. Keeping this in one place means you only
configure your provider/key once.
"""

import os
import requests


def call_llm(system_prompt, user_prompt, json_mode=True):
    """
    Calls whichever provider is set in LLM_PROVIDER ("gemini" or "groq"),
    using the LLM_API_KEY secret. Returns the raw text response.
    """
    provider = os.environ.get("LLM_PROVIDER", "gemini").lower()
    api_key = os.environ["LLM_API_KEY"]

    if provider == "gemini":
        return _call_gemini(system_prompt, user_prompt, api_key, json_mode)
    elif provider == "groq":
        return _call_groq(system_prompt, user_prompt, api_key, json_mode)
    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {provider}")


def _call_gemini(system_prompt, user_prompt, api_key, json_mode):
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-1.5-flash:generateContent?key={api_key}"
    )
    generation_config = {"temperature": 0.8}
    if json_mode:
        generation_config["response_mime_type"] = "application/json"

    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"parts": [{"text": user_prompt}]}],
        "generationConfig": generation_config,
    }
    resp = requests.post(url, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]


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
