import io
import os
from typing import Generator

import pytest
from fastapi.testclient import TestClient

import sys
from pathlib import Path

# Add repo root to sys.path so Python can find main.py
sys.path.append(str(Path(__file__).resolve().parent.parent))

import main


@pytest.fixture(autouse=True)
def isolated_storage(tmp_path: "os.PathLike[str]") -> Generator[None, None, None]:
	# Point the app to a temporary storage directory for each test
	main.STORAGE_DIR = tmp_path
	tmp_path.mkdir(exist_ok=True)
	# Reset counters for isolation
	main.files_stored_counter = 0
	yield


@pytest.fixture
def client() -> TestClient:
	return TestClient(main.app)


def test_root_lists_endpoints(client: TestClient) -> None:
	resp = client.get("/")
	assert resp.status_code == 200
	data = resp.json()
	assert data["message"] == "File Storage API"
	assert any(ep.startswith("GET /files/") for ep in data["endpoints"])


def test_health_endpoint(client: TestClient) -> None:
	resp = client.get("/health")
	assert resp.status_code == 200
	data = resp.json()
	assert data["status"] == "healthy"
	assert data["service"] == "File Storage API"
	assert "timestamp" in data


def test_list_files_initially_empty(client: TestClient) -> None:
	resp = client.get("/files")
	assert resp.status_code == 200
	data = resp.json()
	assert data["files"] == []
	assert data["count"] == 0


def test_upload_and_download_file(client: TestClient, tmp_path) -> None:
	content = b"hello world"
	files = {"file": ("greeting.txt", io.BytesIO(content), "text/plain")}
	upload = client.post("/files", files=files)
	assert upload.status_code == 200
	up = upload.json()
	assert up["filename"] == "greeting.txt"
	assert up["size"] == len(content)

	# Listing should show the file
	list_resp = client.get("/files")
	assert list_resp.status_code == 200
	listed = list_resp.json()
	assert listed["files"] == ["greeting.txt"]
	assert listed["count"] == 1

	# Download file
	download = client.get("/files/greeting.txt")
	assert download.status_code == 200
	assert download.content == content
	assert download.headers["content-type"] == "application/octet-stream"


def test_invalid_filename_rejected_on_upload(client: TestClient) -> None:
	files = {"file": ("../hack.txt", io.BytesIO(b"oops"), "text/plain")}
	resp = client.post("/files", files=files)
	assert resp.status_code == 400
	assert resp.json()["detail"] == "Invalid filename"


def test_metrics_reflect_storage_activity(client: TestClient) -> None:
	# Initially empty
	m0 = client.get("/metrics").json()
	assert m0["files_current"] == 0
	assert m0["files_stored_total"] == 0

	# Upload two files
	for name in ("a.txt", "b.txt"):
		files = {"file": (name, io.BytesIO(name.encode()), "text/plain")}
		assert client.post("/files", files=files).status_code == 200

	m1 = client.get("/metrics").json()
	assert m1["files_current"] == 2
	assert m1["files_stored_total"] == 2
	assert m1["total_storage_bytes"] >= len("a.txt") + len("b.txt")
	assert "total_storage_mb" in m1


