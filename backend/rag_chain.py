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


def build_chain(filename: str | None = None):
    vectorstore = get_vectorstore()

    search_kwargs = {"k": config.RETRIEVE_TOP_K}
    if filename:
        search_kwargs["filter"] = {"source": filename}

    retriever = vectorstore.as_retriever(search_kwargs=search_kwargs)

    llm = ChatOllama(model=config.LLM_MODEL, temperature=0)

    document_chain = create_stuff_documents_chain(llm, prompt)
    return create_retrieval_chain(retriever, document_chain)


def ask(question: str, filename: str | None = None) -> dict:
    chain = build_chain(filename)
    result = chain.invoke({"input": question})

    sources = sorted(
        {doc.metadata.get("source", "unknown") for doc in result.get("context", [])}
    )

    return {
        "answer": result["answer"],
        "sources": sources,
    }
