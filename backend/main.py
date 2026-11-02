"""SmartDoc AI FastAPI 백엔드

엔드포인트:
  POST /upload            - PDF 업로드 및 벡터DB 저장
  GET  /documents         - 업로드된 문서 목록 조회
  POST /ask               - 일반 RAG 답변
  POST /ask-agent         - 자가 교정형 Agent 답변
  POST /ask-agent/stream  - Agent 진행 단계를 실시간으로 받는 스트리밍 버전 (NDJSON, 한 줄에 이벤트 하나)
  GET  /                  - 상태 확인 + 사용 중인 프롬프트 버전

비동기 처리
  LLM·검색 호출은 await로 처리하고, PDF 인덱싱처럼 동기 라이브러리만 있는 작업은
  run_in_threadpool로 별도 스레드에서 돌려 이벤트 루프(다른 요청 처리)를 막지 않는다.
"""
import json
import os
import shutil

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from . import config, prompts
from .agent_graph import aask_agent, astream_agent
from .guardrails import sanitize_filename
from .ingest import ingest_pdf, list_ingested_files
from .rag_chain import aask

app = FastAPI(title="SmartDoc AI")

os.makedirs(config.UPLOAD_DIR, exist_ok=True)
os.makedirs(config.CHROMA_DIR, exist_ok=True)


class AskRequest(BaseModel):
    question: str = Field(..., max_length=1000)
    filename: str | None = None  # 특정 문서로 검색 범위를 좁히고 싶을 때 사용


def _check(req: AskRequest) -> None:
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="질문을 입력해주세요.")


@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    filename = sanitize_filename(file.filename)
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDF 파일만 업로드할 수 있습니다.")

    save_path = os.path.join(config.UPLOAD_DIR, filename)
    with open(save_path, "wb") as f:
        await run_in_threadpool(shutil.copyfileobj, file.file, f)

    chunk_count = await run_in_threadpool(ingest_pdf, save_path, filename)
    return {"filename": filename, "chunks_saved": chunk_count}


@app.get("/documents")
async def get_documents():
    return {"documents": await run_in_threadpool(list_ingested_files)}


@app.post("/ask")
async def ask_question(req: AskRequest):
    _check(req)
    return await aask(req.question, req.filename)


@app.post("/ask-agent")
async def ask_question_agent(req: AskRequest):
    """검색 결과가 부족하면 질문을 스스로 재작성해 다시 검색하는 Agent."""
    _check(req)
    return await aask_agent(req.question, req.filename)


@app.post("/ask-agent/stream")
async def ask_question_agent_stream(req: AskRequest):
    """Agent의 각 단계(검색·채점·재작성·생성·근거 확인)가 끝날 때마다 한 줄씩 보낸다."""
    _check(req)

    async def events():
        try:
            async for ev in astream_agent(req.question, req.filename):
                yield json.dumps(ev, ensure_ascii=False, default=str) + "\n"
        except Exception as e:  # 스트림 도중 오류도 이벤트로 알려 화면이 멈추지 않게 한다
            yield json.dumps({"type": "error", "detail": f"{type(e).__name__}: {e}"}, ensure_ascii=False) + "\n"

    return StreamingResponse(events(), media_type="application/x-ndjson")


@app.get("/")
async def health_check():
    return {"status": "ok", "service": "SmartDoc AI", "prompt_versions": prompts.versions()}
