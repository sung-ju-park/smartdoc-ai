"""SmartDoc AI Streamlit 프론트엔드"""
import requests
import streamlit as st

API_URL = "http://localhost:8000"

st.set_page_config(page_title="SmartDoc AI", page_icon="📄")
st.title("📄 SmartDoc AI")
st.caption("문서를 업로드하고 자유롭게 질문해보세요. (Ollama + LangChain + RAG 기반, 로컬 실행)")

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# --- 사이드바: 문서 업로드 ---
with st.sidebar:
    st.header("문서 업로드")
    uploaded_file = st.file_uploader("PDF 파일 선택", type=["pdf"])

    if uploaded_file is not None and st.button("업로드 및 인덱싱"):
        with st.spinner("문서를 분석하고 있습니다..."):
            files = {
                "file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")
            }
            try:
                res = requests.post(f"{API_URL}/upload", files=files)
                if res.status_code == 200:
                    data = res.json()
                    st.success(f"{data['filename']} 저장 완료 ({data['chunks_saved']}개 청크)")
                else:
                    st.error(f"업로드 실패: {res.text}")
            except requests.exceptions.ConnectionError:
                st.error("백엔드 서버(FastAPI)에 연결할 수 없습니다. 먼저 서버를 실행해주세요.")

    st.divider()
    st.subheader("업로드된 문서")
    try:
        docs = requests.get(f"{API_URL}/documents").json().get("documents", [])
    except requests.exceptions.ConnectionError:
        docs = []
        st.warning("백엔드 서버(FastAPI)가 실행 중인지 확인해주세요.")

    selected_doc = st.selectbox("검색 범위 (선택 안 하면 전체 문서 대상)", ["전체"] + docs)

    st.divider()
    st.subheader("응답 모드")
    mode = st.radio(
        "질문에 답하는 방식",
        ["일반 RAG", "Agent 모드 (자가 교정)"],
        help="Agent 모드는 검색 결과가 부족하면 질문을 스스로 재작성해 다시 검색합니다.",
    )

# --- 메인: 채팅 ---
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
        if msg.get("sources"):
            st.caption(f"출처: {', '.join(msg['sources'])}")

question = st.chat_input("문서에 대해 질문해보세요")

if question:
    st.session_state.chat_history.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.write(question)

    filename = None if selected_doc == "전체" else selected_doc

    with st.chat_message("assistant"):
        with st.spinner("답변을 생성하고 있습니다..."):
            try:
                endpoint = "/ask-agent" if mode.startswith("Agent") else "/ask"
                res = requests.post(
                    f"{API_URL}{endpoint}",
                    json={"question": question, "filename": filename},
                )
                if res.status_code == 200:
                    data = res.json()
                    st.write(data["answer"])
                    if data.get("sources"):
                        st.caption(f"출처: {', '.join(data['sources'])}")
                    if "retries" in data:
                        st.caption(f"검색 재시도 횟수: {data['retries']}회")
                    st.session_state.chat_history.append(
                        {
                            "role": "assistant",
                            "content": data["answer"],
                            "sources": data.get("sources", []),
                        }
                    )
                else:
                    st.error(f"오류: {res.text}")
            except requests.exceptions.ConnectionError:
                st.error("백엔드 서버에 연결할 수 없습니다. FastAPI 서버를 먼저 실행해주세요.")
