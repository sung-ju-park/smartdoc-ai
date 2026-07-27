# SmartDoc AI

PDF 문서를 업로드하면, 그 문서 내용을 근거로 질문에 답변해주는 LLM 기반 문서 검색·질의응답(RAG) 서비스입니다.
외부 API 없이 **로컬 LLM(Ollama)**으로만 동작하도록 만들었습니다.

## 왜 이렇게 만들었나

- **로컬 LLM(Ollama)**: OpenAI 등 외부 API 대신 로컬에서 LLM을 실행합니다. API 비용 없이 자유롭게 실험할 수 있고, 문서 내용이 외부로 전송되지 않는다는 장점이 있습니다.
- **RAG(검색 증강 생성)**: LLM이 학습하지 않은 내용(회사 내부 문서 등)에 대해서도, 관련 문단을 검색해서 근거로 답변하도록 구성했습니다.
- **FastAPI + Streamlit 분리 구조**: 백엔드(API 서버)와 프론트엔드를 분리해서, 나중에 웹/모바일 등 다른 클라이언트로도 쉽게 확장할 수 있도록 설계했습니다.

## 아키텍처

```
PDF 업로드
  → 텍스트 추출 (PyPDFLoader)
  → 청크 분리 (RecursiveCharacterTextSplitter)
  → 임베딩 (Ollama: nomic-embed-text)
  → 벡터 저장 (Chroma)

질문 입력
  → 벡터 유사도 검색으로 관련 문단 추출
  → LLM(Ollama: qwen2.5:3b)에 문맥 + 질문 전달
  → 답변 + 출처 문서명 반환
```

## 기술 스택

| 영역 | 사용 기술 |
|---|---|
| LLM / 임베딩 | Ollama (`qwen2.5:3b`, `nomic-embed-text`) |
| RAG 파이프라인 | LangChain (`create_retrieval_chain`, `create_stuff_documents_chain`) |
| 벡터DB | Chroma |
| 백엔드 | FastAPI |
| 프론트엔드 | Streamlit |

## 폴더 구조

```
smartdoc-ai/
├── backend/
│   ├── config.py       # 모델/경로 설정값
│   ├── ingest.py       # PDF 파싱 → 청크 → 임베딩 → 벡터DB 저장
│   ├── rag_chain.py    # 검색 + LLM 답변 생성 체인
│   └── main.py         # FastAPI 엔드포인트 (/upload, /documents, /ask)
├── frontend/
│   └── app.py          # Streamlit UI
├── data/
│   ├── uploads/        # 업로드된 PDF 저장 위치
│   └── chroma_db/       # 벡터DB 저장 위치
└── requirements.txt
```

## 실행 방법

### 1. Ollama 모델 준비

```bash
ollama pull qwen2.5:3b
ollama pull nomic-embed-text
```

### 2. 패키지 설치

```bash
python -m venv venv
source venv/bin/activate   # Windows는 venv\Scripts\activate
pip install -r requirements.txt
```

### 3. 백엔드(FastAPI) 실행

```bash
uvicorn backend.main:app --reload
```

### 4. 프론트엔드(Streamlit) 실행 (새 터미널에서)

```bash
streamlit run frontend/app.py
```

브라우저에서 `http://localhost:8501`로 접속해 PDF를 업로드하고 질문해보세요.

## API 엔드포인트

| Method | Path | 설명 |
|---|---|---|
| POST | `/upload` | PDF 파일 업로드 및 벡터DB 저장 |
| GET | `/documents` | 업로드된 문서 목록 조회 |
| POST | `/ask` | 질문에 대한 답변 생성 (`{"question": "...", "filename": "선택"}`) |

## 향후 확장 계획

- LangGraph 기반 Agent로 확장: 웹 검색, 계산기 등 도구 연결
- 대화 히스토리를 반영한 멀티턴 질의응답
- Docker로 배포 환경 구성
