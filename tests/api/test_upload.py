"""Story 2.1 — POST /api/surveys: valid upload, field-level 422s, size cap, health."""

from datetime import date
from importlib import import_module
from pathlib import Path

import httpx
import pytest

from reefcase.api.main import create_app
from reefcase.api.sync_asgi import SyncASGITransport
from reefcase.core.errors import NotFoundError
from reefcase.store.db import Store

CLIP_BYTES = (Path(__file__).parents[1] / "fixtures" / "clip_10s.mp4").read_bytes()
GOOD_FIELDS = {"lat": "19.7292", "lon": "-157.4132", "dive_date": "2026-10-01"}


def build_app(make_settings, tmp_path: Path):
    settings = make_settings(data_dir=str(tmp_path / "var"), segmenter="fake")
    return create_app(settings)


def client_for(app) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


def sync_client_for(app) -> httpx.Client:
    return httpx.Client(transport=SyncASGITransport(app), base_url="http://test")


async def post_survey(
    client: httpx.AsyncClient, video_name="clip.mp4", video_bytes=None, **overrides
):
    fields = dict(GOOD_FIELDS)
    fields.update(overrides)
    for key, value in list(fields.items()):
        if value is None:
            del fields[key]
    data = {"video": (video_name, video_bytes or CLIP_BYTES, "video/mp4")}
    return await client.post("/api/surveys", data=fields, files=data)


@pytest.mark.asyncio
async def test_upload_creates_queued_survey_and_stores_video(make_settings, tmp_path) -> None:
    app = build_app(make_settings, tmp_path)
    async with client_for(app) as client:
        response = await post_survey(client)
    assert response.status_code == 201
    body = response.json()
    assert body["id"].startswith("srv_")
    assert body["status"] == "queued"
    assert body["source"] == "upload"
    assert body["dive_date"] == "2026-10-01"
    assert body["video_path"] == f"blobs/{body['id']}/video.mp4"
    assert body["site_id"].startswith("site_")

    store = app.state.store
    survey = await store.surveys.get(body["id"])
    assert survey.model_dump(mode="json") == body
    assert store.blobs.read(body["video_path"]) == CLIP_BYTES


@pytest.mark.asyncio
async def test_upload_names_the_site(make_settings, tmp_path) -> None:
    app = build_app(make_settings, tmp_path)
    async with client_for(app) as client:
        named = await post_survey(client, site_name="Horseshoe Reef")
        unnamed = await post_survey(client)
    store = app.state.store
    site_named = await store.sites.get(named.json()["site_id"])
    assert site_named.name == "Horseshoe Reef"
    site_unnamed = await store.sites.get(unnamed.json()["site_id"])
    assert site_unnamed.name == "Reef @ 19.72920, -157.41320"


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_lat", ["95", "-91"])
async def test_upload_rejects_lat_out_of_range(make_settings, tmp_path, bad_lat) -> None:
    app = build_app(make_settings, tmp_path)
    async with client_for(app) as client:
        response = await post_survey(client, lat=bad_lat)
    assert response.status_code == 422
    assert "lat" in response.text


@pytest.mark.asyncio
async def test_upload_rejects_lon_out_of_range(make_settings, tmp_path) -> None:
    app = build_app(make_settings, tmp_path)
    async with client_for(app) as client:
        response = await post_survey(client, lon="-200")
    assert response.status_code == 422
    assert "lon" in response.text


@pytest.mark.asyncio
async def test_upload_rejects_non_video_file(make_settings, tmp_path) -> None:
    app = build_app(make_settings, tmp_path)
    async with client_for(app) as client:
        response = await post_survey(client, video_name="notes.txt", video_bytes=b"hello")
    assert response.status_code == 422
    assert "video" in response.text


@pytest.mark.asyncio
async def test_upload_rejects_missing_dive_date(make_settings, tmp_path) -> None:
    app = build_app(make_settings, tmp_path)
    async with client_for(app) as client:
        response = await post_survey(client, dive_date=None)
    assert response.status_code == 422
    assert "dive_date" in response.text


@pytest.mark.asyncio
async def test_upload_rejects_oversized_video(make_settings, tmp_path, monkeypatch) -> None:
    surveys = import_module("reefcase.api.routes.surveys")
    monkeypatch.setattr(surveys, "MAX_VIDEO_BYTES", 1024)
    app = build_app(make_settings, tmp_path)
    async with client_for(app) as client:
        response = await post_survey(client)
    assert response.status_code == 413


@pytest.mark.asyncio
async def test_get_survey_returns_created_survey(make_settings, tmp_path) -> None:
    app = build_app(make_settings, tmp_path)
    async with client_for(app) as client:
        created = await post_survey(client)
        fetched = await client.get(f"/api/surveys/{created.json()['id']}")
    assert fetched.status_code == 200
    assert fetched.json() == created.json()


@pytest.mark.asyncio
async def test_unknown_survey_is_404(make_settings, tmp_path) -> None:
    app = build_app(make_settings, tmp_path)
    async with client_for(app) as client:
        response = await client.get("/api/surveys/srv_missing")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_survey_survives_app_shutdown(make_settings, tmp_path) -> None:
    app = build_app(make_settings, tmp_path)
    async with client_for(app) as client:
        response = await post_survey(client)
    survey_id = response.json()["id"]
    app.state.store.close()
    with Store.open(tmp_path / "var") as reopened:
        assert (await reopened.surveys.get(survey_id)).id == survey_id
        with pytest.raises(NotFoundError):
            await reopened.surveys.get("srv_nope")


def test_health_reports_provider_config(make_settings, tmp_path) -> None:
    app = build_app(make_settings, tmp_path)
    with sync_client_for(app) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["segmenter"] == "fake"
    assert body["agent_llm"] is False
    assert body["teacher_llm"] is False


def test_dive_date_is_a_real_date() -> None:
    assert date.fromisoformat("2026-10-01") == date(2026, 10, 1)
