"""SmartDoc AI LLM 비교 실험

같은 문서, 같은 검색(임베딩·Chroma·top-k)을 그대로 두고
답변을 만드는 LLM과 방식(일반 RAG / Agent)만 바꿔서 결과를 비교한다.

측정 항목
  - 정답률: 답변 가능한 질문에 정답 키워드를 모두 담아 답했는가
  - 거절 정확도: 문서에 없는 질문에 지어내지 않고 모른다고 했는가 (못 하면 환각)
  - 실패 원인: 검색 실패 / 생성 실패 / 잘못된 거절
  - 외국 문자 혼입: 한국어 답변에 일본어·한자가 섞였는가
  - 응답 시간, 토큰 사용량, 예상 비용

실행 예)
  python -m eval.run_eval --doc data/uploads/박성주_AI_Engineer_포트폴리오.pdf \
      --models ollama:qwen2.5:3b openai:gpt-4o-mini --modes rag agent
"""
import argparse
import csv
import json
import os
import statistics
import time
from datetime import datetime

from langchain_core.callbacks import get_usage_metadata_callback

from backend.agent_graph import ask_agent
from backend.ingest import ingest_pdf
from backend.rag_chain import ask as rag_ask

from .models import get_llm, get_price
from .scoring import score

HERE = os.path.dirname(os.path.abspath(__file__))


