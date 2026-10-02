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
        return ChatGoogleGenerativeAI(model=model, temperature=temperature)

    raise ValueError(f"지원하지 않는 provider입니다: {provider}")
