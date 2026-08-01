"""LangGraph 기반 자가 교정형(Self-Correcting) RAG Agent

rag_chain.py의 단순 RAG(검색 → 생성, 1회성)를 확장해서,
검색된 문서가 질문에 답하기 충분한지 LLM이 스스로 판단하고,
부족하면 질문을 다시 써서 재검색하는 판단 루프를 추가한 버전이다.

플로우:
    retrieve → grade_documents ─(충분)──────────→ generate → END
                              └─(부족, 재시도 가능)→ rewrite_query → retrieve (반복)
                              └─(부족, 재시도 소진)──→ generate → END
"""
from typing import Optional, TypedDict

from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama
from langgraph.graph import END, START, StateGraph

from . import config
from .ingest import get_vectorstore

MAX_RETRIES = 2


class AgentState(TypedDict):
    question: str            # 사용자에게 보여줄 원본 질문
    search_query: str        # 실제 검색에 쓰는 질문 (재작성될 수 있음)
    filename: Optional[str]
    documents: list
    grade: str                # "sufficient" | "insufficient"
    retries: int
    answer: str
    sources: list


def _llm():
    return ChatOllama(model=config.LLM_MODEL, temperature=0)


# ---------- 1. 검색 ----------
def retrieve_node(state: AgentState) -> dict:
    vectorstore = get_vectorstore()
    search_kwargs = {"k": config.RETRIEVE_TOP_K}
    if state.get("filename"):
        search_kwargs["filter"] = {"source": state["filename"]}
    retriever = vectorstore.as_retriever(search_kwargs=search_kwargs)
    docs = retriever.invoke(state["search_query"])
    return {"documents": docs}


# ---------- 2. 검색 결과 채점 ----------
GRADE_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "당신은 검색된 문서가 질문에 답하기 충분한 정보를 담고 있는지 평가하는 채점자입니다.\n"
            "문서에 질문과 관련된 내용이 있으면 'sufficient', 관련 내용이 거의 없으면 'insufficient'라고만 답하세요.\n"
            "다른 말은 하지 마세요.",
        ),
        ("human", "질문: {question}\n\n문서 내용:\n{context}"),
    ]
)


def grade_documents_node(state: AgentState) -> dict:
    context = "\n\n".join(d.page_content for d in state["documents"]) or "(검색된 문서 없음)"
    result = _llm().invoke(GRADE_PROMPT.format_messages(question=state["question"], context=context))
    grade = "sufficient" if "sufficient" in result.content.lower() else "insufficient"
    return {"grade": grade}


# ---------- 3. 질문 재작성 (검색이 부족했을 때) ----------
REWRITE_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "검색 결과가 질문에 답하기 부족했습니다. 같은 의도를 유지하면서, "
            "문서 검색에 더 적합하도록 질문을 구체적인 키워드 중심으로 다시 써주세요. "
            "재작성한 질문만 답하세요.",
        ),
        ("human", "원본 질문: {question}"),
    ]
)


def rewrite_query_node(state: AgentState) -> dict:
    result = _llm().invoke(REWRITE_PROMPT.format_messages(question=state["question"]))
    return {
        "search_query": result.content.strip(),
        "retries": state["retries"] + 1,
    }


# ---------- 4. 최종 답변 생성 ----------
ANSWER_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "당신은 업로드된 문서를 기반으로 질문에 답하는 어시스턴트입니다.\n"
            "아래 문맥에 있는 내용만 근거로 답변하세요. 문맥에서 답을 찾을 수 없으면 모른다고 솔직하게 말하세요.\n"
            "답변은 한국어로 간결하고 명확하게 작성하세요.\n\n문맥:\n{context}",
        ),
        ("human", "{question}"),
    ]
)


def generate_node(state: AgentState) -> dict:
    context = "\n\n".join(d.page_content for d in state["documents"]) or "(검색된 문서 없음)"
    result = _llm().invoke(ANSWER_PROMPT.format_messages(question=state["question"], context=context))
    sources = sorted({d.metadata.get("source", "unknown") for d in state["documents"]})
    return {"answer": result.content, "sources": sources}


# ---------- 라우팅 ----------
def route_after_grading(state: AgentState) -> str:
    if state["grade"] == "sufficient":
        return "generate"
    if state["retries"] >= MAX_RETRIES:
        # 재시도를 다 썼으면 지금까지 찾은 문서로라도 답변을 시도한다
        return "generate"
    return "rewrite_query"


def build_agent_graph():
    graph = StateGraph(AgentState)

    graph.add_node("retrieve", retrieve_node)
    graph.add_node("grade_documents", grade_documents_node)
    graph.add_node("rewrite_query", rewrite_query_node)
    graph.add_node("generate", generate_node)

    graph.add_edge(START, "retrieve")
    graph.add_edge("retrieve", "grade_documents")
    graph.add_conditional_edges(
        "grade_documents",
        route_after_grading,
        {"generate": "generate", "rewrite_query": "rewrite_query"},
    )
    graph.add_edge("rewrite_query", "retrieve")
    graph.add_edge("generate", END)

    return graph.compile()


def ask_agent(question: str, filename: Optional[str] = None) -> dict:
    app = build_agent_graph()
    initial_state: AgentState = {
        "question": question,
        "search_query": question,
        "filename": filename,
        "documents": [],
        "grade": "",
        "retries": 0,
        "answer": "",
        "sources": [],
    }
    result = app.invoke(initial_state)
    return {
        "answer": result["answer"],
        "sources": result["sources"],
        "retries": result["retries"],
    }
