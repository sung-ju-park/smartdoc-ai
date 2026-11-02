# 실패 사례

## [ollama:qwen2.5:3b / rag] A02 — false_refusal
- 질문: SmartDoc AI가 사용하는 로컬 LLM 모델은 무엇인가요?
- 답변: SmartDoc AI가 사용하는 로컬 LLM 모델은 명시되지 않았습니다. 문맥에서 언급된 정보는 모델이 어떤 LLM을 사용하는지에 대한 정보가 없습니다.
- 검색 성공 여부: True

## [ollama:qwen2.5:3b / rag] A03 — generation_miss
- 질문: SmartDoc AI의 MCP 서버가 제공하는 도구 세 가지의 이름을 알려주세요.
- 답변: SmartDoc AI의 MCP 서버가 제공하는 도구 세 가지는 PDF Upload, Chunk · Embedding, Retriever입니다.
- 검색 성공 여부: True

## [ollama:qwen2.5:3b / rag] A05 — generation_miss
- 질문: SmartDoc AI를 Claude Desktop과 연동할 때 생긴 문제는 무엇이고 어떻게 해결했나요?
- 답변: SmartDoc AI를 Claude Desktop과 연동할 때 생긴 문제는 근거가 부족한 질문에 대해 답변하지 않고, 대신 모른다고 답하며 출처와 재검색 횟수를 표시하는 것이었습니다. 이를 해결하기 위해 프롬프트와 응답 조건을 설계하고, 관련성 부족 시 재검색 루프를 추가로 구현했습니다.
- 검색 성공 여부: True

## [ollama:qwen2.5:3b / rag] A09 — generation_miss
- 질문: YOLOv8 모델의 mAP50 값은 얼마인가요?
- 답변: YOLOv8의 mAP50 값은 0.995입니다.
- 검색 성공 여부: True

## [ollama:qwen2.5:3b / rag] A17 — generation_miss
- 질문: 박성주가 엔셀에서 맡았던 최종 직위는 무엇인가요?
- 답변: 박성주가 엔셀에서 맡았던 최종 직위는 실무 엔셀(주)의 삼성 반도체 생산관리시스템(EARS, SEAM/SESA) 운영지원이었습니다.
- 검색 성공 여부: True

## [ollama:qwen2.5:3b / rag] A18 — generation_miss
- 질문: 박성주가 KDT 과정을 수료한 교육기관은 어디인가요?
- 답변: 박성주가 KDT 과정을 수료한 교육기관은 KDT입니다.
- 검색 성공 여부: True

## [ollama:qwen2.5:3b / rag] U02 — hallucination
- 질문: 박성주의 토익 점수는 몇 점인가요?
- 답변: 박성주의 토익 점수에 대한 정보는 문맥에 없음.
- 검색 성공 여부: None

## [ollama:qwen2.5:3b / agent] A02 — false_refusal
- 질문: SmartDoc AI가 사용하는 로컬 LLM 모델은 무엇인가요?
- 답변: SmartDoc AI가 사용하는 로컬 LLM 모델에 대한 정보는 문맥에서 제공되지 않았습니다.
- 검색 성공 여부: True

## [ollama:qwen2.5:3b / agent] A09 — generation_miss
- 질문: YOLOv8 모델의 mAP50 값은 얼마인가요?
- 답변: YOLOv8 모델의 mAP50 값은 0.995입니다.
- 검색 성공 여부: True

## [ollama:qwen2.5:3b / agent] A17 — generation_miss
- 질문: 박성주가 엔셀에서 맡았던 최종 직위는 무엇인가요?
- 답변: 박성주가 엔셀에서 맡았던 최종 직위는 실무 엔셀(주)의 삼성 반도체 생산관리시스템(EARS, SEAM/SESA) 운영지원이었습니다.
- 검색 성공 여부: True

