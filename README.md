# reMarkable Podcast

Generate personalized podcast episodes from your handwritten notes. Connect your reMarkable tablet or upload journal photos, and the app extracts your writing via OCR, generates a script with AI, and produces audio you can listen to.

## How it works

1. **Input** -- Connect your reMarkable tablet (cloud sync) or upload photos of handwritten journal pages
2. **Extract** -- Handwriting is converted to text via Google Cloud Vision OCR
3. **Script** -- Claude generates a podcast script based on your notes, using one of 6 personality styles
4. **Audio** -- ElevenLabs text-to-speech produces an MP3 episode

## Prerequisites

- Python 3.10+
- Node.js 18+
- API keys (configured in `.env.local`):
  - `ANTHROPIC_API_KEY` -- for script generation
  - `ELEVENLABS_API_KEY` -- for text-to-speech
  - `GOOGLE_APPLICATION_CREDENTIALS` -- service account JSON path for OCR
  - `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` -- for Google OAuth login
  - `APP_SECRET_KEY` -- any random string for JWT signing

Optional:
- `REMARKABLE_TOKEN` -- JWT token for reMarkable Cloud access (not needed for photo-only usage)

## Setup

```bash
# Clone and enter the project
git clone <your-repo-url>
cd remarkable-podcast

# Create virtual environment and install dependencies
python -m venv .venv
source .venv/bin/activate
pip install -e ".[web]"

# Install frontend dependencies
cd web
npm install
npm run build
cd ..

# Copy and edit your environment config
cp .env.local.example .env.local   # if an example exists, otherwise create .env.local
```

## Running the app

### Backend

```bash
source .venv/bin/activate
uvicorn api.main:app --reload
```

The app is available at `http://localhost:8000`.

With `--reload`, the server automatically restarts when you edit Python files. To stop it, press `Ctrl+C`.

### Frontend development

For live-reloading frontend changes without rebuilding:

```bash
cd web
npm run dev
```

This starts a dev server at `http://localhost:5173` that proxies API requests to the backend at `:8000`. Both servers need to be running.

### Building the frontend

```bash
cd web
npm run build
```

Output goes to `web/dist/` and is served by the FastAPI backend automatically.

## Project structure

```
api/            FastAPI backend (routes, auth, worker, photo library)
daily_podcast/  Podcast pipeline (extract, summarize, speak, personalities)
remarkable_mcp/ reMarkable tablet integration (cloud API, file parsing, OCR)
web/            React + TypeScript + Tailwind frontend (Vite)
data/           SQLite database + user episode files + uploaded photos
.env.local      Environment variables (not committed)
```

## Key concepts

- **Show** -- A recurring podcast series. Configured with a source (reMarkable or Photo Library), personality, time window, and cadence.
- **Episode** -- A single podcast generation. Goes through: extracting -> summarizing -> generating audio -> ready.
- **Photo Library** -- Upload journal photos (JPEG, PNG, HEIC). OCR runs automatically at upload time and is cached permanently.
- **Personalities** -- 6 podcast styles: Logbook, Analyst, Coach, Connector, Creative, Editor. Each has a distinct tone and system prompt.

## License

MIT
