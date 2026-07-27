"""SmartDoc AI FastAPI 백엔드

엔드포인트:
  POST /upload    - PDF 업로드 및 벡터DB 저장
  GET  /documents - 업로드된 문서 목록 조회
  POST /ask       - 질문에 대한 답변 생성
"""
import os
import shutil

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel

from . import config
from .ingest import ingest_pdf, list_ingested_files
from .rag_chain import ask as rag_ask

app = FastAPI(title="SmartDoc AI")

os.makedirs(config.UPLOAD_DIR, exist_ok=True)
os.makedirs(config.CHROMA_DIR, exist_ok=True)


class AskRequest(BaseModel):
    question: str
    filename: str | None = None  # 특정 문서로 검색 범위를 좁히고 싶을 때 사용


@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDF 파일만 업로드할 수 있습니다.")

    save_path = os.path.join(config.UPLOAD_DIR, file.filename)
    with open(save_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    chunk_count = ingest_pdf(save_path, file.filename)

    return {"filename": file.filename, "chunks_saved": chunk_count}


@app.get("/documents")
async def get_documents():
    return {"documents": list_ingested_files()}


@app.post("/ask")
async def ask_question(req: AskRequest):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="질문을 입력해주세요.")

    return rag_ask(req.question, req.filename)


@app.get("/")
async def health_check():
    return {"status": "ok", "service": "SmartDoc AI"}
