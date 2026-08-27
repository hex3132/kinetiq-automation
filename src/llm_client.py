"""
llm_client.py
Shared free-tier LLM call helper used by every module that needs an LLM.

Automatic fallback: if LLM_PROVIDER is "gemini" and Gemini fails entirely
(daily quota exhausted, servers down, timeouts, etc.) AND a GROQ_API_KEY
secret is also set, this automatically retries the same request on Groq.

Both Gemini and Groq model candidate lists are tried in order and skip
past any model that's been renamed/deprecated (404), so a provider
retiring a model name doesn't break the whole pipeline.
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
                        print(f"[llm_client] Got {resp.status_code} on '{model_name}', "
                              f"waiting {wait_s}s before retry ({backoff_attempt + 1}/{len(RATE_LIMIT_BACKOFF_SECONDS)})...")
                        time.sleep(wait_s)
                        continue
                    else:
                        print(f"[llm_client] Still failing on '{model_name}' after backoff, trying next model...")
                        break

                resp.raise_for_status()
                data = resp.json()
                print(f"[llm_client] Used Gemini model: {model_name}")
                return data["candidates"][0]["content"]["parts"][0]["text"]

            except requests.exceptions.HTTPError as e:
                last_error = str(e)
                print(f"[llm_client] Model '{model_name}' failed ({e}), trying next candidate...")
                break
            except requests.exceptions.RequestException as e:
                last_error = str(e)
                print(f"[llm_client] Network error on '{model_name}' ({e}), trying next candidate...")
                break

    raise RuntimeError(
        f"All Gemini model candidates failed. Last error: {last_error}. "
        f"Tried: {GEMINI_MODEL_CANDIDATES}"
    )


GROQ_MODEL_CANDIDATES = [
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "qwen/qwen3.6-27b",
]


def _call_groq(system_prompt, user_prompt, api_key, json_mode):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    # NOT sending response_format here — newer gpt-oss/qwen models on Groq
    # return 400 Bad Request with response_format={"type":"json_object"}.
    # Our system prompts already explicitly instruct "output ONLY valid JSON",
    # and clean_json_text() strips any stray markdown fences, so plain
    # prompting is enough without forcing that (currently unsupported) param.
    last_error = None
    for model_name in GROQ_MODEL_CANDIDATES:
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.8,
        }

        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=60)
            if resp.status_code == 404:
                print(f"[llm_client] Groq model '{model_name}' not found, trying next candidate...")
                last_error = f"404 for {model_name}"
                continue
            if resp.status_code == 400:
                print(f"[llm_client] Groq model '{model_name}' rejected the request (400: {resp.text[:200]}), trying next candidate...")
                last_error = f"400 for {model_name}"
                continue
            resp.raise_for_status()
            data = resp.json()
            print(f"[llm_client] Used Groq model: {model_name}")
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            last_error = str(e)
            print(f"[llm_client] Groq model '{model_name}' failed ({e}), trying next candidate...")
            continue

    raise RuntimeError(
        f"All Groq model candidates failed. Last error: {last_error}. "
        f"Tried: {GROQ_MODEL_CANDIDATES}"
    )

def clean_json_text(raw):
    return raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
