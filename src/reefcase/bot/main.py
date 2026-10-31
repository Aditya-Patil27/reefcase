"""Story 8.2: Telegram bot interface for ReefCase (FR19).

Divers can send their video clip and location pin directly via Telegram.
The bot uploads the clip to the ReefCase API, monitors progress over SSE,
and reports the verdict, findings, and web case file link.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import cast

import httpx
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger("reefcase.bot")

MAX_TELEGRAM_FILE_BYTES = 20 * 1024 * 1024  # 20 MB limit imposed by Telegram Bot API


class BotSettings(BaseSettings):
    """Bot-specific configuration."""

    model_config = SettingsConfigDict(env_prefix="REEFCASE_BOT_")

    api_url: str = "https://app2732006--reefcase-api-api.us-east.modal.run"


@dataclass
class VideoPayload:
    """A video uploaded by the diver."""

    content: bytes
    filename: str
    dive_date: date
    size: int


@dataclass
class LocationPayload:
    """A location provided by the diver."""

    lat: float
    lon: float


@dataclass
class ChatSession:
    """Pending user state for an ongoing upload."""

    video: VideoPayload | None = None
    location: LocationPayload | None = None


SendCallable = Callable[[int, str], Awaitable[None]]


def _get_val(d: object, key: str) -> object | None:
    if not isinstance(d, dict):
        return None
    for k, v in cast(dict[object, object], d).items():
        if k == key:
            return v
    return None


def _get_str(d: object, key: str) -> str | None:
    val = _get_val(d, key)
    return val if isinstance(val, str) else None


def _get_int(d: object, key: str) -> int | None:
    val = _get_val(d, key)
    return val if isinstance(val, int) else None


def _get_float(d: object, key: str) -> float | None:
    val = _get_val(d, key)
    if isinstance(val, (int, float)):
        return float(val)
    return None


def _get_dict(d: object, key: str) -> dict[str, object] | None:
    val = _get_val(d, key)
    if isinstance(val, dict):
        res: dict[str, object] = {}
        for k, v in cast(dict[object, object], val).items():
            if isinstance(k, str):
                res[k] = v
        return res
    return None


def _get_list(d: object, key: str) -> list[object] | None:
    val = _get_val(d, key)
    if isinstance(val, list):
        return cast(list[object], val)
    return None


def _is_video_doc(doc: dict[str, object]) -> bool:
    mime = (_get_str(doc, "mime_type") or "").lower()
    name = (_get_str(doc, "file_name") or "").lower()
    if mime.startswith("video/"):
        return True
    return any(name.endswith(ext) for ext in [".mp4", ".mov", ".avi", ".webm", ".mkv"])


async def follow_survey_events(
    survey_id: str,
    chat_id: int,
    send: SendCallable,
    api_client: httpx.AsyncClient,
    api_url: str,
) -> None:
    """Follow survey SSE events until completion or failure."""
    events_url = f"{api_url.rstrip('/')}/api/surveys/{survey_id}/events"
    base_web_url = api_url.rstrip("/")

    try:
        async with api_client.stream(
            "GET", events_url, timeout=httpx.Timeout(600.0, read=None)
        ) as response:
            if response.status_code != 200:
                await send(
                    chat_id,
                    f"Could not follow investigation events ({response.status_code}).",
                )
                return

            event_type: str | None = None
            data_lines: list[str] = []

            async for line in response.aiter_lines():
                line = line.strip()
                if not line:
                    if data_lines:
                        raw_data = "\n".join(data_lines)
                        data_lines = []
                        try:
                            parsed_payload: object = json.loads(raw_data)
                        except Exception:
                            parsed_payload = {}

                        current_type = event_type
                        if not current_type and isinstance(parsed_payload, dict):
                            payload_dict = cast(dict[str, object], parsed_payload)
                            current_type = _get_str(payload_dict, "type")
                        event_type = None

                        if current_type == "report_ready":
                            inv_url = f"{api_url.rstrip('/')}/api/surveys/{survey_id}/investigation"
                            inv_resp = await api_client.get(inv_url)
                            if inv_resp.status_code == 200:
                                inv_data: object = inv_resp.json()
                                verdict = _get_str(inv_data, "verdict") or ""
                                raw_findings = _get_list(inv_data, "findings") or []
                                findings: list[str] = []
                                for item in raw_findings:
                                    if isinstance(item, dict):
                                        item_dict = cast(dict[str, object], item)
                                        stmt = _get_str(item_dict, "statement")
                                        if stmt:
                                            findings.append(stmt)
                                top_3 = findings[:3]
                                findings_text = "\n".join(f"• {stmt}" for stmt in top_3)
                                link = f"{base_web_url}/surveys/{survey_id}"
                                msg = (
                                    f"Investigation complete!\n\n"
                                    f"Verdict: {verdict}\n\n"
                                    f"Top findings:\n{findings_text}\n\n"
                                    f"Case file: {link}"
                                )
                                await send(chat_id, msg)
                            else:
                                link = f"{base_web_url}/surveys/{survey_id}"
                                await send(
                                    chat_id,
                                    f"Investigation ready! Case file: {link}",
                                )
                            return

                        if current_type == "survey_failed":
                            reason = "Unknown failure"
                            if isinstance(parsed_payload, dict):
                                payload_dict = cast(dict[str, object], parsed_payload)
                                reason_val = _get_str(payload_dict, "reason")
                                if reason_val:
                                    reason = reason_val
                            await send(chat_id, f"Investigation failed: {reason}")
                            return
                    continue

                if line.startswith("event:"):
                    event_type = line[len("event:") :].strip()
                elif line.startswith("data:"):
                    data_lines.append(line[len("data:") :].strip())
    except Exception as exc:
        logger.exception("Error while following survey events: %s", exc)
        await send(chat_id, f"Error following investigation: {exc}")


async def submit_and_follow(
    session: ChatSession,
    chat_id: int,
    send: SendCallable,
    api_client: httpx.AsyncClient,
    api_url: str,
) -> None:
    """Submit the clip and location to the survey API, then follow its progress."""
    video = session.video
    loc = session.location
    if video is None or loc is None:
        return

    # Reset session so that next submission starts fresh
    session.video = None
    session.location = None

    url = f"{api_url.rstrip('/')}/api/surveys"
    files = {"video": (video.filename, video.content, "video/mp4")}
    data = {
        "lat": str(loc.lat),
        "lon": str(loc.lon),
        "dive_date": video.dive_date.isoformat(),
        "source": "bot",
    }

    try:
        resp = await api_client.post(url, files=files, data=data)
    except Exception as exc:
        logger.exception("Failed to connect to API")
        await send(chat_id, f"Failed to submit survey: {exc}")
        return

    if resp.status_code == 422:
        try:
            err_json: object = resp.json()
            if isinstance(err_json, dict):
                err_dict = cast(dict[str, object], err_json)
                detail = _get_str(err_dict, "detail") or str(err_dict)
            else:
                detail = str(err_json)
        except Exception:
            detail = resp.text
        await send(chat_id, f"Survey submission rejected: {detail}")
        return

    if resp.status_code != 201:
        await send(chat_id, f"Survey submission error ({resp.status_code}): {resp.text}")
        return

    survey_data: object = resp.json()
    survey_id = _get_str(survey_data, "id") or ""
    await send(chat_id, "Investigating…")

    await follow_survey_events(survey_id, chat_id, send, api_client, api_url)


async def handle_video(
    session: ChatSession,
    video: VideoPayload,
    chat_id: int,
    send: SendCallable,
    api_client: httpx.AsyncClient,
    api_url: str,
) -> None:
    """Handle an incoming video clip."""
    if video.size > MAX_TELEGRAM_FILE_BYTES:
        await send(chat_id, "clip is over 20 MB, trim it or upload it on the website")
        return

    session.video = video
    if session.location is None:
        await send(chat_id, "Clip received. Please send your dive location.")
        return

    await submit_and_follow(session, chat_id, send, api_client, api_url)


async def handle_location(
    session: ChatSession,
    location: LocationPayload,
    chat_id: int,
    send: SendCallable,
    api_client: httpx.AsyncClient,
    api_url: str,
) -> None:
    """Handle an incoming location pin."""
    session.location = location
    if session.video is None:
        await send(chat_id, "Location received. Please send your dive clip.")
        return

    await submit_and_follow(session, chat_id, send, api_client, api_url)


async def run_bot(
    token: str,
    api_url: str,
    stop_event: asyncio.Event | None = None,
) -> None:
    """Run the Telegram bot long polling loop."""
    telegram_base = f"https://api.telegram.org/bot{token}"
    file_base = f"https://api.telegram.org/file/bot{token}"
    sessions: dict[int, ChatSession] = {}

    async with httpx.AsyncClient(timeout=httpx.Timeout(40.0, read=40.0)) as http_client:

        async def send_message(chat_id: int, text: str) -> None:
            await http_client.post(
                f"{telegram_base}/sendMessage",
                json={"chat_id": chat_id, "text": text},
            )

        offset = 0
        while stop_event is None or not stop_event.is_set():
            try:
                resp = await http_client.get(
                    f"{telegram_base}/getUpdates",
                    params={"offset": offset, "timeout": 30},
                )
                if resp.status_code != 200:
                    logger.warning("getUpdates failed with status %d", resp.status_code)
                    await asyncio.sleep(2)
                    continue

                resp_data: object = resp.json()
                raw_updates = _get_list(resp_data, "result") or []
                for raw_update in raw_updates:
                    if not isinstance(raw_update, dict):
                        continue
                    update_dict = cast(dict[str, object], raw_update)
                    update_id = _get_int(update_dict, "update_id")
                    if update_id is not None:
                        offset = max(offset, update_id + 1)
                    message = _get_dict(update_dict, "message")
                    if message is None:
                        continue
                    chat = _get_dict(message, "chat")
                    if chat is None:
                        continue
                    chat_id = _get_int(chat, "id")
                    if chat_id is None:
                        continue

                    session = sessions.setdefault(chat_id, ChatSession())

                    # Check for location
                    loc = _get_dict(message, "location")
                    if loc is not None:
                        lat = _get_float(loc, "latitude")
                        lon = _get_float(loc, "longitude")
                        if lat is not None and lon is not None:
                            loc_payload = LocationPayload(lat=lat, lon=lon)
                            await handle_location(
                                session, loc_payload, chat_id, send_message, http_client, api_url
                            )
                            continue

                    # Check for video or video-document
                    video_info = _get_dict(message, "video")
                    doc_info = _get_dict(message, "document")
                    target: dict[str, object] | None = None
                    if video_info is not None:
                        target = video_info
                    elif doc_info is not None and _is_video_doc(doc_info):
                        target = doc_info

                    if target is not None:
                        file_id = _get_str(target, "file_id")
                        file_size = _get_int(target, "file_size") or 0
                        file_name = _get_str(target, "file_name") or "clip.mp4"

                        if file_size > MAX_TELEGRAM_FILE_BYTES:
                            await send_message(
                                chat_id, "clip is over 20 MB, trim it or upload it on the website"
                            )
                            continue

                        if file_id is None:
                            await send_message(chat_id, "Could not read video file information.")
                            continue

                        file_resp = await http_client.get(
                            f"{telegram_base}/getFile", params={"file_id": file_id}
                        )
                        if file_resp.status_code != 200:
                            await send_message(chat_id, "Failed to download video from Telegram.")
                            continue

                        file_resp_data: object = file_resp.json()
                        result_info = _get_dict(file_resp_data, "result")
                        file_path = _get_str(result_info, "file_path") if result_info else None
                        if file_path is None:
                            await send_message(chat_id, "Failed to locate video on Telegram.")
                            continue

                        dl_resp = await http_client.get(f"{file_base}/{file_path}")
                        if dl_resp.status_code != 200:
                            await send_message(chat_id, "Failed to download video content.")
                            continue

                        raw_date = _get_int(message, "date")
                        if raw_date is not None:
                            msg_date = datetime.fromtimestamp(raw_date, tz=UTC).date()
                        else:
                            msg_date = datetime.now(UTC).date()

                        payload = VideoPayload(
                            content=dl_resp.content,
                            filename=file_name,
                            dive_date=msg_date,
                            size=file_size or len(dl_resp.content),
                        )
                        await handle_video(
                            session, payload, chat_id, send_message, http_client, api_url
                        )
                        continue

                    # Check for commands or text
                    text = _get_str(message, "text")
                    if text and text.startswith("/"):
                        welcome = (
                            "Welcome to ReefCase! Send a reef video clip and a location pin "
                            "to begin an investigation."
                        )
                        await send_message(chat_id, welcome)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.exception("Error in bot polling loop: %s", exc)
                await asyncio.sleep(2)


def main() -> None:
    """Run the ReefCase Telegram bot."""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    from reefcase.core.config import Settings

    settings = Settings()
    token_secret = settings.telegram_token
    if not token_secret:
        logger.error("REEFCASE_TELEGRAM_TOKEN is not set. Exiting.")
        sys.exit(1)

    bot_settings = BotSettings()
    logger.info("Starting ReefCase Telegram bot connected to %s", bot_settings.api_url)
    try:
        asyncio.run(run_bot(token=token_secret.get_secret_value(), api_url=bot_settings.api_url))
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")


if __name__ == "__main__":
    main()
