---
status: done
---

# Story 8.2: Telegram bot

As a diver,
I want to send my clip to a bot after the dive,
So that contributing takes no effort (FR19).

- Owner: D · Priority: P2 · Depends on: 5.4
- Files: `src/reefcase/bot/main.py`, `src/reefcase/api/routes/surveys.py`, `tests/bot/test_bot.py`, `tests/api/test_upload.py`
- Done when: gate passes; a manual test with a real bot token works

## Acceptance Criteria

**Given** a user sends a video and then a location
**When** the bot receives both
**Then** it POSTs to the API, replies "Investigating…", and on `report_ready` sends the verdict, the top 3 findings and the web link

## Architecture contract

- Architecture §2 & §3: Bot talks to API, does not import `pipeline`, `agent`, or `store`. Layering contract: `api | bot` is top layer.
- Architecture §6.3: Upload endpoint `POST /api/surveys` with multipart form fields (`video`, `lat`, `lon`, `dive_date`, `source="bot"`).
- Settings: Bot API URL configured in `BotSettings` (`REEFCASE_BOT_API_URL`, default `https://app2732006--reefcase-api-api.us-east.modal.run`). Bot token from `Settings.telegram_token` (`REEFCASE_TELEGRAM_TOKEN`).

## Decisions

- **Telegram Bot API directly over httpx:** `aiogram` (via `aiohttp` 3.8.6 C extensions) fails to build on Python 3.14 on Windows due to changes in CPython 3.14 `longobject.h`. Per lead-d instructions, we use Telegram Bot API directly over `httpx` (long polling via `getUpdates`, `getFile`, `sendMessage`).
- **Upload endpoint optional field:** Add optional `source: Annotated[Literal["upload", "bot"], Form()] = "upload"` to `src/reefcase/api/routes/surveys.py`. Update OpenAPI snapshot and regenerate types.
- **20 MB download limit:** Telegram Bot API cannot download files larger than 20 MB. If `file_size > 20 * 1024 * 1024`, immediately reply `"clip is over 20 MB, trim it or upload it on the website"`.
- **In-memory per-chat state:** Holds either video or location until both are present; dive date is taken from the video message timestamp.
- **Offline tests with respx:** Zero live network calls. Logic encapsulated in pure async functions tested with `respx` mock client and synthetic SSE events from `src/reefcase/core/events.py`.

## Tasks

1. [x] Test `source="bot"` in `tests/api/test_upload.py`.
2. [x] Implement `source: Annotated[Literal["upload", "bot"], Form()] = "upload"` in `src/reefcase/api/routes/surveys.py`. Update `web/src/api/openapi.snapshot.json` and run `pnpm -C web run gen:api`.
3. [x] Tests for bot in `tests/bot/test_bot.py`:
   - video then location
   - location then video
   - clip over 20 MB
   - API returning 422
   - survey failed event
4. [x] Implement `src/reefcase/bot/main.py` with `BotSettings`, `ChatSession`, message handling, SSE stream follower, and long-polling runner.
5. [x] Add manual test verification steps to `ops/lead-d/handoff.md`.
6. [x] Run gates: `uv run poe gate` and `pnpm -C web run gate`.

## Lessons

- Under Python 3.14, binary C-extension packages without prebuilt wheels (like older `aiohttp`) will fail to compile. Direct `httpx` API integration avoids third-party C dependencies.
- Read query/form parameters carefully to preserve openapi schema compatibility.
- Ensure test suite never performs live network requests.

## Library check

- `aiogram`: Failed build on Python 3.14 (`aiohttp==3.8.6` build error with MSVC on Python 3.14 `ob_digit` in `_longobject`).
- `httpx`: 0.28.1 installed and confirmed.
- `respx`: 0.23.1 installed in dev dependencies for mocking httpx calls.
