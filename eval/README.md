# LLM 비교 실험

SmartDoc AI의 답변 품질이 **모델과 방식(일반 RAG / Agent)에 따라 얼마나 달라지는지** 같은 조건에서 측정하는 실험입니다.

## 실험 설계

공정한 비교를 위해 **검색 단계는 모두 고정**하고, 답변을 만드는 LLM만 바꿉니다.

| 고정 | 바꾸는 것 |
|---|---|
| 문서, 청크 크기(800/100), 임베딩(`nomic-embed-text`), Chroma, top-k(4), 프롬프트 | 답변 LLM, RAG 방식(rag / agent) |

`rag_chain.ask()`와 `agent_graph.ask_agent()`에 `llm` 인자를 추가해, 기존 서비스 코드는 그대로 두고 모델만 주입할 수 있게 했습니다. 인자를 넘기지 않으면 기존처럼 로컬 Ollama 모델을 사용합니다.

## 평가 데이터셋 (`dataset.jsonl`)

포트폴리오 PDF를 대상 문서로 쓰는 질문 26개입니다.

- **답변 가능 18개**: 문서에 정답이 있는 질문. 정답 키워드(대체 표현 포함)를 모두 담아야 정답
- **답변 불가 8개**: 문서에 없는 정보를 묻는 질문. 지어내지 않고 모른다고 해야 정답

다른 문서로 실험하려면 같은 형식으로 질문을 새로 만들면 됩니다.

```json
{"id": "A01", "question": "...", "answerable": true, "keywords": [["chroma", "크로마"]]}
{"id": "U01", "question": "...", "answerable": false}
```

## 측정 지표

| 지표 | 의미 |
|---|---|
| 정답률 | 답변 가능 질문 중 정답 키워드를 모두 포함한 비율 |
| 거절 정확도 | 답변 불가 질문에 모른다고 답한 비율 (못 하면 환각) |
| 검색 실패 / 생성 실패 | 정답 근거가 검색 결과에 없었는지, 있었는데 답이 틀렸는지 구분 |
| 잘못된 거절 | 근거가 있는데도 모른다고 답한 경우 |
| 외국 문자 혼입 | 한국어 답변에 일본어·한자가 섞인 경우 (작은 모델에서 실제로 관찰된 문제) |
| 응답 시간 | 평균, p90 (첫 호출의 모델 로딩 시간은 제외) |
| 토큰 / 비용 | 질문당 평균 입력·출력 토큰, 100문항당 예상 비용 |

## 실행 방법

```powershell
# 1) 추가 패키지 (쓸 provider만)
pip install -r requirements-eval.txt

# 2) API 키 설정 (PowerShell, 현재 창에서만 유효)
$env:OPENAI_API_KEY = "sk-..."
# $env:ANTHROPIC_API_KEY = "..."
# $env:GOOGLE_API_KEY = "..."

# 3) 빠른 확인: 질문 3개만
python -m eval.run_eval --doc "data/uploads/박성주_AI_Engineer_포트폴리오.pdf" --models ollama:qwen2.5:3b --modes rag --limit 3

# 4) 본 실험
python -m eval.run_eval --doc "data/uploads/박성주_AI_Engineer_포트폴리오.pdf" `
  --models ollama:qwen2.5:3b openai:gpt-4o-mini --modes rag agent
```

프로젝트 루트(`smartdoc-ai/`)에서 실행합니다. 결과는 `eval/results/<날짜_시간>/`에 저장됩니다.

- `summary.md`: 모델·방식별 요약 표
- `results.csv`: 질문별 상세 결과 (엑셀로 열 수 있음)
- `failures.md`: 틀린 질문의 답변과 실패 원인

비용을 계산하려면 `models.py`의 `PRICE_PER_1M_TOKENS`에 각 회사 공식 가격표의 값을 넣으세요.

## 결과

> 실험 후 `summary.md`의 표와, 실패 사례에서 발견한 점을 여기에 정리합니다.
