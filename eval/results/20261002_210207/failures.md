# 실패 사례

## [ollama:qwen2.5:3b / rag] A02 — false_refusal
- 질문: SmartDoc AI가 사용하는 로컬 LLM 모델은 무엇인가요?
- 답변: SmartDoc AI가 사용하는 로컬 LLM 모델은 명시되지 않았습니다. 문맥에서 언급된 것은 PDF를 업로드하고 검색, 질문에 답변하는 기능입니다. 모델의 종류나 이름은 언급되지 않았습니다.
- 검색 성공 여부: True

## [ollama:qwen2.5:3b / rag] A03 — generation_miss
- 질문: SmartDoc AI의 MCP 서버가 제공하는 도구 세 가지의 이름을 알려주세요.
- 답변: SmartDoc AI의 MCP 서버가 제공하는 도구 세 가지는 PDF Upload, Chunk & Embedding, 그리고 Retriever입니다.
- 검색 성공 여부: True

## [ollama:qwen2.5:3b / rag] A09 — generation_miss
- 질문: YOLOv8 모델의 mAP50 값은 얼마인가요?
- 답변: YOLOv8 모델의 mAP50 값은 0.995입니다.
- 검색 성공 여부: True

## [ollama:qwen2.5:3b / rag] A17 — generation_miss
- 질문: 박성주가 엔셀에서 맡았던 최종 직위는 무엇인가요?
- 답변: 박성주가 엔셀에서 맡았던 최종 직위는 삼성 반도체 생산관리시스템(EARS, SEAM/SESA) 운영지원이었습니다.
- 검색 성공 여부: True

## [ollama:qwen2.5:3b / rag] A18 — generation_miss
- 질문: 박성주가 KDT 과정을 수료한 교육기관은 어디인가요?
- 답변: 박성주가 KDT 과정을 수료한 교육기관은 KDT입니다.
- 검색 성공 여부: True

## [ollama:qwen2.5:3b / agent] A02 — generation_miss
- 질문: SmartDoc AI가 사용하는 로컬 LLM 모델은 무엇인가요?
- 답변: SmartDoc AI가 사용하는 로컬 LLM 모델은 명시되지 않았습니다.
- 검색 성공 여부: True

## [ollama:qwen2.5:3b / agent] A17 — generation_miss
- 질문: 박성주가 엔셀에서 맡았던 최종 직위는 무엇인가요?
- 답변: 박성주가 엔셀에서 맡았던 최종 직위는 실무 엔셀(주)의 삼성 반도체 생산관리시스템(EARS, SEAM/SESA) 운영지원이었습니다.
- 검색 성공 여부: True

## [ollama:qwen2.5:3b / agent] U01 — hallucination
- 질문: 박성주가 가장 좋아하는 색깔은 무엇인가요?
- 답변: 문맥에서 박성주가 좋아하는 색깔에 대한 정보는 없음.
- 검색 성공 여부: None

## [ollama:qwen2.5:3b / agent] U05 — hallucination
- 질문: YOLOv8을 학습할 때 사용한 배치 크기는 얼마인가요?
- 답변: 문맥에서 배치 크기가 정확히 언급된 정보는 없습니다. YOLOv8의 배치 크기를 파악하려면 해당 연구의 구체적인 배치 크기 설정 정보를 찾아야 합니다.
- 검색 성공 여부: None

