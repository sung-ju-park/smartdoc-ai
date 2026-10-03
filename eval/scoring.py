"""답변 채점 규칙

- 답변 가능 질문: 정답 키워드가 모두 들어 있으면 정답으로 본다.
  키워드 하나는 문자열이거나 '대체 표현 목록'(그중 하나만 있어도 인정)이다.
  "re:"로 시작하면 정규식으로 검사한다. (예: '프로젝트'의 '프로'를 '직위 프로'로 잘못 세지 않도록)
- 답변 불가 질문: 모른다고 답하면(거절) 정답으로 본다.
- 검색 성공 여부: 정답 키워드가 '검색된 문단'에 이미 있었는지 확인해서
  틀린 답이 검색 실패 때문인지, 검색은 됐는데 생성에서 틀린 건지 구분한다.
"""
import re

# 문서에 근거가 없다고 말하는 표현들 (너무 넓은 '없습니다'는 일부러 넣지 않았다)
REFUSAL_PATTERNS = [
    "모르", "모릅", "모름", "알 수 없", "찾을 수 없", "확인할 수 없", "확인되지 않",
    "제공되지 않", "나와 있지 않", "나와있지 않", "포함되어 있지 않", "언급되어 있지 않",
    "언급되지 않", "명시되지 않", "명시되어 있지 않", "기재되어 있지 않",
    "찾지 못", "답변할 수 없", "답할 수 없",
]
# "정보가 없", "정보는 없음", "언급된 정보는 없습니다"처럼 조사가 달라지는 표현은 정규식으로 잡는다.
# (1차 실험에서 '정보는 없음'을, 2차 실험에서 '모릅니다'를 놓쳐 올바른 거절을 환각으로 잘못 집계한 문제를 고친 부분)
REFUSAL_REGEX = re.compile(r"(정보|내용|언급|근거|기록|자료)(이|가|은|는|도)?\s*없")

# 한국어 답변에 섞이면 안 되는 문자: 일본어 히라가나/가타카나, 한자
FOREIGN_SCRIPT = re.compile(r"[\u3040-\u30ff\u4e00-\u9fff]")


def _norm(text: str) -> str:
    return re.sub(r"\s+", "", text or "").lower()


def _match_one(text: str, option: str) -> bool:
    if option.startswith("re:"):
        return re.search(option[3:], text or "", flags=re.IGNORECASE) is not None
    return _norm(option) in _norm(text)


def keyword_hits(text: str, keywords: list) -> list[bool]:
    hits = []
    for kw in keywords:
        options = kw if isinstance(kw, list) else [kw]
        hits.append(any(_match_one(text, opt) for opt in options))
    return hits


def is_refusal(answer: str) -> bool:
    a = _norm(answer)
    if any(_norm(p) in a for p in REFUSAL_PATTERNS):
        return True
    return REFUSAL_REGEX.search(answer or "") is not None


def has_foreign_script(answer: str) -> bool:
    return bool(FOREIGN_SCRIPT.search(answer or ""))


def score(item: dict, answer: str, contexts: list[str] | None, retrieval_hit: bool | None = None) -> dict:
    """contexts가 None이면(저장된 결과를 다시 채점할 때) 기록해 둔 retrieval_hit 값을 그대로 쓴다."""
    refused = is_refusal(answer)
    foreign = has_foreign_script(answer)

    if not item["answerable"]:
        return {
            "correct": refused,
            "partial": 1.0 if refused else 0.0,
            "refused": refused,
            "retrieval_hit": None,
            "failure_type": "" if refused else "hallucination",
            "foreign_script": foreign,
        }

    hits = keyword_hits(answer, item["keywords"])
    correct = all(hits)
    if contexts is not None:
        retrieval_hit = all(keyword_hits("\n".join(contexts), item["keywords"]))

    if correct:
        failure = ""
    elif not retrieval_hit:
        failure = "retrieval_miss"      # 필요한 문단을 검색해오지 못함
    elif refused:
        failure = "false_refusal"       # 근거가 있는데 모른다고 함
    else:
        failure = "generation_miss"     # 근거는 있었는데 답을 잘못 만듦

    return {
        "correct": correct,
        "partial": sum(hits) / len(hits),
        "refused": refused,
        "retrieval_hit": retrieval_hit,
        "failure_type": failure,
        "foreign_script": foreign,
    }
