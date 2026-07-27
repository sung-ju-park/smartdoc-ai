"""SmartDoc AI 설정 값 모음"""

# Ollama 모델
LLM_MODEL = "qwen2.5:3b"
EMBEDDING_MODEL = "nomic-embed-text"

# 텍스트 분할 설정
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100

# 저장 경로
UPLOAD_DIR = "data/uploads"
CHROMA_DIR = "data/chroma_db"
COLLECTION_NAME = "smartdoc"

# 검색 시 가져올 문단 개수
RETRIEVE_TOP_K = 4
