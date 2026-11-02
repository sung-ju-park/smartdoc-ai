"""prompts.yaml을 읽어 ChatPromptTemplate과 버전을 돌려준다."""
import os
from functools import lru_cache

import yaml
from langchain_core.prompts import ChatPromptTemplate

PROMPT_FILE = os.path.join(os.path.dirname(__file__), "prompts.yaml")


@lru_cache(maxsize=1)
def _load() -> dict:
    with open(PROMPT_FILE, encoding="utf-8") as f:
        return yaml.safe_load(f)


def get(name: str) -> ChatPromptTemplate:
    p = _load()[name]
    return ChatPromptTemplate.from_messages([("system", p["system"].strip()), ("human", p["human"])])


def version(name: str) -> str:
    return _load()[name]["version"]


def versions(*names: str) -> dict:
    """응답과 평가 결과에 남길 프롬프트 버전들."""
    data = _load()
    return {n: data[n]["version"] for n in (names or data.keys())}
