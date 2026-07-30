# Kinetiq Story — Daily Automation Pipeline

Runs every morning on GitHub's free servers and produces one finished,
ready-to-upload vertical video: topic picked → script written → voiceover
generated → visuals fetched → video assembled → uploaded to your Google
Drive, along with a metadata/editing checklist file.

## What this actually does (read this before you set it up)

Everything below is genuinely free, no credit card needed anywhere.

**Visuals default to AI-generated images** via Pollinations.ai (free, no
API key at all) — closer to your original AI-art style than stock
footage. Be clear-eyed about the real limits of this, though:
- Pollinations generates **static images, not video clips.** The pipeline
  applies a slow Ken Burns zoom/pan to each image so it still feels
  kinetic, but it's not the same as a moving AI-generated scene.
- There is still no free API for actual AI *video* generation (Meta AI,
  Sora, Runway, etc. all require paid access or have no public API at
  all) — if you ever want real AI video clips, that's the one piece that
  would need a paid tool.
- Free image quality/consistency will vary more than a paid model — treat
  each day's output as a first draft and swap out any segment that comes
  out looking wrong before you post.
- If you'd rather use real stock footage instead, set
  `visuals.provider: "pexels"` (or `"pixabay"`) in `config.yaml` — both
  paths are built in and you can switch anytime.

| Step | Tool | Cost |
|---|---|---|
| Topic picking | Reddit + Hacker News, boosted by your own channel's history (YouTube Data API) | Free, no key for Reddit/HN; free API key for YouTube |
| Topic research | Wikipedia REST API — grounds the script in real facts | Free, no key |
| Script writing | Google Gemini free tier *or* Groq free tier | Free tier |
| Voiceover | `edge-tts` (Microsoft neural voices, incl. Christopher) | Free, no key |
| Visuals | Pollinations.ai AI images (default) *or* Pexels/Pixabay stock footage | Free, no key for Pollinations; free tier for Pexels/Pixabay |
| Assembly | `moviepy` (runs locally in the Action) | Free |
| Hosting/scheduling | GitHub Actions | Free for public repos |
| Delivery | Google Drive API (service account) | Free tier |

## One-time setup

### 1. Create the repo
Push this folder to a **public** GitHub repo (public repos get unlimited
free Actions minutes; private repos get ~2,000 free minutes/month, which
is still enough for one ~15-minute run per day).

### 2. Get your free API keys

**LLM (pick ONE):**
- Gemini: go to https://aistudio.google.com/apikey → create a free API key.
- Groq: go to https://console.groq.com/keys → create a free API key.

**Visuals (optional — only needed if you switch away from the default):**
The default (`visuals.provider: "ai"`) needs no key at all — Pollinations.ai
is free and keyless. Only get one of these if you set the provider to
stock footage instead:
- Pexels: https://www.pexels.com/api/ → sign up, copy your API key.
- Pixabay: https://pixabay.com/api/docs/ → sign up, copy your API key.

**YouTube Data API (for channel-history-based topic scoring):**
1. In the same Google Cloud project you'll create for Drive below, search
   "YouTube Data API v3" and click **Enable**.
2. Go to APIs & Services → Credentials → **Create Credentials → API key**.
   Copy it.
3. Find your channel ID: YouTube Studio → Settings → Channel → Advanced
   settings, or from your channel's URL if it contains `/channel/UC...`.
4. Put the channel ID in `config.yaml` under `channel.youtube_channel_id`.
   If you skip this, the pipeline just falls back to generic trending
   topics without the channel-history boost — nothing breaks.

**Google Drive:**
1. Go to https://console.cloud.google.com → create a project (free).
2. Enable the "Google Drive API" for that project.
3. Create a Service Account (IAM & Admin → Service Accounts).
4. Create a JSON key for it and download the file.
5. Open the JSON file, copy its full contents.
6. In Google Drive, create a folder for your videos, share it with the
   service account's email (looks like `xxxx@yyyy.iam.gserviceaccount.com`)
   as **Editor**, and copy the folder's ID from its URL
   (`drive.google.com/drive/folders/`**`THIS_PART`**).

