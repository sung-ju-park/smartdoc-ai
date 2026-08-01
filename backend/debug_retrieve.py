"""디버그용: 특정 질문으로 검색했을 때 실제로 어떤 청크가 검색되는지 그대로 출력한다.

사용법 (프로젝트 루트에서):
    python -m backend.debug_retrieve "엔셀에서 얼마나 근무했어?" 박성주_포트폴리오.pdf
    python -m backend.debug_retrieve "엔셀에서 얼마나 근무했어?"   # 전체 문서 대상
"""
import sys

from .config import RETRIEVE_TOP_K
from .ingest import get_vectorstore


def main():
    if len(sys.argv) < 2:
        print("사용법: python -m backend.debug_retrieve \"질문\" [파일명]")
        return

    question = sys.argv[1]
    filename = sys.argv[2] if len(sys.argv) > 2 else None

    vectorstore = get_vectorstore()
    search_kwargs = {"k": RETRIEVE_TOP_K}
    if filename:
        search_kwargs["filter"] = {"source": filename}

    retriever = vectorstore.as_retriever(search_kwargs=search_kwargs)
    docs = retriever.invoke(question)

    print(f"질문: {question}")
    print(f"검색된 청크 수: {len(docs)}\n")
    for i, doc in enumerate(docs, 1):
        print(f"--- 청크 {i} (출처: {doc.metadata.get('source')}) ---")
        print(doc.page_content)
        print()


if __name__ == "__main__":
    main()
