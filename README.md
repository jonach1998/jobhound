# JobHound 🐾

[![CI](https://github.com/jonach1998/jobhound/actions/workflows/tests.yml/badge.svg)](https://github.com/jonach1998/jobhound/actions/workflows/tests.yml)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

AI-powered job hunting automation. Scrapes LinkedIn, Indeed, and Computrabajo, scores each listing against a candidate profile using any OpenAI-compatible LLM, and sends the best matches to Telegram.

## How it works

1. **Scrape** — fetches job listings from LinkedIn, Indeed (via JobSpy), and Computrabajo for each configured search term.
2. **Score** — sends each listing to an AI model with the candidate's CV and a custom scoring prompt. Returns a 0–100 match score with a short explanation of what fits and what doesn't.
3. **Notify** — sends jobs above the configured score threshold to Telegram with score, company, location, and a direct link.
4. **Schedule** — runs automatically at configured hours via APScheduler. Already-seen jobs are deduplicated across runs using SQLite. Failed notifications are retried on the next run.

## Running with Docker (recommended)

Docker is the recommended way to run JobHound. It handles all dependencies, keeps the process running in the background, and restarts automatically if the machine reboots.

**Prerequisites:** [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/install/).

### Using the published image

The easiest option — no need to clone the repository.

**1. Create a working directory**

```bash
mkdir jobhound && cd jobhound
```

**2. Create your `.env` file**

Download the example and fill it in:

```bash
curl -o .env https://raw.githubusercontent.com/jonach1998/jobhound/main/.env.example
```

Open `.env` and fill in at minimum:
- `AI_API_KEY`, `AI_MODEL`, `AI_BASE_URL` — see [Compatible AI providers](#compatible-ai-providers)
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_IDS` — see [Telegram setup](#telegram-setup) (optional)
- `TZ` — your timezone (e.g. `America/New_York`, `America/Costa_Rica`)

**3. Create a profile**

```bash
mkdir -p profiles/my-profile
```

Create the three files inside `profiles/my-profile/` — see [Profiles](#profiles) for what each one should contain.

**4. Create a `docker-compose.yml`**

```yaml
services:
  jobhound:
    image: jonach1998/jobhound:latest
    container_name: jobhound
    restart: unless-stopped
    env_file: .env
    volumes:
      - ./data:/app/data
      - ./profiles:/app/profiles:ro
```

**5. Start the container**

```bash
docker compose up -d
```

### Building from source

Use this if you want to modify the code or contribute to the project.

**1. Clone the repo**

```bash
git clone https://github.com/jonach1998/jobhound.git
cd jobhound
```

**2. Configure the environment**

```bash
cp .env.example .env
```

Open `.env` and fill in the same values as above.

**3. Create a profile**

```bash
cp -r profiles/example profiles/my-profile
```

Edit the three files inside `profiles/my-profile/` and remove `example: true` from `profile.yaml`. See [Profiles](#profiles) for details.

**4. Build and start**

```bash
docker compose up -d --build
```

---

**Checking the logs**

```bash
docker compose logs -f jobhound
```

The container runs in the background and restarts automatically on reboot (`restart: unless-stopped`). If `RUN_ON_STARTUP=true`, it runs a first scan immediately on start.

**Useful commands**

```bash
docker compose stop jobhound        # stop without removing
docker compose start jobhound       # start again
docker compose up -d --build        # rebuild after code changes
docker compose down                 # stop and remove the container
```

## Running without Docker

Use this if you prefer to run the app directly on your machine, for example to test changes quickly without rebuilding the container.

**Prerequisites:** Python 3.12.

**1. Clone and install**

```bash
git clone https://github.com/jonach1998/jobhound.git
cd jobhound

python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

**2. Configure and run**

```bash
cp .env.example .env
# Edit .env with your values

PYTHONPATH=src python src/main.py
```

The app loads profiles from the `profiles/` folder and stores the job database at `data/jobs.sqlite`, both relative to the project root. Note that scheduling (`SCHEDULE_HOURS`) works the same way — the process must stay running for the scheduler to fire.

## Configuration

Copy `.env.example` to `.env` and fill in the values:

| Variable | Required | Description |
|---|---|---|
| `AI_API_KEY` | Yes | API key for your AI provider |
| `AI_MODEL` | Yes | Model name (e.g. `gpt-4o-mini`, `llama-3.3-70b-versatile`) |
| `AI_BASE_URL` | Yes | Provider base URL (see table below) |
| `SCHEDULE_HOURS` | Yes | Hours to run daily (e.g. `08:00,20:00`) |
| `RUN_ON_STARTUP` | Yes | `true` to run once immediately on container start |
| `TZ` | Yes | Container timezone (e.g. `America/New_York`) |
| `TELEGRAM_BOT_TOKEN` | If using Telegram | Token from [@BotFather](https://t.me/BotFather) |
| `TELEGRAM_CHAT_IDS` | If using Telegram | Comma-separated chat IDs to notify |
| `PROFILE_YAML_FILENAME` | No | Profile config filename (default: `profile.yaml`) |
| `PROFILE_CV_FILENAME` | No | CV filename (default: `cv.txt`) |
| `PROFILE_SCORING_PROMPT_FILENAME` | No | Scoring prompt filename (default: `scoring_prompt.txt`) |

> **Telegram is optional.** If `TELEGRAM_CHAT_IDS` is not set, the app scores jobs and logs results to stdout without sending any notifications.

## Telegram setup

**1. Create a bot**

1. Open Telegram and search for [@BotFather](https://t.me/BotFather).
2. Send `/newbot` and follow the prompts.
3. Copy the token it gives you — that's your `TELEGRAM_BOT_TOKEN`.

**2. Get your chat ID**

1. Start a conversation with [@userinfobot](https://t.me/userinfobot).
2. It will reply with your numeric chat ID.
3. Set `TELEGRAM_CHAT_IDS` to that number (comma-separate if you want multiple recipients).

## Compatible AI providers

JobHound uses the OpenAI chat completions format (`POST /v1/chat/completions`). Any provider that implements this interface works out of the box.

| Provider | `AI_BASE_URL` | Notes |
|---|---|---|
| [OpenAI](https://platform.openai.com) | `https://api.openai.com/v1` | GPT-4o, GPT-4o-mini |
| [OpenRouter](https://openrouter.ai) | `https://openrouter.ai/api/v1` | Proxy for Claude, Gemini, Llama, and more |
| [Groq](https://console.groq.com) | `https://api.groq.com/openai/v1` | Fast inference; Llama 3, Mixtral |
| [Together AI](https://api.together.xyz) | `https://api.together.xyz/v1` | Wide model selection |
| [Deepseek](https://platform.deepseek.com) | `https://api.deepseek.com/v1` | Deepseek-V3, Deepseek-R1 |
| [Mistral](https://console.mistral.ai) | `https://api.mistral.ai/v1` | Mistral Large, Mistral Small |
| [Ollama](https://ollama.com) | `http://localhost:11434/v1` | Local, free, private |
| [MiniMax](https://www.minimaxi.com) | `https://api.minimax.io/v1` | Tested default |

> The model must support `response_format: {"type": "json_object"}`. All providers listed above support it.

## Profiles

Each profile is a folder under `profiles/` with three files:

```
profiles/my-profile/
  profile.yaml         # display name, score threshold, search terms
  cv.txt               # candidate CV sent to the AI for scoring
  scoring_prompt.txt   # scoring rules and criteria for this profile
```

**To add a profile:**

1. Copy `profiles/example/` and rename the folder.
2. Edit the three files:
   - **`profile.yaml`** — set `display_name`, `score_threshold` (0–100), and `search_terms`.
   - **`cv.txt`** — the candidate's CV in plain text. This is sent verbatim to the AI for every job scored.
   - **`scoring_prompt.txt`** — tell the AI what makes a good or bad match for this candidate. Describe the candidate's situation, define the score scale, and list what to prioritize and penalize. English or Spanish both work. See `profiles/example/scoring_prompt.txt` for a complete reference.
3. Remove `example: true` from `profile.yaml`.

The app auto-discovers all active profiles at startup. No code or Docker changes needed. Multiple profiles run independently — useful for searching different roles or candidates simultaneously.

## Project structure

```
src/jobhound/
  app.py               # orchestration: scrape → score → notify → schedule
  config/              # env and profile loading
  models/              # Job dataclass
  repositories/        # SQLite job store
  scrapers/            # JobSpy (LinkedIn/Indeed) and Computrabajo scrapers
  services/            # AI scorer and Telegram notifier
  utils/               # logging helpers
profiles/example/      # template profile (not run automatically)
data/jobs.sqlite       # persistent job store (created at runtime)
```

## Adding a scraper

See [CONTRIBUTING.md](CONTRIBUTING.md#adding-a-scraper).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=jonach1998/jobhound&type=Date)](https://star-history.com/#jonach1998/jobhound&Date)

## License

MIT — see [LICENSE](LICENSE).
