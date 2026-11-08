"""完整问答评估的起步入口：默认展示题卡，--run实际运行并保存逐题记录。"""

import argparse
from contextlib import redirect_stdout
from datetime import datetime, timezone
import io
import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from time import perf_counter

from eval_retrieval import load_cases


PROJECT_DIR = Path(__file__).resolve().parent


def save_report(report: dict, output_path: Path) -> None:
    """每题结束保存一次，完整写好后替换报告文件。"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        dir=output_path.parent, prefix=".rag-report-", suffix=".tmp", delete=False
    ) as temporary:
        temporary_path = Path(temporary.name)
    try:
        temporary_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
        temporary_path.replace(output_path)
    finally:
        temporary_path.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="按题卡运行RAG，保存答案、引用、状态和耗时。")
    parser.add_argument("--cases", type=Path, default=PROJECT_DIR / "evals" / "rag_cases.json")
    parser.add_argument("--split", choices=["dev", "holdout", "insufficient"], default="dev")
    parser.add_argument("--case-id", help="只选当前分组中的指定题号。")
    parser.add_argument("--index", type=Path, default=PROJECT_DIR / "artifacts" / "indexes" / "full.json")
    parser.add_argument("--strategy", choices=["dense", "hybrid"], default="hybrid")
    parser.add_argument("--k", type=int, default=3)
    parser.add_argument("--candidate-k", type=int, default=6)
    parser.add_argument("--recover", action="store_true", help="资料不足时补入候选，最多复查一次。")
    parser.add_argument("--run", action="store_true", help="实际请求大模型，消耗账号额度。")
    parser.add_argument("--env-file", type=Path, default=PROJECT_DIR / ".env")
    args = parser.parse_args()
    if args.k <= 0 or args.candidate_k < args.k:
        parser.error("需要candidate-k >= k > 0。")

    cases = load_cases(args.cases)
    selected_cases = [case for case in cases if case["split"] == args.split]
    if args.case_id:
        selected_cases = [case for case in selected_cases if case["id"] == args.case_id]
    if not selected_cases:
        parser.error("当前分组/题号没有题目，请检查题卡和参数。")
    if len({case["id"] for case in selected_cases}) != len(selected_cases):
        parser.error("所选题目ID重复，请先修正题卡。")
    for case in selected_cases:
        if not isinstance(case["question"], str) or not case["question"].strip():
            parser.error("题目必须是非空文字。")
        if case["expected_status"] not in {"answered", "insufficient"}:
            parser.error("题卡expected_status须为answered或insufficient。")
        print(f"{case['id']}，预期{case['expected_status']}：{case['question']}")
    if not args.run:
        print("当前展示所选题卡；使用--run执行实际问答并记录。")
        return
    if not args.index.is_file() or not args.env_file.is_file():
        parser.error("请检查索引文件和--env-file配置路径是否存在。")

    from langchain_core.vectorstores import InMemoryVectorStore
    from check_evidence import build_hybrid_candidates, run_checked_rag
    from retrieve import create_embeddings

    print("[准备] 加载一次索引，供所选题目共用。", flush=True)
    setup_started = perf_counter()
    vectorstore = InMemoryVectorStore.load(str(args.index), embedding=create_embeddings())
    chunks = vectorstore.get_by_ids(list(vectorstore.store))
    if not chunks:
        parser.error("索引中没有文档记录，请先重新构建。")
    setup_seconds = perf_counter() - setup_started
    now = datetime.now(timezone.utc)
    output_path = PROJECT_DIR / "evals" / "results" / f"rag_runs_{args.split}_{now.strftime('%Y%m%dT%H%M%S%fZ')}.json"
    report = {
        "created_at_utc": now.isoformat(),
        "scope": "完整问答运行记录与预期行为对照，答案完整性和引用语义支持供后续逐题复核。",
        "configuration": {"index": str(args.index.resolve()), "strategy": args.strategy,
                          "k": args.k, "candidate_k": args.candidate_k, "recover": args.recover,
                          "chunk_count": len(chunks), "split": args.split},
        "setup_seconds": setup_seconds, "cases_snapshot": selected_cases, "results": [],
        "call_count_scope": "检查和回答函数的调用尝试，错误时用量可能未知。",
    }
    save_report(report, output_path)
    print("逐题报告：", output_path, flush=True)

    for case in selected_cases:
        run_record = {"question": case["question"], "status": "started"}
        trace = io.StringIO()
        started = perf_counter()
        try:
            with redirect_stdout(trace):
                if args.strategy == "hybrid":
                    candidates = build_hybrid_candidates(case["question"], chunks, vectorstore, args.candidate_k)
                else:
                    candidates = vectorstore.similarity_search(case["question"], k=args.candidate_k)
                # 参考答案/评分要点保留在评估层，答题流程只接问题与检索原文。
                run_checked_rag(case["question"], candidates, args.k, args.env_file,
                                check=True, recover=args.recover, generate_answer=True,
                                run_record=run_record)
        except KeyboardInterrupt:
            run_record["status"] = "interrupted"
            raise
        except Exception as error:
            run_record["status"] = "error"
            run_record["error_type"] = type(error).__name__
        finally:
            elapsed = perf_counter() - started
            row = {"case_id": case["id"], "expected_status": case["expected_status"],
                   "status_matches_expected": run_record["status"] == case["expected_status"],
                   "elapsed_seconds": elapsed, "run": run_record, "trace": trace.getvalue(),
                   "token_usage": None,
                   "review": {"answer_complete": None, "answer_supported": None, "citations_supported": None}}
            report["results"].append(row)
            save_report(report, output_path)
        print(f"{case['id']}：实际{run_record['status']}，预期行为符合={row['status_matches_expected']}，"
              f"检查尝试{run_record.get('check_calls', 0)}，回答尝试{run_record.get('answer_calls', 0)}，耗时{elapsed:.2f}秒",
              flush=True)

        if run_record.get("answer"):
            print("实际答案：", run_record["answer"])
            print("引用编号：", run_record.get("citation_ids", []))
        if run_record.get("checks"):
            print("最后一次资料判断：", run_record["checks"][-1]["result"]["reason"])
        if run_record["status"] == "error":
            print("错误类型：", run_record["error_type"])

    matched = sum(row["status_matches_expected"] for row in report["results"])
    print(f"预期行为符合题数：{matched}/{len(report['results'])}")
    print("答案内容和引用支持情况，接下来对照参考标准复核。")
    print("报告已保存：", output_path)


if __name__ == "__main__":
    main()
