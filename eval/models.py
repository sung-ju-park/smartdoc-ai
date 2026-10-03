"""비교할 LLM을 'provider:model' 문자열 하나로 만들어 주는 팩토리

예)
  ollama:qwen2.5:3b
  ollama:qwen2.5:7b
  openai:gpt-4o-mini
  anthropic:claude-haiku-4-5
  gemini:gemini-2.5-flash

API 모델을 쓰려면 해당 provider의 API 키를 환경변수로 넣어야 한다.
  OPENAI_API_KEY / ANTHROPIC_API_KEY / GOOGLE_API_KEY
"""

# 100만 토큰당 가격(USD). (입력, 출력)
# 가격은 자주 바뀌므로 각 회사의 공식 가격 페이지를 보고 직접 채워 넣는다.
# 값이 None이면 비용은 계산하지 않고 토큰 수만 기록한다. 로컬 모델은 0으로 둔다.
PRICE_PER_1M_TOKENS = {
    "openai:gpt-4o-mini": None,
    "anthropic:claude-haiku-4-5": None,
    "gemini:gemini-2.5-flash": None,
}


import time

from langchain_core.rate_limiters import InMemoryRateLimiter


class TimedRateLimiter(InMemoryRateLimiter):
    """무료 등급 한도를 지키려고 기다린 시간을 따로 기록하는 rate limiter.

    응답 시간을 잴 때 이 대기 시간을 빼야 모델 자체의 응답 속도를 공정하게 비교할 수 있다.
    """

    waited_sec: float = 0.0

    def acquire(self, *, blocking: bool = True) -> bool:
        start = time.perf_counter()
        ok = super().acquire(blocking=blocking)
        self.waited_sec += time.perf_counter() - start
        return ok


def get_price(spec: str):
    if spec.startswith("ollama:"):
        return (0.0, 0.0)
    return PRICE_PER_1M_TOKENS.get(spec)


def get_llm(spec: str, temperature: float = 0):
    provider, _, model = spec.partition(":")
    if not model:
        raise ValueError(f"모델 형식이 잘못됐습니다: {spec} (예: ollama:qwen2.5:3b)")

    if provider == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(model=model, temperature=temperature)
    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=model, temperature=temperature)
    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=model, temperature=temperature)
    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        # 무료 등급은 분당 요청 수 제한이 있어서(약 10회 안팎) 요청 간격을 자동으로 벌린다.
        # 약 7~8초에 1번 = 분당 8회 정도
        limiter = TimedRateLimiter(requests_per_second=0.13, check_every_n_seconds=0.1, max_bucket_size=1)
        return ChatGoogleGenerativeAI(
            model=model, temperature=temperature, rate_limiter=limiter, max_retries=6
        )

    raise ValueError(f"지원하지 않는 provider입니다: {provider}")
