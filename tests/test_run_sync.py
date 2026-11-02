"""동기 래퍼(run_sync) 점검: 평가 스크립트가 질문마다 토큰 수를 제대로 받는지"""
from langchain_core.callbacks import get_usage_metadata_callback
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from backend.rag_chain import run_sync


def _msg():
    return AIMessage(content="a", response_metadata={"model_name": "fake"},
                     usage_metadata={"input_tokens": 10, "output_tokens": 2, "total_tokens": 12})


def test_usage_callback_sees_every_call():
    llm = GenericFakeChatModel(messages=iter([_msg() for _ in range(3)]))
    for _ in range(3):
        with get_usage_metadata_callback() as cb:
            run_sync(llm.ainvoke("hi"))
        assert cb.usage_metadata["fake"]["input_tokens"] == 10
