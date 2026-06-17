"""Tests for the Voxhelm FastAPI server — all endpoints."""

import time
import pytest


def _wait_for_job(api_client, job_id, timeout=10):
    """Poll a job until done or error."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = api_client.get(f"/api/jobs/{job_id}")
        assert resp.status_code == 200
        data = resp.json()
        if data["status"] in ("done", "error"):
            return data
        time.sleep(0.1)
    raise TimeoutError(f"Job {job_id} did not complete in {timeout}s")


# ── Presets & heads listing ────────────────────────────────────────────────

def test_list_presets(api_client):
    resp = api_client.get("/api/presets")
    assert resp.status_code == 200
    presets = resp.json()
    assert len(presets) == 6
    assert all("key" in p and "description" in p for p in presets)


def test_list_heads_empty(api_client):
    resp = api_client.get("/api/heads")
    assert resp.status_code == 200
    assert resp.json() == []


def test_root_serves_html(api_client):
    resp = api_client.get("/")
    assert resp.status_code == 200
    assert "Voxhelm" in resp.text


# ── Generate base ──────────────────────────────────────────────────────────

def test_generate_base_preset_svg(api_client):
    resp = api_client.post("/api/generate-base", json={
        "mode": "svg", "preset": "young_woman",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["name"] == "young_woman"
    assert data["mode"] == "svg"


def test_generate_base_custom_prompt_svg(api_client):
    resp = api_client.post("/api/generate-base", json={
        "mode": "svg", "prompt": "robot with teal accents", "name": "robot",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "robot"


def test_generate_base_photo(api_client):
    resp = api_client.post("/api/generate-base", json={
        "mode": "photo", "prompt": "woman, 30s, dark hair", "name": "photo_test",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "photo"
    assert "cost" in data


def test_generate_base_bad_mode(api_client):
    resp = api_client.post("/api/generate-base", json={
        "mode": "invalid", "prompt": "test",
    })
    assert resp.status_code == 400


def test_generate_base_no_input(api_client):
    resp = api_client.post("/api/generate-base", json={"mode": "svg"})
    assert resp.status_code == 400


# ── Generate visemes (async) ──────────────────────────────────────────────

def test_generate_visemes_svg(api_client):
    api_client.post("/api/generate-base", json={
        "mode": "svg", "preset": "young_man",
    })
    resp = api_client.post("/api/generate-visemes", json={"head": "young_man"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert "job_id" in data
    # Wait for completion
    job = _wait_for_job(api_client, data["job_id"])
    assert job["status"] == "done"


def test_generate_visemes_photo(api_client):
    api_client.post("/api/generate-base", json={
        "mode": "photo", "prompt": "test person", "name": "photo_vis",
    })
    resp = api_client.post("/api/generate-visemes", json={"head": "photo_vis"})
    assert resp.status_code == 200
    job = _wait_for_job(api_client, resp.json()["job_id"])
    assert job["status"] == "done"
    assert job["cost"] is not None


def test_generate_visemes_missing_head(api_client):
    resp = api_client.post("/api/generate-visemes", json={"head": "nonexistent"})
    assert resp.status_code == 404


# ── One-shot generate (async visemes) ──────────────────────────────────────

def test_generate_full_svg(api_client):
    resp = api_client.post("/api/generate", json={
        "mode": "svg", "preset": "older_man",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert "job_id" in data
    job = _wait_for_job(api_client, data["job_id"])
    assert job["status"] == "done"


def test_generate_full_photo(api_client):
    resp = api_client.post("/api/generate", json={
        "mode": "photo", "prompt": "test", "name": "oneshot_photo",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "photo"
    job = _wait_for_job(api_client, data["job_id"])
    assert job["status"] == "done"


# ── Head assets ────────────────────────────────────────────────────────────

def test_get_assets_svg(api_client):
    # Generate full set first
    resp = api_client.post("/api/generate", json={
        "mode": "svg", "preset": "young_woman",
    })
    _wait_for_job(api_client, resp.json()["job_id"])

    resp = api_client.get("/api/head/young_woman/assets")
    assert resp.status_code == 200
    data = resp.json()
    assert data["complete"] is True
    assert data["visemes"] == 15
    assert "sil" in data["assets"]
    assert data["assets"]["sil"]["type"] == "svg"


def test_get_assets_photo(api_client):
    resp = api_client.post("/api/generate", json={
        "mode": "photo", "prompt": "test", "name": "assets_photo",
    })
    _wait_for_job(api_client, resp.json()["job_id"])

    resp = api_client.get("/api/head/assets_photo/assets")
    assert resp.status_code == 200
    data = resp.json()
    assert data["assets"]["sil"]["type"] == "png"
    assert data["assets"]["sil"]["data"].startswith("data:image/png;base64,")
    assert "cost" in data


def test_get_assets_not_found(api_client):
    resp = api_client.get("/api/head/nonexistent/assets")
    assert resp.status_code == 404


# ── Validate ───────────────────────────────────────────────────────────────

def test_validate_head(api_client):
    resp = api_client.post("/api/generate", json={
        "mode": "svg", "preset": "young_woman",
    })
    _wait_for_job(api_client, resp.json()["job_id"])

    resp = api_client.get("/api/head/young_woman/validate")
    assert resp.status_code == 200
    assert "young_woman" in resp.text


def test_validate_head_not_found(api_client):
    resp = api_client.get("/api/head/nonexistent/validate")
    assert resp.status_code == 404


# ── Speak ──────────────────────────────────────────────────────────────────

def test_speak_success(api_client):
    resp = api_client.post("/api/generate", json={
        "mode": "svg", "preset": "young_woman",
    })
    _wait_for_job(api_client, resp.json()["job_id"])

    resp = api_client.post("/api/speak", json={
        "head": "young_woman", "text": "hello world",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "audio_b64" in data
    assert "timeline" in data
    assert len(data["timeline"]) >= 1


def test_speak_missing_head(api_client):
    resp = api_client.post("/api/speak", json={
        "head": "nonexistent", "text": "hello",
    })
    assert resp.status_code == 404


# ── Job status ─────────────────────────────────────────────────────────────

def test_job_status(api_client):
    api_client.post("/api/generate-base", json={
        "mode": "svg", "preset": "young_woman",
    })
    resp = api_client.post("/api/generate-visemes", json={"head": "young_woman"})
    job_id = resp.json()["job_id"]

    # Should be able to poll
    resp = api_client.get(f"/api/jobs/{job_id}")
    assert resp.status_code == 200
    assert resp.json()["status"] in ("running", "done")


def test_job_not_found(api_client):
    resp = api_client.get("/api/jobs/nonexistent")
    assert resp.status_code == 404


# ── Head list after generation ─────────────────────────────────────────────

def test_list_heads_after_generate(api_client):
    resp = api_client.post("/api/generate", json={
        "mode": "svg", "preset": "young_woman",
    })
    _wait_for_job(api_client, resp.json()["job_id"])

    resp = api_client.get("/api/heads")
    heads = resp.json()
    assert len(heads) >= 1
    names = [h["name"] for h in heads]
    assert "young_woman" in names


# ── Serve head files ───────────────────────────────────────────────────────

def test_serve_head_file_svg(api_client):
    resp = api_client.post("/api/generate", json={
        "mode": "svg", "preset": "young_woman",
    })
    _wait_for_job(api_client, resp.json()["job_id"])

    resp = api_client.get("/heads/young_woman/sil.svg")
    assert resp.status_code == 200


def test_serve_head_file_not_found(api_client):
    resp = api_client.get("/heads/nonexistent/sil.svg")
    assert resp.status_code == 404
