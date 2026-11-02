"""SmartDoc AI Streamlit 프론트엔드

- Agent 모드는 /ask-agent/stream으로 단계(검색 → 채점 → 재작성 → 생성 → 근거 확인)를 실시간으로 보여준다.
- 답변마다 안전장치 결과(통과·경고·차단, 걸러낸 지시문)와 출처(파일·쪽 번호·원문 일부), 응답 시간을 함께 보여준다.
"""
import json

import requests
import streamlit as st

API_URL = "http://localhost:8000"

st.set_page_config(page_title="SmartDoc AI", page_icon="📄", layout="wide")
st.markdown("""
<style>
.block-container{max-width:960px;padding-top:2rem}
.badge{display:inline-block;padding:2px 10px;border-radius:999px;font-size:12.5px;font-weight:600;margin-right:6px}
.ok{background:#e3f4ea;color:#17663a}.warn{background:#fff4dc;color:#8a5a00}.blocked{background:#fde7e7;color:#a12828}
.muted{color:#6b7280;font-size:12.5px}
.cite{border-left:3px solid #d1d5db;padding:4px 10px;margin:6px 0;font-size:13px;color:#374151}
</style>""", unsafe_allow_html=True)

STEP_LABEL = {
    "retrieve": "🔎 문서 검색",
    "grade_documents": "🧮 검색 결과 채점",
    "rewrite_query": "✏️ 질문 다시 쓰기",
    "generate": "✍️ 답변 생성",
    "guard": "🛡️ 근거 확인",
}
GUARD_TEXT = {"ok": ("ok", "근거 확인 통과"), "warn": ("warn", "근거 약한 문장 있음"),
              "blocked": ("blocked", "근거 없는 내용이 있어 답변 보류")}


def step_line(ev: dict) -> str:
    n, t = ev["node"], f"{ev['elapsed_sec']:.1f}초"
    if n == "retrieve":
        extra = f"문단 {ev['chunks']}개"
        if ev.get("removed_injections"):
            extra += f" · 문서 속 지시문 {ev['removed_injections']}개 걸러냄"
    elif n == "grade_documents":
        extra = "충분" if ev.get("grade") == "sufficient" else "부족 → 다시 검색"
    elif n == "rewrite_query":
        extra = f"“{ev.get('query', '')}” (재시도 {ev.get('retry')}회)"
    elif n == "guard":
        extra = GUARD_TEXT[ev["level"]][1]
    else:
        extra = ""
    return f"{STEP_LABEL.get(n, n)}{' — ' + extra if extra else ''}  `{t}`"


def render_meta(data: dict) -> None:
    g = data.get("guard", {})
    cls, text = GUARD_TEXT.get(g.get("level", "ok"), GUARD_TEXT["ok"])
    if g.get("refusal"):
        text = "문서에 없는 내용이라고 답함"
    badges = f"<span class='badge {cls}'>🛡️ {text}</span>"
    if g.get("removed_injections"):
        badges += f"<span class='badge warn'>지시문 {len(g['removed_injections'])}개 걸러냄</span>"
    if "retries" in data:
        badges += f"<span class='badge ok' style='background:#eef2ff;color:#3730a3'>재검색 {data['retries']}회</span>"
    badges += f"<span class='muted'>{data.get('elapsed_sec', 0):.1f}초</span>"
    st.markdown(badges, unsafe_allow_html=True)

    issues = g.get("issues", []) + g.get("warnings", [])
    if issues or g.get("removed_injections"):
        with st.expander("안전장치 상세"):
            for i in issues:
                st.markdown(f"- {i}")
            for r in g.get("removed_injections", []):
                st.markdown(f"- 걸러낸 지시문 ({r.get('source')}): {r.get('text')}")
    cites = data.get("citations", [])
    if cites:
        with st.expander(f"출처 {len(cites)}개"):
            for c in cites:
                page = f" · {c['page']}쪽" if c.get("page") else ""
                st.markdown(f"<div class='cite'><b>{c['source']}{page}</b><br>{c['snippet']}…</div>",
                            unsafe_allow_html=True)


