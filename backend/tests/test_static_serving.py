from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app


def test_static_serving_disabled_when_dist_missing(monkeypatch) -> None:
    # `frontend/dist` may exist locally if the user has built the frontend.
    # Force static serving *off* by pointing to a non-existent directory.
    monkeypatch.setenv("COMMANDDECK_FRONTEND_DIST_DIR", "__does_not_exist__")

    app = create_app()
    with TestClient(app) as client:
        resp = client.get("/")
        assert resp.status_code == 404


def test_static_serving_index_assets_and_spa_fallback(
    tmp_path: Path, monkeypatch
) -> None:
    dist_dir = tmp_path / "dist"
    assets_dir = dist_dir / "assets"
    assets_dir.mkdir(parents=True)

    (dist_dir / "index.html").write_text(
        "<!doctype html><html><body>OK</body></html>", encoding="utf-8"
    )
    (assets_dir / "app.js").write_text("console.log('ok')", encoding="utf-8")

    monkeypatch.setenv("COMMANDDECK_FRONTEND_DIST_DIR", str(dist_dir))

    app = create_app()
    with TestClient(app) as client:
        index = client.get("/")
        assert index.status_code == 200
        assert "text/html" in index.headers.get("content-type", "")
        assert index.headers.get("cache-control") == "no-store"
        assert "OK" in index.text

        asset = client.get("/assets/app.js")
        assert asset.status_code == 200
        assert "console.log" in asset.text
        assert asset.headers.get("cache-control") == "public, max-age=31536000, immutable"

        # SPA fallback should return index.html for unknown client routes.
        fallback = client.get("/some/client/route")
        assert fallback.status_code == 200
        assert "OK" in fallback.text
        assert fallback.headers.get("cache-control") == "no-store"


def test_static_serving_index_without_assets_dir(tmp_path: Path, monkeypatch) -> None:
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir(parents=True)
    (dist_dir / "index.html").write_text(
        "<!doctype html><html><body>NOASSETS</body></html>", encoding="utf-8"
    )

    monkeypatch.setenv("COMMANDDECK_FRONTEND_DIST_DIR", str(dist_dir))

    app = create_app()
    with TestClient(app) as client:
        index = client.get("/")
        assert index.status_code == 200
        assert "NOASSETS" in index.text
        assert index.headers.get("cache-control") == "no-store"

        # No assets directory: requests under /assets fall through to the SPA fallback.
        asset = client.get("/assets/app.js")
        assert asset.status_code == 200
        assert "NOASSETS" in asset.text
        assert asset.headers.get("cache-control") == "no-store"
