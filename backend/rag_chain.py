"""질문을 받아 관련 문단을 검색하고 LLM으로 답변을 생성하는 RAG 체인"""
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_classic.chains.retrieval import create_retrieval_chain
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama

from . import config
from .ingest import get_vectorstore

SYSTEM_PROMPT = """당신은 업로드된 문서를 기반으로 질문에 답하는 어시스턴트입니다.
아래 문맥(context)에 있는 내용만 근거로 답변하세요.
문맥에서 답을 찾을 수 없으면 모른다고 솔직하게 말하세요.
답변은 한국어로 간결하고 명확하게 작성하세요.

문맥:
{context}
"""

prompt = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_PROMPT),
        ("human", "{input}"),
    ]
)


def build_chain(filename: str | None = None, llm=None):
    vectorstore = get_vectorstore()

    search_kwargs = {"k": config.RETRIEVE_TOP_K}
    if filename:
        search_kwargs["filter"] = {"source": filename}

    retriever = vectorstore.as_retriever(search_kwargs=search_kwargs)

    # llm을 넘기지 않으면 기존처럼 로컬 Ollama 모델을 사용한다.
    # 모델 비교 실험(eval/)에서는 다른 LLM을 주입해서 같은 파이프라인으로 비교한다.
    if llm is None:
        llm = ChatOllama(model=config.LLM_MODEL, temperature=0)

    document_chain = create_stuff_documents_chain(llm, prompt)
    return create_retrieval_chain(retriever, document_chain)


def ask(question: str, filename: str | None = None, llm=None) -> dict:
    chain = build_chain(filename, llm=llm)
    result = chain.invoke({"input": question})

    sources = sorted(
        {doc.metadata.get("source", "unknown") for doc in result.get("context", [])}
    )

    return {
        "answer": result["answer"],
        "sources": sources,
        # 평가 시 '검색 실패'와 '생성 실패'를 구분하기 위해 검색된 문단 원문도 함께 반환
        "contexts": [doc.page_content for doc in result.get("context", [])],
    }
