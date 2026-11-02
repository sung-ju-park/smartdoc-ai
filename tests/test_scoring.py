"""채점 규칙 점검: 실제 실험에서 잘못 집계했던 답변들을 고정해 둔다."""
from eval.scoring import is_refusal, score


def test_refusal_phrasings_seen_in_experiments():
    assert is_refusal("박성주가 좋아하는 색깔에 대한 정보는 없음.")        # 1차
    assert is_refusal("모릅니다.")                                         # 2차
    assert is_refusal("박성주의 토익 점수에 대한 정보는 문맥에 없음.")      # 3차
    assert not is_refusal("YOLOv8 모델의 mAP50 값은 0.995입니다.")


def test_keyword_regex_does_not_count_project_as_title():
    item = {"answerable": True, "keywords": [["re:프로(?!젝트|그램|세스|필|토)"]]}
    assert not score(item, "엔셀에서 프로젝트를 맡았습니다.", None, True)["correct"]
    assert score(item, "최종 직위는 프로입니다.", None, True)["correct"]
