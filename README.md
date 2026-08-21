# YouTube Content Intelligence

## Demo

<!-- TODO(you): record a 30-60s terminal capture of a full run (python main.py),
     convert to GIF, save as docs/demo.gif, then delete this comment. -->
![Terminal run](docs/demo.gif)

<!-- TODO(you): screenshot your Trello board showing the two winner cards,
     save as docs/trello.png, then delete this comment. -->
![Trello winner cards](docs/trello.png)

Daily automated pipeline that monitors competitor gaming channels on YouTube,
scores their video performance, and uses an LLM to reverse-engineer *why* the
winners work — then generates optimized title ideas and delivers them to a
Trello board as ready-to-use content concepts.

## How it works

```
YouTube Data API v3 ──► SQLite ──► Normalized metrics ──► Groq LLM ──► Trello cards
 (latest uploads from    (videos,   (velocity, engagement,  (concepts,   (performance +
  N gaming channels)     snapshots) baseline ratio)          patterns,    opportunity
                                                            titles)      winners)
```

| Stage | Modules | What it does |
|---|---|---|
| 1. Ingest | `youtube/videos.py`, `channels.py`, `parser.py` | Resolve @handles, fetch latest uploads, parse durations, classify short/long |
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
  (Shorts never compete with long-form)
- **view_velocity** — views per hour since publish
- **engagement_rate** — (likes + comments) ÷ views

Two winners are selected each run:

- **Performance Winner** — highest breakout score
- **Opportunity Winner** — most replicable concept (LLM-scored 1–10) among the rest

## Project structure

```
├── main.py               # pipeline entrypoint
├── config.json           # channels to track + videos per channel
├── run_daily.bat         # scheduled-run wrapper (Windows)
├── requirements.txt
├── .env.example          # copy to .env and fill in your keys
├── data/                 # sqlite db (created at runtime, gitignored)
├── logs/                 # run logs (gitignored)
└── youtube/
    ├── videos.py         # YouTube Data API v3 client
    ├── channels.py       # handle → channel resolution
    ├── parser.py         # ISO-8601 duration parsing, format classification
    ├── database.py       # sqlite schema + queries
    ├── analysis.py       # per-video metrics, channel baselines
    ├── scoring.py        # normalization, breakout score, winner selection
    ├── llm.py            # Groq client (forced JSON mode)
    ├── concepts.py       # per-video concept extraction
    ├── patterns.py       # cross-channel pattern detection
    ├── titles.py         # optimized title generation
    └── trello.py         # winner cards
```

## Getting started

### Prerequisites

- Python 3.10+
- A [YouTube Data API v3](https://console.cloud.google.com/) key — a full run
  uses ~15 quota units of the free 10k/day
- A [Groq](https://console.groq.com/keys) API key (free tier available)
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
| `GROQ_API_KEY` | [console.groq.com/keys](https://console.groq.com/keys) |
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

The LLM model defaults to `openai/gpt-oss-120b` — change `MODEL` in
`youtube/llm.py` if needed.

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

### 4. Run daily (optional, Windows)

`run_daily.bat` runs the pipeline and appends all output to
`logs/run_log.txt`. Schedule it with Task Scheduler:

```powershell
schtasks /Create /SC DAILY /ST 09:00 /TN "YouTube Content Intelligence" `
  /TR "C:\path\to\youtube-content-intelligence\run_daily.bat"
```

Adjust the path. On macOS/Linux, wire the same commands into cron.

## Data model

Two tables in `data/youtube.db`:

- `videos` — one row per video (upserted on every run)
- `snapshots` — views/likes/comments appended per run, enabling historical
  trend tracking

## Limitations / roadmap

- [ ] Concept analysis re-runs for all stored videos every run — cache results per `video_id`
- [ ] Shorts detection is duration-based (≤180s) only
- [ ] No retry/backoff on API calls
- [ ] Snapshots table grows unbounded — add pruning

## License

<!-- TODO(you): pick a license (e.g. MIT), add a LICENSE file, update this section -->
Not yet licensed.
