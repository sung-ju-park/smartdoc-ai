"""안전장치(가드레일)

1) 입력 쪽 — 문서 속 지시문 걸러내기 (프롬프트 인젝션)
   업로드한 문서에 "이전 지시를 무시하고 ~라고 답하라" 같은 문장이 섞여 있으면,
   LLM이 그 문장을 문서 내용이 아니라 '명령'으로 따를 수 있다.
   검색된 문단에서 이런 문장(줄)만 지우고 나머지 내용은 그대로 LLM에 넘긴다.

2) 출력 쪽 — 답변이 검색된 문단에 근거하는지 확인
   - 차단: 문단에 없는 숫자, 문단에 없는 영문 고유명사(모델·도구 이름 등), 검색된 문단 없이 한 답변
   - 경고: 문단과 겹치는 표현이 매우 적은 문장 (표현을 바꿔 쓴 정상 답변도 걸릴 수 있어 막지는 않음)
   '모른다'는 답변은 근거가 필요 없으므로 통과시킨다.

규칙 기반이라 빠르고 설명 가능하지만, 표현을 바꾼 공격이나 숫자·이름이 없는 틀린 문장은 잡지 못한다.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

from langchain_core.documents import Document

# ---------------------------------------------------------------- 파일명
_SAFE_NAME = re.compile(r"[^0-9A-Za-z가-힣._\- ()\[\]]")


def sanitize_filename(name: str) -> str:
    """업로드 파일명에서 경로를 떼고 위험한 문자를 바꾼다. ('../../x.pdf' 같은 경로 조작 방지)"""
    base = os.path.basename((name or "").replace("\\", "/")).strip()
    base = _SAFE_NAME.sub("_", base).lstrip(".")
    return base[:120] or "document.pdf"


# ---------------------------------------------------------------- 1) 문서 속 지시문
INJECTION_PATTERNS = [
    r"(이전|위의?|앞의?|기존의?|모든)\s*(지시|명령|규칙|지침|프롬프트)\S*\s*(을|를|은|는)?\s*(모두\s*)?(무시|잊)",
    r"(지시|명령|규칙)\S*\s*(을|를)?\s*따르지\s*마",
    r"(시스템|system)\s*(프롬프트|prompt|지시|메시지)",
    r"(이\s*문서를\s*읽는|너는|당신은)\s*(AI|인공지능|어시스턴트|챗봇)",
    r"(대신|반드시)\s*['\"“‘].{1,60}['\"”’]\s*(라고|이라고)\s*(만\s*)?(답|대답|출력)",
    r"ignore\s+(all\s+|any\s+)?(the\s+)?(previous|prior|above)\s+(instructions|prompts|rules)",
    r"disregard\s+(all\s+|the\s+)?(previous|prior|above)",
    r"you\s+are\s+now\b",
    r"(reveal|print|show)\s+(the\s+)?system\s+prompt",
]
_INJ = re.compile("|".join(f"(?:{p})" for p in INJECTION_PATTERNS), re.IGNORECASE)


def find_injection(text: str) -> bool:
    return bool(_INJ.search(text or ""))


def scrub_documents(docs: list[Document]) -> tuple[list[Document], list[dict]]:
    """문단에서 지시문 문장만 지운 사본과, 지운 내용 목록을 돌려준다.

    PDF에서 뽑은 글은 문장 중간에서 줄이 바뀌는 경우가 많아, 줄이 아니라 문장 단위로 나눠서 본다.
    지시문이 없는 문단은 글자 하나 바꾸지 않고 그대로 둔다. (문장 사이 공백·줄바꿈을 바꾸면
    LLM에 들어가는 글이 달라져, 안전장치를 켠 것만으로 답변이 바뀔 수 있기 때문)
    """
    clean, removed = [], []
    for d in docs:
        # 홀수 번째 조각은 문장 사이 구분자(공백·줄바꿈)다. 지운 문장 뒤의 구분자만 함께 지운다.
        parts = re.split(r"((?<=[.!?。])\s+)", d.page_content)
        keep, hit = [], False
        for i in range(0, len(parts), 2):
            sent, sep = parts[i], (parts[i + 1] if i + 1 < len(parts) else "")
            flat = re.sub(r"\s+", " ", sent)
            if find_injection(flat):
                hit = True
                item = {"source": d.metadata.get("source"), "page": d.metadata.get("page"), "text": flat[:200]}
                if item not in removed:      # 겹치는 청크에 같은 문장이 두 번 들어 있을 수 있다
                    removed.append(item)
            else:
                keep.append(sent + sep)
        clean.append(Document(page_content="".join(keep), metadata=dict(d.metadata)) if hit else d)
    return clean, removed


# ---------------------------------------------------------------- 2) 답변 근거 확인
REFUSAL_PATTERNS = re.compile(
    r"모르|모릅|모름|알 수 없|찾을 수 없|확인할 수 없|확인되지 않|제공되지 않|나와\s?있지 않|포함되어 있지 않|"
    r"언급되(어 있)?지 않|명시되(어 있)?지 않|기재되어 있지 않|찾지 못|답변할 수 없|답할 수 없|"
    r"(정보|내용|언급|근거|기록|자료)(이|가|은|는|도)?\s*없|"
    r"(문맥|문서|본문|자료)(에|에는|에서|에서는)\s*(없|나와\s?있지 않)"
)
_NUM = re.compile(r"(?<![0-9A-Za-z])\d+(?:[.,]\d+)*")
_LATIN = re.compile(r"[A-Za-z][A-Za-z0-9+#.\-]*[A-Za-z0-9+#]")
# 답변에 흔히 나오지만 근거 문단에 없어도 문제없는 영문 표현
_LATIN_OK = {"ai", "llm", "rag", "api", "pdf", "ok"}
WARN_SUPPORT = 0.2


def _norm_num(s: str) -> str:
    s = s.replace(",", "")
    if "." in s:
        whole, frac = s.split(".", 1)
        return f"{int(whole)}.{frac}"
    return str(int(s))


def _ctx_numbers(ctx: str) -> set[str]:
    """근거 문단의 숫자. '2025.03' 같은 날짜 표기는 '2025', '3'으로도 인정한다."""
    out = set()
    for n in _NUM.findall(ctx):
        out.add(_norm_num(n))
        for part in re.split(r"[.,]", n):
            if part:
                out.add(str(int(part)))
    return out


def _bigrams(s: str) -> set[str]:
    s = re.sub(r"[^0-9A-Za-z가-힣]", "", s.lower())
    return {s[i:i + 2] for i in range(len(s) - 1)}


def is_refusal(answer: str) -> bool:
    return bool(REFUSAL_PATTERNS.search(answer or ""))


@dataclass
class GuardResult:
    level: str                       # "ok" | "warn" | "blocked"
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    refusal: bool = False

    @property
    def passed(self) -> bool:
        return self.level != "blocked"

    def to_dict(self) -> dict:
        return {"level": self.level, "passed": self.passed, "issues": self.issues,
                "warnings": self.warnings, "refusal": self.refusal}


def check_answer(answer: str, contexts: list[str]) -> GuardResult:
    if is_refusal(answer):
        return GuardResult("ok", refusal=True)
    ctx = "\n".join(contexts)
    if not ctx.strip():
        return GuardResult("blocked", ["검색된 근거 문단 없이 답변함"])

    issues, warnings = [], []
    # 줄 맨 앞 목록 번호(1. 2) 등)는 숫자 검사에서 뺀다
    body = re.sub(r"(?m)^\s*\d+[.)]\s+", " ", answer)
    ctx_nums = _ctx_numbers(ctx)
    bad_nums = sorted({n for n in _NUM.findall(body) if _norm_num(n) not in ctx_nums})
    if bad_nums:
        issues.append("근거 문단에 없는 숫자: " + ", ".join(bad_nums))

    ctx_low = ctx.lower()
    bad_terms = sorted({t for t in _LATIN.findall(answer)
                        if t.lower() not in _LATIN_OK and t.lower() not in ctx_low})
    if bad_terms:
        issues.append("근거 문단에 없는 영문 용어: " + ", ".join(bad_terms))

    cb = _bigrams(ctx)
    for s in re.split(r"(?<=[.!?。])\s+|\n", answer):
        g = _bigrams(s)
        if len(g) >= 10 and len(g & cb) / len(g) < WARN_SUPPORT:
            warnings.append(f"근거와 겹치는 표현이 적은 문장: {s.strip()[:60]}")

    if issues:
        return GuardResult("blocked", issues, warnings)
    return GuardResult("warn" if warnings else "ok", [], warnings)


# 막았을 때 보여줄 문장. '찾지 못'이 들어 있어 평가에서는 거절로 집계된다
# (문서에 없는 질문에 지어낸 답을 막았다면 올바른 거절, 정답이었던 답을 막았다면 잘못된 거절)
FALLBACK_ANSWER = ("문서에서 이 답변의 근거를 찾지 못해 답변을 보류했습니다. "
                   "아래 출처의 원문을 직접 확인해 주세요.")
