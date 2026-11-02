import json

from fastapi.testclient import TestClient

from backend import main


def client():
    return TestClient(main.app)


def test_empty_question_rejected():
    assert client().post("/ask", json={"question": "  "}).status_code == 400


def test_upload_sanitizes_filename(monkeypatch, tmp_path):
    monkeypatch.setattr(main.config, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(main, "ingest_pdf", lambda path, name: 3)
    r = client().post("/upload", files={"file": ("../../evil.pdf", b"%PDF-1.4", "application/pdf")})
    assert r.status_code == 200 and r.json()["filename"] == "evil.pdf"
    assert (tmp_path / "evil.pdf").exists()


def test_upload_rejects_non_pdf():
    r = client().post("/upload", files={"file": ("a.txt", b"x", "text/plain")})
    assert r.status_code == 400


def test_ask_agent_json(use_fakes, docs):
    use_fakes(["sufficient", "장애 등급 1은 4시간 안에 조치해야 합니다."], docs)
    r = client().post("/ask-agent", json={"question": "조치 시간은?"}).json()
    assert r["guard"]["passed"] and r["sources"] == ["guide.pdf"]


def test_ask_agent_stream_ndjson(use_fakes, docs):
    use_fakes(["sufficient", "장애 등급 1은 4시간 안에 조치해야 합니다."], docs)
    with client().stream("POST", "/ask-agent/stream", json={"question": "조치 시간은?"}) as r:
        events = [json.loads(line) for line in r.iter_lines() if line]
    assert [e.get("node") for e in events[:-1]] == ["retrieve", "grade_documents", "generate", "guard"]
    assert events[-1]["type"] == "final"


def test_health_shows_prompt_versions():
    assert client().get("/").json()["prompt_versions"]["answer_rag"] == "answer-rag-v1"
