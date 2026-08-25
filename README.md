# YouTube Content Intelligence

## Demo

<!-- TODO(you): record a 30-60s terminal capture of a full run (python main.py),
     convert to GIF, save as docs/demo.gif, then delete this comment and add: ![Terminal run](docs/demo.gif) -->

<!-- TODO(you): screenshot your Trello board showing the winner card,
     save as docs/trello.png, then delete this comment and add: ![Trello winner card](docs/trello.png) -->

Daily automated pipeline that races the latest uploads from competitor gaming
channels against each other, crowns the one that overperformed relative to its
audience size, uses an LLM to reverse-engineer *why* it works — then generates
an optimized title and delivers it to a Trello board as a ready-to-use content
concept.

## How it works

```
YouTube Data API v3 ───> Velocity ranking ───> Gemini LLM ───> Trello card
 (latest upload from     (views/hour per       (concept +      (performance
  each tracked channel)   million subs)         title)          winner)
```

| Stage | Modules | What it does |
|---|---|---|
| 1. Ingest | `youtube/videos.py`, `channels.py`, `parser.py` | Resolve @handles, fetch **only the latest upload** per channel, parse durations, classify short/long (duration + aspect ratio + #shorts tag) |
| 2. Score | `main.py`, `youtube/analysis.py` | Views-per-hour since publish, normalized by subscriber count → velocity index; rank fresh every run (no database) |
| 3. Analyze | `youtube/llm.py`, `concepts.py`, `titles.py` | Concept extraction + optimized title rewriting for **the winner only** (2 LLM calls total) |
| 4. Deliver | `youtube/trello.py` | Push Performance Winner card |

Stateless by design: nothing is stored between runs. Every run compares the
current latest uploads from scratch.

## Scoring

Each video's latest-upload performance is measured as:

```
view_velocity   = views / hours_since_publish          (raw momentum)
velocity_index  = view_velocity / subscribers × 1e6    (ranking metric)
```

`velocity_index` reads as *views per hour per million subscribers*. Ranking on
the subscriber-adjusted figure means a 300K-sub channel can legitimately beat
a 4M-sub channel — it measures overperformance relative to audience size,
not raw reach.

Details that keep comparisons honest:

- Videos younger than 30 minutes are scored as if exactly 30 minutes old, so
  brand-new uploads don't post absurd near-infinite velocities.
- If a channel's latest upload is a **Short**, it stays in the ranking but is
  flagged in the output — Shorts accumulate views far faster than long-form,
  so a Short winning the index should be read with that skew in mind.
- A channel whose fetch fails is skipped with a warning instead of killing
  the run; the race continues with the remaining channels.

The highest velocity index wins. One **Performance Winner** is pushed to
Trello each run.

A YouTube API run costs ~7 quota units (5 channel lookups + 1 playlist call +
1 batched videos call).

## Project structure

```
├── main.py                          # pipeline entrypoint
├── config.json                      # channels to track
├── test_llm.py                      # manual smoke test (lists available models)
├── requirements.txt
├── .env.example                     # copy to .env and fill in your keys
├── .github/
│   └── workflows/daily.yml          # daily scheduled run (GitHub Actions)
└── youtube/
    ├── videos.py         # YouTube Data API v3 client (retries w/ backoff)
    ├── channels.py       # handle → channel resolution
    ├── parser.py         # ISO-8601 duration parsing, format classification
    ├── analysis.py       # time-since-publish helper
    ├── llm.py            # Gemini client (JSON mode, model fallback, retries)
    ├── concepts.py       # concept extraction (single batched request)
    ├── titles.py         # optimized title generation
    └── trello.py         # winner card
```

## Getting started

### Prerequisites

- Python 3.10+
- A [YouTube Data API v3](https://console.cloud.google.com/) key — a full run
  uses ~7 quota units of the free 10k/day
- A [Google AI Studio (Gemini)](https://aistudio.google.com/apikey) API key
  (free tier available)
- [Trello API key + token](https://trello.com/power-ups/admin) and the ID of
  the target list

### 1. Install

```bash
git clone https://github.com/<your-username>/youtube-content-intelligence.git
cd youtube-content-intelligence
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure

```bash
# Windows
copy .env.example .env
# macOS / Linux
cp .env.example .env
```

Fill in `.env`:

| Variable | Where to get it |
|---|---|
| `YOUTUBE_API_KEY` | Google Cloud Console → enable *YouTube Data API v3* → Credentials |
| `GEMINI_API_KEY` | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) |
| `TRELLO_API_KEY` | [trello.com/power-ups/admin](https://trello.com/power-ups/admin) |
| `TRELLO_TOKEN` | Token link next to your API key on the same page |
| `TRELLO_LIST_ID` | Open any card in the target list, append `.json` to its URL, grab `idList` |

Then edit `config.json`:

```json
{
    "channels": [
        "https://www.youtube.com/@somechannel",
        "https://www.youtube.com/@anotherchannel"
    ]
}
```

LLM calls are tiered: concept extraction runs on lightweight flash-lite
variants with higher free-tier daily quotas, while title generation uses the
strongest Flash model. Both fall back through older variants on rate limits —
see `CREATIVE_MODELS` and `BULK_MODELS` in `youtube/llm.py`.

### 3. Run

```bash
python main.py
```

Sample output:

```
======================================================================
Channel: https://www.youtube.com/@gameranxTV
Name: gameranx
Subscribers: 7,800,000
[long ]        481,203 views | 10 Games That ...

====================================================================================================
LATEST-UPLOAD VELOCITY RANKING (views per hour per million subscribers)
====================================================================================================
1. Some Channel (312,000 subs)
       84,112 views in    26.4 h  |  3,185.6 views/hr raw  |  index 10210.00
   This Game Is a Masterpiece...

====================================================================================================
PERFORMANCE WINNER
====================================================================================================
Some Channel | This Game Is a Masterpiece...
Velocity index: 10210.00 | 3,185.6 views/hr | 84,112 views in 26.4 h | https://www.youtube.com/watch?v=...

  Optimized title: The 40-Hour Detail Everyone Missed in This Game
  Technique: Specific Reveal
  Why: Names a tangible detail so viewers know exactly what they'll discover.
```

### 4. Run daily (optional)

A GitHub Actions workflow (`.github/workflows/daily.yml`) runs the pipeline
every day at 20:00 UTC. To enable it, add these repository secrets
(*Settings → Secrets and variables → Actions*):

`YOUTUBE_API_KEY`, `GEMINI_API_KEY`, `TRELLO_API_KEY`, `TRELLO_TOKEN`,
`TRELLO_LIST_ID`

You can also trigger a run manually from the *Actions* tab via
*workflow_dispatch*. To run locally on a schedule instead, use Task Scheduler
(Windows) or cron (macOS/Linux) to invoke `python main.py` periodically.

## Limitations / roadmap

- [x] Shorts detection combines duration (≤180s), thumbnail aspect ratio
      (vertical/square), and `#shorts` hashtags — the Data API has no
      `is_short` flag, so this remains a heuristic
- [x] Retry with exponential backoff on transient YouTube Data API errors
      (429/5xx/network); non-retryable client errors fail fast
- [ ] Velocity measured from a single point in time is *average speed since
      publish*, not current momentum — a video posted yesterday and one
      posted an hour ago accrue views at different decay curves
- [ ] Subscriber counts are rounded by YouTube above ~1K, so the index is
      approximate for very large channels

## License

<!-- TODO(you): pick a license (e.g. MIT), add a LICENSE file, update this section -->
Not yet licensed.
