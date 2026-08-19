import sys
import os

# backend 패키지를 import할 수 있도록 상위 폴더를 경로에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp.server.fastmcp import FastMCP
from backend.rag_chain import ask as rag_ask
from backend.agent_graph import ask_agent
from backend.ingest import ingest_pdf

mcp = FastMCP("SmartDoc AI")


@mcp.tool()
def search_documents(question: str, filename: str | None = None) -> str:
    """업로드된 문서에서 질문과 관련된 내용을 검색하고 답변합니다 (기본 RAG)."""
    result = rag_ask(question, filename)
    sources = ", ".join(result["sources"]) if result["sources"] else "없음"
    return f"{result['answer']}\n\n[출처: {sources}]"


@mcp.tool()
def ask_document_agent(question: str, filename: str | None = None) -> str:
    """자기교정형 RAG Agent로 문서 기반 질문에 답변합니다. 검색 결과가 부족하면 스스로 질의를 재구성해 다시 검색합니다."""
    result = ask_agent(question, filename)
    sources = ", ".join(result["sources"]) if result["sources"] else "없음"
    return f"{result['answer']}\n\n[출처: {sources}, 재시도 횟수: {result['retries']}]"


@mcp.tool()
def upload_document(file_path: str) -> str:
    """로컬 PDF 파일 경로를 받아 문서를 읽고 벡터DB에 인덱싱합니다. file_path는 PDF 파일의 전체 절대경로여야 합니다."""
    if not os.path.exists(file_path):
        return f"파일을 찾을 수 없습니다: {file_path}"
    if not file_path.lower().endswith(".pdf"):
        return "PDF 파일만 업로드할 수 있습니다."
    filename = os.path.basename(file_path)
    try:
        chunk_count = ingest_pdf(file_path, filename)
        return f"'{filename}' 인덱싱 완료 — {chunk_count}개 청크로 저장됐습니다."
    except Exception as e:
        return f"인덱싱 중 오류가 발생했습니다: {str(e)}"


if __name__ == "__main__":
    mcp.run(transport="stdio")