"""Story 8.3 — the API serves the built web app from one origin (REEFCASE_WEB_DIST)."""

from pathlib import Path

import httpx
import pytest

from reefcase.api.main import create_app

INDEX = "<!doctype html><title>ReefCase</title>"


def _web_dist(tmp_path: Path) -> Path:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text(INDEX, encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    return dist


def _client(make_settings, tmp_path: Path, **overrides) -> httpx.AsyncClient:
    settings = make_settings(data_dir=str(tmp_path / "var"), segmenter="fake", **overrides)
    app = create_app(settings, run_stages=None)
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_the_web_build_is_served_at_the_root(make_settings, tmp_path: Path) -> None:
    async with _client(make_settings, tmp_path, web_dist=str(_web_dist(tmp_path))) as client:
        index = await client.get("/")
        asset = await client.get("/assets/app.js")

    assert index.status_code == 200
    assert index.text == INDEX
    assert asset.status_code == 200
    assert asset.text == "console.log(1)"


@pytest.mark.asyncio
async def test_client_side_routes_fall_back_to_index(make_settings, tmp_path: Path) -> None:
    async with _client(make_settings, tmp_path, web_dist=str(_web_dist(tmp_path))) as client:
        response = await client.get("/case/srv_123")

    assert response.status_code == 200
    assert response.text == INDEX


@pytest.mark.asyncio
async def test_api_routes_win_and_unknown_api_paths_stay_404(make_settings, tmp_path: Path) -> None:
    async with _client(make_settings, tmp_path, web_dist=str(_web_dist(tmp_path))) as client:
        health = await client.get("/api/health")
        missing = await client.get("/api/nope")

    assert health.json()["segmenter"] == "fake"
    assert missing.status_code == 404
    assert missing.json() == {"detail": "Not Found"}


@pytest.mark.asyncio
async def test_no_web_build_is_served_by_default(make_settings, tmp_path: Path) -> None:
    async with _client(make_settings, tmp_path) as client:
        response = await client.get("/")

    assert response.status_code == 404


def test_a_missing_web_build_fails_at_startup(make_settings, tmp_path: Path) -> None:
    settings = make_settings(
        data_dir=str(tmp_path / "var"), segmenter="fake", web_dist=str(tmp_path / "gone")
    )

    with pytest.raises(RuntimeError, match="gone"):
        create_app(settings, run_stages=None)