if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# --- 사이드바 ---
with st.sidebar:
    st.header("📄 SmartDoc AI")
    st.caption("로컬 LLM(Ollama) 기반 문서 검색·질의응답 Agent")
    try:
        health = requests.get(f"{API_URL}/", timeout=3).json()
        st.success("백엔드 연결됨")
    except requests.exceptions.RequestException:
        health = None
        st.error("백엔드(FastAPI)에 연결할 수 없습니다. 먼저 서버를 실행해주세요.")

    st.subheader("문서 업로드")
    uploaded_file = st.file_uploader("PDF 파일 선택", type=["pdf"], label_visibility="collapsed")
    if uploaded_file is not None and st.button("업로드 및 인덱싱", use_container_width=True):
        with st.spinner("문서를 분석하고 있습니다..."):
            try:
                res = requests.post(f"{API_URL}/upload",
                                    files={"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")})
                if res.ok:
                    d = res.json()
                    st.success(f"{d['filename']} 저장 완료 ({d['chunks_saved']}개 청크)")
                else:
                    st.error(f"업로드 실패: {res.text}")
            except requests.exceptions.ConnectionError:
                st.error("백엔드 서버에 연결할 수 없습니다.")

    try:
        docs = requests.get(f"{API_URL}/documents", timeout=5).json().get("documents", [])
    except requests.exceptions.RequestException:
        docs = []
    selected_doc = st.selectbox("검색 범위", ["전체 문서"] + docs)

    mode = st.radio("응답 방식", ["Agent (자가 교정 + 단계 표시)", "일반 RAG"],
                    help="Agent는 검색 결과가 부족하면 질문을 스스로 다시 써서 재검색합니다.")
    if health:
        with st.expander("프롬프트 버전"):
            st.json(health.get("prompt_versions", {}))
    if st.button("대화 지우기", use_container_width=True):
        st.session_state.chat_history = []
        st.rerun()

# --- 메인 ---
st.title("문서에 질문하기")
st.caption("답변은 업로드한 문서에 근거해서만 만들고, 근거를 확인할 수 없는 내용은 내보내지 않습니다.")

for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
        if msg.get("data"):
            render_meta(msg["data"])

question = st.chat_input("문서에 대해 질문해보세요")
if question:
    st.session_state.chat_history.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.write(question)

    filename = None if selected_doc == "전체 문서" else selected_doc
    payload = {"question": question, "filename": filename}
    with st.chat_message("assistant"):
        data = None
        try:
            if mode.startswith("Agent"):
                with st.status("Agent가 작업 중입니다…", expanded=True) as status:
                    with requests.post(f"{API_URL}/ask-agent/stream", json=payload, stream=True, timeout=600) as res:
                        for line in res.iter_lines(decode_unicode=True):
                            if not line:
                                continue
                            ev = json.loads(line)
                            if ev["type"] == "step":
                                st.markdown(step_line(ev))
                            elif ev["type"] == "final":
                                data = ev
                            elif ev["type"] == "error":
                                st.error(ev["detail"])
                    status.update(label=f"완료 ({data['elapsed_sec']:.1f}초)" if data else "오류",
                                  state="complete" if data else "error", expanded=False)
            else:
                with st.spinner("답변을 생성하고 있습니다..."):
                    res = requests.post(f"{API_URL}/ask", json=payload, timeout=600)
                    data = res.json() if res.ok else None
                    if not res.ok:
                        st.error(f"오류: {res.text}")
        except requests.exceptions.ConnectionError:
            st.error("백엔드 서버에 연결할 수 없습니다. FastAPI 서버를 먼저 실행해주세요.")

        if data:
            st.write(data["answer"])
            render_meta(data)
            st.session_state.chat_history.append({"role": "assistant", "content": data["answer"], "data": data})
