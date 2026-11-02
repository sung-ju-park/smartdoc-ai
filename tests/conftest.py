"""테스트 공통 준비: Ollama·Chroma 없이 돌도록 LLM과 검색기를 가짜로 바꾼다."""
import sys
from pathlib import Path

import pytest
from langchain_core.documents import Document
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.runnables import RunnableLambda

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend import agent_graph, rag_chain  # noqa: E402

DOCS = [
    Document(page_content="SmartDoc AI는 Ollama의 qwen2.5:3b 모델과 Chroma 벡터DB를 사용한다.\n청크 크기는 800자이다.",
             metadata={"source": "guide.pdf", "page": 0}),
    Document(page_content="장애 등급 1은 4시간 안에 조치해야 한다.",
             metadata={"source": "guide.pdf", "page": 2}),
]


@pytest.fixture
def docs():
    return [Document(page_content=d.page_content, metadata=dict(d.metadata)) for d in DOCS]


@pytest.fixture
def use_fakes(monkeypatch):
    """fake(llm 응답 목록, 검색 결과)를 부르면 그대로 쓰이도록 바꾼다."""
    def apply(responses, documents):
        llm = FakeListChatModel(responses=responses)
        retr = RunnableLambda(lambda q: documents)
        monkeypatch.setattr(rag_chain, "retriever_for", lambda filename: retr)
        monkeypatch.setattr(agent_graph, "retriever_for", lambda filename: retr)
        monkeypatch.setattr(rag_chain, "_default_llm", lambda: llm)
        monkeypatch.setattr(agent_graph, "_default_llm", lambda: llm)
        return llm
    return apply
