# YouTube Content Intelligence

## Demo

<!-- TODO(you): record a 30-60s terminal capture of a full run (python main.py),
     convert to GIF, save as docs/demo.gif, then delete this comment and add: ![Terminal run](docs/demo.gif) -->

<!-- TODO(you): screenshot your Trello board showing the two winner cards,
     save as docs/trello.png, then delete this comment and add: ![Trello winner cards](docs/trello.png) -->

Daily automated pipeline that monitors competitor gaming channels on YouTube,
scores their video performance, and uses an LLM to reverse-engineer *why* the
winners work — then generates optimized title ideas and delivers them to a
Trello board as ready-to-use content concepts.

## How it works

```
YouTube Data API v3 ──► SQLite ──► Normalized metrics ──► Gemini LLM ──► Trello cards
 (latest uploads from    (videos,   (velocity, engagement,  (concepts,   (performance +
  N gaming channels)     snapshots) baseline ratio)          patterns,    opportunity
                                                             titles)      winners)
```

| Stage | Modules | What it does |
|---|---|---|
| 1. Ingest | `youtube/videos.py`, `channels.py`, `parser.py` | Resolve @handles, fetch latest uploads, parse durations, classify short/long (duration + aspect ratio + #shorts tag) |
| 2. Store | `youtube/database.py` | Upsert videos, append a stats snapshot per run (time-series) |
| 3. Score | `youtube/analysis.py`, `scoring.py` | View velocity, engagement rate, per-channel/format baselines → breakout score |
| 4. Analyze | `youtube/llm.py`, `concepts.py`, `patterns.py`, `titles.py` | Concept extraction, cross-channel pattern detection, optimized title rewriting |
| 5. Deliver | `youtube/trello.py` | Push Performance Winner + Opportunity Winner cards |

## Scoring

Each metric is min-max normalized across the current run, then blended:

```
breakout_score = 0.45 · baseline_ratio_norm
               + 0.35 · view_velocity_norm
               + 0.20 · engagement_rate_norm
```

- **baseline_ratio** — views ÷ median views of the same channel *and same format*
  (Shorts never compete with long-form). If a channel has only one video in a
  format, the median across all channels for that format is used instead
- **view_velocity** — views per hour since publish
- **engagement_rate** — (likes + comments) ÷ (views + 100). The constant in
  the denominator dampens inflated rates on very low-view videos

Before blending, each metric series has outliers clipped to Tukey fences
(Q1 − 1.5·IQR … Q3 + 1.5·IQR), so a single extreme result can't compress
everyone else's normalized scores. Well-behaved data is left untouched.

Scores are computed per run over that run's videos only, so historical
videos don't skew the normalization.

Two winners are selected each run:

- **Performance Winner** — highest breakout score
- **Opportunity Winner** — most replicable concept (LLM-scored 1–10) among the rest

## Project structure

```
├── main.py                          # pipeline entrypoint
├── config.json                      # channels to track + videos per channel
├── test_llm.py                      # manual smoke test (lists available models)
├── requirements.txt
├── .env.example                     # copy to .env and fill in your keys
├── .github/
│   └── workflows/run_daily.yml      # daily scheduled run (GitHub Actions)
├── data/                            # sqlite db (gitignored locally; CI force-commits it)
├── logs/                            # run logs (gitignored)
└── youtube/
    ├── videos.py         # YouTube Data API v3 client
    ├── channels.py       # handle → channel resolution
    ├── parser.py         # ISO-8601 duration parsing, format classification
    ├── database.py       # sqlite schema + queries + snapshot pruning
    ├── analysis.py       # per-video metrics, channel baselines
    ├── scoring.py        # normalization, breakout score, winner selection
    ├── llm.py            # Gemini client (JSON mode, model fallback, retries)
    ├── concepts.py       # per-video concept extraction (batched, cached)
    ├── patterns.py       # cross-channel pattern detection
    ├── titles.py         # optimized title generation
    └── trello.py         # winner cards
```

## Getting started

### Prerequisites

- Python 3.10+
- A [YouTube Data API v3](https://console.cloud.google.com/) key — a full run
  uses ~15 quota units of the free 10k/day
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
    ],
    "videos_per_channel": 10
}
```

LLM calls are tiered: bulk work (concept extraction, pattern detection)
runs on lightweight flash-lite variants with higher free-tier daily
quotas, while title generation uses the strongest Flash model. Both
fall back through older variants on rate limits — see `CREATIVE_MODELS`
and `BULK_MODELS` in `youtube/llm.py`.

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
[long ]      1,204,551 views | 10 Games That ...

====================================================================================================
PERFORMANCE WINNER
====================================================================================================
IGN | Marvel's Wolverine - Official Deluxe Edition Trailer
Score: 0.7691 | https://www.youtube.com/watch?v=...

  Optimized title: Never-Before-Seen Wolverine Fight Added to Deluxe Edition — First Look
  Technique: Specific Reveal
  Why: Names a tangible addition so viewers know exactly what exclusive content they'll see.

====================================================================================================
CROSS-CHANNEL PATTERNS
====================================================================================================
[MODERATE] Leak/Accidental Reveal of Upcoming Game
  Channels: Gwynblade, Inside Games
```

### 4. Run daily (optional)

A GitHub Actions workflow (`.github/workflows/run_daily.yml`) runs the
pipeline every day at 20:00 UTC and commits `data/youtube.db` back to the
repo so history accumulates between runs.

To enable it, add these repository secrets (*Settings → Secrets and
variables → Actions*):

`YOUTUBE_API_KEY`, `GEMINI_API_KEY`, `TRELLO_API_KEY`, `TRELLO_TOKEN`,
`TRELLO_LIST_ID`

You can also trigger a run manually from the *Actions* tab via
*workflow_dispatch*. To run locally on a schedule instead, use Task
Scheduler (Windows) or cron (macOS/Linux) to invoke `python main.py`
periodically.

## Data model

Two tables in `data/youtube.db`:

- `videos` — one row per video (upserted on every run), plus a `concept_json`
  column caching LLM concept analysis so videos are only analyzed once
- `snapshots` — views/likes/comments appended per run, enabling historical
  trend tracking (rows older than 30 days are pruned each run)

## Limitations / roadmap

- [x] Shorts detection combines duration (≤180s), thumbnail aspect ratio
      (vertical/square), and `#shorts` hashtags — the Data API has no
      `is_short` flag, so this remains a heuristic
- [x] Retry with exponential backoff on transient YouTube Data API errors
      (429/5xx/network); non-retryable client errors fail fast
- [ ] `data/youtube.db` committed by CI grows over time — snapshot pruning
      plus a per-run `VACUUM` keep it compact for now; consider artifact
      storage if it becomes a problem

## License

<!-- TODO(you): pick a license (e.g. MIT), add a LICENSE file, update this section -->
Not yet licensed.
