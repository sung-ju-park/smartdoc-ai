"""LangGraph 기반 자가 교정형(Self-Correcting) RAG Agent

검색된 문서가 질문에 답하기 충분한지 LLM이 스스로 판단하고, 부족하면 질문을 다시 써서 재검색한다.
답변을 만든 뒤에는 근거 확인 단계(guard)를 거쳐, 근거가 없는 답변은 내보내지 않는다.

플로우:
    retrieve → grade_documents ─(충분)──────────→ generate → guard → END
                              └─(부족, 재시도 가능)→ rewrite_query → retrieve (반복)
                              └─(부족, 재시도 소진)──→ generate → guard → END

모든 노드는 비동기(async)로 동작해, FastAPI 이벤트 루프를 막지 않는다.
astream_agent()는 단계가 끝날 때마다 이벤트를 흘려보내 화면에서 진행 상황을 볼 수 있게 한다.
"""
import time
from functools import partial
from typing import AsyncIterator, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from . import prompts
from .guardrails import scrub_documents
from .rag_chain import _default_llm, finalize, retriever_for, run_sync, text_of

MAX_RETRIES = 2
PROMPTS = ("grade", "rewrite", "answer_agent")


class AgentState(TypedDict):
    question: str            # 사용자에게 보여줄 원본 질문
    search_query: str        # 실제 검색에 쓰는 질문 (재작성될 수 있음)
    filename: Optional[str]
    documents: list
    removed: list            # 문서에서 걸러낸 지시문
    grade: str               # "sufficient" | "insufficient"
    retries: int
    answer: str
    result: dict             # 근거 확인까지 끝난 최종 응답
    guard_on: bool


# ---------- 1. 검색 (+ 문서 속 지시문 걸러내기) ----------
async def retrieve_node(state: AgentState) -> dict:
    docs = await retriever_for(state.get("filename")).ainvoke(state["search_query"])
    docs, removed = scrub_documents(docs) if state.get("guard_on", True) else (docs, [])
    seen = state.get("removed", [])
    return {"documents": docs, "removed": seen + [r for r in removed if r not in seen]}


# ---------- 2. 검색 결과 채점 ----------
def parse_grade(text: str) -> str:
    text = text.lower()
    # 'insufficient' 안에도 'sufficient'가 들어 있으므로 insufficient를 먼저 확인한다
    if "insufficient" in text:
        return "insufficient"
    return "sufficient" if "sufficient" in text else "insufficient"


async def grade_documents_node(state: AgentState, llm) -> dict:
    context = "\n\n".join(d.page_content for d in state["documents"]) or "(검색된 문서 없음)"
    msg = await llm.ainvoke(prompts.get("grade").format_messages(question=state["question"], context=context))
    return {"grade": parse_grade(text_of(msg))}


# ---------- 3. 질문 재작성 (검색이 부족했을 때) ----------
async def rewrite_query_node(state: AgentState, llm) -> dict:
    msg = await llm.ainvoke(prompts.get("rewrite").format_messages(question=state["question"]))
    return {"search_query": text_of(msg).strip(), "retries": state["retries"] + 1}


# ---------- 4. 답변 생성 ----------
async def generate_node(state: AgentState, llm) -> dict:
    context = "\n\n".join(d.page_content for d in state["documents"]) or "(검색된 문서 없음)"
    msg = await llm.ainvoke(prompts.get("answer_agent").format_messages(question=state["question"], context=context))
    return {"answer": text_of(msg)}


# ---------- 5. 근거 확인 (안전장치) ----------
async def guard_node(state: AgentState) -> dict:
    return {"result": finalize(state["answer"], state["documents"], state.get("removed", []),
                               state.get("guard_on", True))}


# ---------- 라우팅 ----------
def route_after_grading(state: AgentState) -> str:
    if state["grade"] == "sufficient":
        return "generate"
    if state["retries"] >= MAX_RETRIES:
        # 재시도를 다 썼으면 지금까지 찾은 문서로라도 답변을 시도한다
        return "generate"
    return "rewrite_query"


def build_agent_graph(llm=None):
    llm = llm or _default_llm()
    graph = StateGraph(AgentState)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("grade_documents", partial(grade_documents_node, llm=llm))
    graph.add_node("rewrite_query", partial(rewrite_query_node, llm=llm))
    graph.add_node("generate", partial(generate_node, llm=llm))
    graph.add_node("guard", guard_node)

    graph.add_edge(START, "retrieve")
    graph.add_edge("retrieve", "grade_documents")
    graph.add_conditional_edges("grade_documents", route_after_grading,
                                {"generate": "generate", "rewrite_query": "rewrite_query"})
    graph.add_edge("rewrite_query", "retrieve")
    graph.add_edge("generate", "guard")
    graph.add_edge("guard", END)
    return graph.compile()


def _initial(question: str, filename: Optional[str], guard_on: bool) -> AgentState:
    return {"question": question, "search_query": question, "filename": filename, "documents": [],
            "removed": [], "grade": "", "retries": 0, "answer": "", "result": {}, "guard_on": guard_on}


def _response(state: dict, elapsed: float) -> dict:
    out = dict(state["result"])
    out["retries"] = state["retries"]
    out["prompt_versions"] = prompts.versions(*PROMPTS)
    out["elapsed_sec"] = round(elapsed, 2)
    return out


async def aask_agent(question: str, filename: Optional[str] = None, llm=None, guard_on: bool = True) -> dict:
    t0 = time.perf_counter()
    state = await build_agent_graph(llm).ainvoke(_initial(question, filename, guard_on))
    return _response(state, time.perf_counter() - t0)


def ask_agent(question: str, filename: Optional[str] = None, llm=None, guard_on: bool = True) -> dict:
    """동기 버전 (평가 스크립트용)"""
    return run_sync(aask_agent(question, filename, llm=llm, guard_on=guard_on))


def _step_info(node: str, update: dict) -> dict:
    """화면에 보여줄 단계별 요약"""
    if node == "retrieve":
        return {"chunks": len(update.get("documents", [])), "removed_injections": len(update.get("removed", []))}
    if node == "grade_documents":
        return {"grade": update.get("grade")}
    if node == "rewrite_query":
        return {"query": update.get("search_query"), "retry": update.get("retries")}
    if node == "guard":
        g = update["result"]["guard"]
        return {"level": g["level"], "issues": g["issues"]}
    return {}


async def astream_agent(question: str, filename: Optional[str] = None, llm=None,
                        guard_on: bool = True) -> AsyncIterator[dict]:
    """단계가 끝날 때마다 {"type": "step", ...}을, 마지막에 {"type": "final", ...}을 흘려보낸다.

    답변 글자를 한 글자씩 흘려보내지 않는 이유: 근거 확인(guard)을 통과하기 전의 답변을
    사용자에게 먼저 보여주지 않기 위해서다. 대신 어느 단계에 있는지는 실시간으로 보여준다.
    """
    t0 = time.perf_counter()
    state = _initial(question, filename, guard_on)
    async for chunk in build_agent_graph(llm).astream(state, stream_mode="updates"):
        for node, update in chunk.items():
            state.update(update)
            yield {"type": "step", "node": node, "elapsed_sec": round(time.perf_counter() - t0, 2),
                   **_step_info(node, update)}
    yield {"type": "final", **_response(state, time.perf_counter() - t0)}