def load_dataset(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def run_one(item: dict, mode: str, llm, filename: str) -> dict:
    """질문 하나를 실행하고 답변, 시간, 토큰 사용량을 돌려준다.

    API 무료 등급 한도를 지키려고 기다린 시간(wait_sec)은 응답 시간에서 뺀다.
    """
    limiter = getattr(llm, "rate_limiter", None)
    waited_before = getattr(limiter, "waited_sec", 0.0)
    with get_usage_metadata_callback() as cb:
        start = time.perf_counter()
        if mode == "rag":
            result = rag_ask(item["question"], filename, llm=llm)
            retries = 0
        else:
            result = ask_agent(item["question"], filename, llm=llm)
            retries = result.get("retries", 0)
        elapsed = time.perf_counter() - start
    wait = getattr(limiter, "waited_sec", 0.0) - waited_before
    latency = elapsed - wait

    input_tokens = sum(u.get("input_tokens", 0) for u in cb.usage_metadata.values())
    output_tokens = sum(u.get("output_tokens", 0) for u in cb.usage_metadata.values())

    return {
        "answer": result["answer"],
        "contexts": result.get("contexts", []),
        "retries": retries,
        "latency_sec": latency,
        "wait_sec": wait,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    k = (len(values) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(values) - 1)
    return values[lo] + (values[hi] - values[lo]) * (k - lo)


def summarize(rows: list[dict], model: str, mode: str) -> dict:
    ok = [r for r in rows if not r["error"]]
    ans = [r for r in ok if r["answerable"]]
    unans = [r for r in ok if not r["answerable"]]
    lat = [r["latency_sec"] for r in ok]
    price = get_price(model)

    avg_in = statistics.mean(r["input_tokens"] for r in ok) if ok else 0
    avg_out = statistics.mean(r["output_tokens"] for r in ok) if ok else 0
    cost_per_100 = None
    if price is not None and ok:
        cost_per_100 = (avg_in * price[0] + avg_out * price[1]) / 1_000_000 * 100

    return {
        "model": model,
        "mode": mode,
        "n": len(rows),
        "errors": len(rows) - len(ok),
        "accuracy": sum(r["correct"] for r in ans) / len(ans) if ans else 0,
        "partial": statistics.mean(r["partial"] for r in ans) if ans else 0,
        "refusal_acc": sum(r["refused"] for r in unans) / len(unans) if unans else 0,
        "retrieval_miss": sum(r["failure_type"] == "retrieval_miss" for r in ans),
        "generation_miss": sum(r["failure_type"] == "generation_miss" for r in ans),
        "false_refusal": sum(r["failure_type"] == "false_refusal" for r in ans),
        "hallucination": sum(r["failure_type"] == "hallucination" for r in unans),
        "foreign_script": sum(r["foreign_script"] for r in ok),
        "latency_mean": statistics.mean(lat) if lat else 0,
        "latency_median": statistics.median(lat) if lat else 0,
        "latency_p90": percentile(lat, 0.9),
        "avg_input_tokens": avg_in,
        "avg_output_tokens": avg_out,
        "cost_per_100": cost_per_100,
    }


def write_reports(out_dir: str, rows: list[dict], summaries: list[dict]) -> None:
    fields = [
        "model", "mode", "id", "answerable", "question", "answer", "correct", "partial",
        "refused", "retrieval_hit", "failure_type", "foreign_script", "retries",
        "latency_sec", "wait_sec", "input_tokens", "output_tokens", "error",
    ]
    with open(os.path.join(out_dir, "results.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    lines = [
        "# LLM 비교 실험 결과\n",
        "| 모델 | 방식 | 오류 | 정답률 | 부분점수 | 거절 정확도 | 검색 실패 | 생성 실패 | 잘못된 거절 | 환각 | 외국 문자 혼입 | 평균 응답(초) | p90 응답(초) | 평균 토큰(입력/출력) | 100문항당 비용(USD) |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for s in summaries:
        cost = "-" if s["cost_per_100"] is None else f"{s['cost_per_100']:.4f}"
        lines.append(
            f"| {s['model']} | {s['mode']} | {s['errors']} | {s['accuracy']:.0%} | {s['partial']:.2f} | "
            f"{s['refusal_acc']:.0%} | {s['retrieval_miss']} | {s['generation_miss']} | "
            f"{s['false_refusal']} | {s['hallucination']} | {s['foreign_script']} | "
            f"{s['latency_mean']:.1f} | {s['latency_p90']:.1f} | "
            f"{s['avg_input_tokens']:.0f} / {s['avg_output_tokens']:.0f} | {cost} |"
        )
    lines += [
        "",
        "- 정답률: 답변 가능 질문 중 정답 키워드를 모두 포함한 비율",
        "- 거절 정확도: 문서에 없는 질문에 모른다고 답한 비율 (못 하면 '환각'으로 집계)",
        "- 검색 실패: 정답 근거가 검색된 문단에 없었던 경우 / 생성 실패: 근거는 있었는데 답이 틀린 경우",
        "- 비용은 models.py의 PRICE_PER_1M_TOKENS를 채웠을 때만 계산",
    ]
    with open(os.path.join(out_dir, "summary.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    fail_lines = ["# 실패 사례\n"]
    for r in rows:
        if r["error"] or not r["correct"] or r["foreign_script"]:
            reason = r["error"] or r["failure_type"] or "foreign_script"
            fail_lines += [
                f"## [{r['model']} / {r['mode']}] {r['id']} — {reason}",
                f"- 질문: {r['question']}",
                f"- 답변: {str(r['answer']).strip()}",
                f"- 검색 성공 여부: {r['retrieval_hit']}",
                "",
            ]
    with open(os.path.join(out_dir, "failures.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(fail_lines) + "\n")


def main():
    parser = argparse.ArgumentParser(description="SmartDoc AI LLM 비교 실험")
    parser.add_argument("--doc", required=True, help="평가에 사용할 PDF 경로")
    parser.add_argument("--models", nargs="+", default=["ollama:qwen2.5:3b"])
    parser.add_argument("--modes", nargs="+", default=["rag", "agent"], choices=["rag", "agent"])
    parser.add_argument("--dataset", default=os.path.join(HERE, "dataset.jsonl"))
    parser.add_argument("--limit", type=int, default=0, help="빠른 테스트용: 앞에서부터 N개만 실행")
    parser.add_argument("--skip-ingest", action="store_true", help="이미 인덱싱된 문서면 다시 넣지 않음")
    args = parser.parse_args()

    filename = os.path.basename(args.doc)
    if not args.skip_ingest:
        n = ingest_pdf(args.doc, filename)
        print(f"[ingest] {filename}: {n}개 청크 저장")

    dataset = load_dataset(args.dataset)
    if args.limit:
        dataset = dataset[: args.limit]

    out_dir = os.path.join(HERE, "results", datetime.now().strftime("%Y%m%d_%H%M%S"))
    os.makedirs(out_dir, exist_ok=True)

    rows, summaries = [], []
    for model in args.models:
        llm = get_llm(model)
        # 첫 호출은 모델 로딩 시간이 섞이므로 측정에서 빼기 위해 한 번 미리 호출한다.
        try:
            llm.invoke("안녕하세요")
        except Exception as e:
            print(f"[warmup 실패] {model}: {e}")

        for mode in args.modes:
            mode_rows = []
            for i, item in enumerate(dataset, 1):
                row = {
                    "model": model, "mode": mode, "id": item["id"],
                    "answerable": item["answerable"], "question": item["question"], "error": "",
                }
                try:
                    out = run_one(item, mode, llm, filename)
                    row.update(out)
                    row.update(score(item, out["answer"], out["contexts"]))
                except Exception as e:
                    row.update({
                        "answer": "", "correct": False, "partial": 0.0, "refused": False,
                        "retrieval_hit": None, "failure_type": "", "foreign_script": False,
                        "retries": 0, "latency_sec": 0.0, "wait_sec": 0.0, "input_tokens": 0, "output_tokens": 0,
                        "error": f"{type(e).__name__}: {e}",
                    })
                mode_rows.append(row)
                mark = "ERR" if row["error"] else ("O" if row["correct"] else "X")
                print(f"[{model} / {mode}] {i}/{len(dataset)} {item['id']} {mark} ({row['latency_sec']:.1f}s)")

            rows += mode_rows
            summaries.append(summarize(mode_rows, model, mode))

    write_reports(out_dir, rows, summaries)
    with open(os.path.join(out_dir, "summary.md"), encoding="utf-8") as f:
        print("\n" + f.read())
    print(f"결과 저장 위치: {out_dir}")


if __name__ == "__main__":
    main()