### 3. Add secrets to your GitHub repo
Go to your repo → Settings → Secrets and variables → Actions, and add:

| Name | Value |
|---|---|
| `LLM_API_KEY` | your Gemini or Groq key |
| `YOUTUBE_API_KEY` | your YouTube Data API key (optional — enables channel-history boost) |
| `PEXELS_API_KEY` | your Pexels key (or leave blank if using Pixabay) |
| `PIXABAY_API_KEY` | your Pixabay key (or leave blank if using Pexels) |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | the full contents of the service account JSON file |
| `GDRIVE_FOLDER_ID` | the Drive folder ID |

Also add one repo **variable** (not secret) called `LLM_PROVIDER` set to
either `gemini` or `groq`, matching whichever key you added.

### 4. Add an ambience track
Drop a free, no-instrument ambient/drone/brown-noise mp3 into
`assets/ambience/brown_noise.mp3` — see that folder's README for free
sources. The pipeline still runs without it, just silently skips ambience.

### 5. Turn it on
Go to the Actions tab in your repo, enable workflows if prompted, and
either wait for tomorrow's 06:00 Bangladesh-time run or trigger it now
manually via "Run workflow".

## Running it locally (to test before relying on the schedule)
```bash
pip install -r requirements.txt
export LLM_PROVIDER=gemini
export LLM_API_KEY=your_key
export PEXELS_API_KEY=your_key
export GOOGLE_SERVICE_ACCOUNT_JSON="$(cat path/to/service-account.json)"
export GDRIVE_FOLDER_ID=your_folder_id
python src/main.py
```

## Tuning the style
Everything about the scripting rules — segment count, word counts,
forbidden words, hook style, topic scoring keywords — lives in
`config.yaml`. Edit it any time without touching code.

## New: Google Flow prompts + humanized voice + platform metadata

Three additions to the pipeline, on top of everything above:

**1. Humanized, emotion-varied voiceover.** The script generator now
tags every segment with an emotion (urgent, tense, hushed, authoritative,
alarmed, grave, resolute), and `tts.py` nudges rate/pitch/volume per tag
so the delivery doesn't sound flat. The voice itself (Christopher) stays
100% consistent throughout — only the delivery varies. Honest limit:
true Azure neural voice *styles* (studio-grade emotional acting) require
a paid Azure subscription; this is a free approximation via prosody, not
the same thing.

**2. Google Flow prompt generation — manual step, by design.**
`generate_flow_prompts.py` writes `output/google_flow_prompts.txt`: one
JSON block per 10-second window (Flow's own limit), grounded in your
actual script so the described scene matches what's being said at that
moment, with the main subject/color palette kept identical across all
blocks for visual consistency. **You paste these into Google Flow
yourself, one at a time, in your own browser.** This is NOT automated
further, on purpose:
- Google Flow has no public API — it's a browser product tied to a
  Google AI Pro/Ultra subscription (a small monthly allowance is free,
  heavier use costs money).
- The only way to "automate" clicking inside Flow is browser-automation
  tools that require your personal Google login inside the automation —
  doing that in a public GitHub Actions run would expose your Google
  credentials in shared infrastructure. That's a real account-security
  risk, so this pipeline deliberately stops at generating the prompt
  text and leaves the actual generation to you, manually, safely logged
  into your own account.

**3. Platform metadata generation.** `generate_platform_metadata.py`
writes `output/platform_metadata.txt` with ready-to-paste title,
description, tags/hashtags, and captions separately for YouTube, TikTok,
Instagram, and Facebook — uploaded to your Drive folder alongside the
video every day.

## Known limitations, honestly
- **AI visuals are static images with a zoom/pan effect, not moving AI video** — no free tool generates real AI video clips today.
- **No true creative judgment** — the topic scorer is keyword-based, not
  a guarantee of quality; skim the daily output before posting.
- **LLM free tiers have rate limits.** One video/day is comfortably within
  both Gemini's and Groq's free daily quotas as of this writing, but check
  current limits on their sites if you ever see failures.
- **Nothing here can guarantee views.** This solves the "I don't have time
  to script/edit/voice everything by hand" problem — it doesn't replace
  judgment about what topics and hooks actually retain viewers.
