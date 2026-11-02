"""질문을 받아 관련 문단을 검색하고 LLM으로 답변을 생성하는 RAG (1회 검색 → 생성)

흐름: 검색 → 문서 속 지시문 걸러내기 → 답변 생성 → 근거 확인(안전장치)
FastAPI에서는 비동기(aask)로 호출하고, 평가 스크립트·기존 코드는 동기 함수(ask)를 그대로 쓴다.
"""
import asyncio
import contextvars
import time

from langchain_ollama import ChatOllama

from . import config, prompts
from .guardrails import FALLBACK_ANSWER, check_answer, scrub_documents
from .ingest import get_vectorstore


def _default_llm():
    return ChatOllama(model=config.LLM_MODEL, temperature=0)


def text_of(message) -> str:
    """LLM 응답에서 텍스트만 꺼낸다. (Gemini 3 계열은 content를 리스트로 돌려준다)"""
    content = message.content
    if isinstance(content, str):
        return content
    return "".join(p if isinstance(p, str) else p.get("text", "")
                   for p in content if isinstance(p, (str, dict)))


def retriever_for(filename: str | None):
    search_kwargs = {"k": config.RETRIEVE_TOP_K}
    if filename:
        search_kwargs["filter"] = {"source": filename}
    return get_vectorstore().as_retriever(search_kwargs=search_kwargs)


def citations(docs) -> list[dict]:
    """출처: 파일명, 쪽 번호(1부터), 문단 앞부분"""
    out = []
    for d in docs:
        page = d.metadata.get("page")
        out.append({"source": d.metadata.get("source", "unknown"),
                    "page": page + 1 if isinstance(page, int) else None,
                    "snippet": d.page_content[:160]})
    return out


def finalize(answer: str, docs, removed: list[dict], guard_on: bool = True) -> dict:
    """근거 확인을 거쳐 최종 응답을 만든다. 차단되면 답변 대신 안내 문장을 돌려준다.

    guard_on=False는 평가용이다: 확인 결과는 기록하되 답변을 막지 않는다.
    """
    contexts = [d.page_content for d in docs]
    guard = check_answer(answer, contexts)
    shown = answer if (guard.passed or not guard_on) else FALLBACK_ANSWER
    return {
        "answer": shown,
        "raw_answer": answer,          # 평가용: 차단 전 원래 답변
        "sources": sorted({d.metadata.get("source", "unknown") for d in docs}),
        "citations": citations(docs),
        "contexts": contexts,
        "guard": {**guard.to_dict(), "removed_injections": removed, "applied": guard_on},
    }


async def aask(question: str, filename: str | None = None, llm=None, guard_on: bool = True) -> dict:
    llm = llm or _default_llm()
    t0 = time.perf_counter()
    docs = await retriever_for(filename).ainvoke(question)
    docs, removed = scrub_documents(docs) if guard_on else (docs, [])
    context = "\n\n".join(d.page_content for d in docs)
    msg = await llm.ainvoke(prompts.get("answer_rag").format_messages(question=question, context=context))
    out = finalize(text_of(msg), docs, removed, guard_on)
    out["prompt_versions"] = prompts.versions("answer_rag")
    out["elapsed_sec"] = round(time.perf_counter() - t0, 2)
    return out


_RUNNER: asyncio.Runner | None = None


def run_sync(coro):
    """동기 코드(평가 스크립트)에서 비동기 함수를 부를 때 쓰는 공용 이벤트 루프.

    질문마다 asyncio.run()으로 새 루프를 만들면, 첫 질문 때 만들어진 Ollama 비동기 연결이
    닫힌 루프에 묶여 다음 질문에서 'Event loop is closed'가 난다. 그래서 루프 하나를 계속 쓴다.

    단, 실행 문맥(context)은 호출할 때마다 새로 복사해 넘긴다. 그러지 않으면 루프가 처음 만들어질 때의
    문맥이 계속 쓰여, 질문마다 새로 건 토큰 집계 콜백이 두 번째 질문부터 기록을 못 받는다.
    """
    global _RUNNER
    if _RUNNER is None:
        _RUNNER = asyncio.Runner()
    return _RUNNER.run(coro, context=contextvars.copy_context())


def ask(question: str, filename: str | None = None, llm=None, guard_on: bool = True) -> dict:
    """동기 버전 (평가 스크립트용)"""
    return run_sync(aask(question, filename, llm=llm, guard_on=guard_on))
