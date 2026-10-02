"""저장된 결과(results.csv)를 모델을 다시 돌리지 않고 다시 채점한다.

채점 규칙(scoring.py)을 고쳤을 때, 1시간 넘게 걸리는 실험을 다시 돌리는 대신
이미 저장된 답변으로 점수만 새로 계산하기 위해 만들었다.

실행 예)
  python -m eval.rescore eval/results/20261002_210207
결과는 원본을 덮어쓰지 않고 '<폴더명>_rescored' 폴더에 저장된다.
"""
import argparse
import csv
import os

from .run_eval import HERE, load_dataset, summarize, write_reports
from .scoring import score


def to_bool(v):
    if v in ("True", "true", "1"):
        return True
    if v in ("False", "false", "0"):
        return False
    return None


def main():
    parser = argparse.ArgumentParser(description="저장된 결과 다시 채점")
    parser.add_argument("result_dir", help="results.csv가 들어 있는 결과 폴더")
    parser.add_argument("--dataset", default=os.path.join(HERE, "dataset.jsonl"))
    args = parser.parse_args()

    items = {d["id"]: d for d in load_dataset(args.dataset)}
    with open(os.path.join(args.result_dir, "results.csv"), encoding="utf-8-sig") as f:
        old_rows = list(csv.DictReader(f))

    rows = []
    for r in old_rows:
        row = {
            "model": r["model"], "mode": r["mode"], "id": r["id"],
            "answerable": to_bool(r["answerable"]), "question": r["question"],
            "answer": r["answer"], "error": r["error"],
            "retries": int(r["retries"] or 0),
            "latency_sec": float(r["latency_sec"] or 0),
            "input_tokens": int(r["input_tokens"] or 0),
            "output_tokens": int(r["output_tokens"] or 0),
        }
        if row["error"]:
            row.update({"correct": False, "partial": 0.0, "refused": False,
                        "retrieval_hit": None, "failure_type": "", "foreign_script": False})
        else:
            row.update(score(items[r["id"]], r["answer"], None, to_bool(r["retrieval_hit"])))
        rows.append(row)

    summaries = []
    for key in dict.fromkeys((r["model"], r["mode"]) for r in rows):
        group = [r for r in rows if (r["model"], r["mode"]) == key]
        summaries.append(summarize(group, *key))

    out_dir = os.path.normpath(args.result_dir) + "_rescored"
    os.makedirs(out_dir, exist_ok=True)
    write_reports(out_dir, rows, summaries)
    with open(os.path.join(out_dir, "summary.md"), encoding="utf-8") as f:
        print(f.read())
    print(f"다시 채점한 결과 저장 위치: {out_dir}")


if __name__ == "__main__":
    main()
