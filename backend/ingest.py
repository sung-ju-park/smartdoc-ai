"""PDF 문서를 읽어 청크로 나누고 임베딩해서 Chroma에 저장하는 모듈"""
from langchain_chroma import Chroma
from langchain_community.document_loaders import PyPDFLoader
from langchain_ollama import OllamaEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from . import config


def get_embeddings():
    return OllamaEmbeddings(model=config.EMBEDDING_MODEL)


def get_vectorstore():
    return Chroma(
        collection_name=config.COLLECTION_NAME,
        embedding_function=get_embeddings(),
        persist_directory=config.CHROMA_DIR,
    )


def ingest_pdf(file_path: str, filename: str) -> int:
    """PDF 한 개를 읽어서 벡터DB에 저장하고, 저장된 청크 개수를 반환한다.

    같은 filename으로 이미 저장된 청크가 있으면 먼저 삭제한 뒤 새로 넣어서
    같은 문서를 다시 업로드했을 때 중복이 쌓이지 않도록 한다.
    """
    vectorstore = get_vectorstore()

    # 같은 파일명으로 이미 저장된 청크가 있으면 먼저 지운다 (재업로드 시 중복 방지)
    existing = vectorstore.get(where={"source": filename})
    if existing and existing.get("ids"):
        vectorstore.delete(ids=existing["ids"])

    loader = PyPDFLoader(file_path)
    pages = loader.load()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.CHUNK_SIZE,
        chunk_overlap=config.CHUNK_OVERLAP,
    )
    chunks = splitter.split_documents(pages)

    # 어떤 파일에서 나온 청크인지 메타데이터에 남겨서 나중에 출처를 표시할 수 있게 한다
    for chunk in chunks:
        chunk.metadata["source"] = filename

    vectorstore.add_documents(chunks)

    return len(chunks)


def list_ingested_files() -> list[str]:
    """지금까지 저장된 문서 파일명 목록 (중복 제거)"""
    vectorstore = get_vectorstore()
    data = vectorstore.get()
    sources = {meta.get("source") for meta in data.get("metadatas", []) if meta}
    return sorted(sources)
