"""读取已有答卷供内容复核；显式--record才另存人工输入的结论。无模型调用。"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

from eval_rag import save_report


PROJECT_DIR = Path(__file__).resolve().parent


def load_review_packet(report_path: Path, case_id: str) -> dict:
    """从同一次报告中配对题卡和实际结果，避免参考标准与答卷错配。"""
    raw = report_path.read_bytes()
    report = json.loads(raw)
    cases = [case for case in report["cases_snapshot"] if case["id"] == case_id]
    rows = [row for row in report["results"] if row["case_id"] == case_id]
    if len(cases) != 1 or len(rows) != 1:
        raise ValueError("题号必须唯一对应一张题卡和一份运行结果。")
    if rows[0]["run"]["status"] != "answered":
        raise ValueError("本小步只复核已生成的答案；停止/错误结果不填写答案完整性。")
    return {
        "source_report": str(report_path.resolve()),
        "source_report_sha256": hashlib.sha256(raw).hexdigest(),
        "case": cases[0],
        "row": rows[0],
    }


def build_review_record(
    packet: dict,
    answer_complete: bool,
    citations_supported: bool,
    reason: str,
    reviewer: str,
) -> dict:
    """保存复核者输入的判断，不把字段校验当作自动语义评分。"""
    if type(answer_complete) is not bool or type(citations_supported) is not bool:
        raise ValueError("两项复核结论必须是布尔值。")
    if not reason.strip() or reviewer not in {"user", "assistant"}:
        raise ValueError("需填写复核理由，并注明user或assistant。")
    return {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_report": packet["source_report"],
        "source_report_sha256": packet["source_report_sha256"],
        "case_id": packet["case"]["id"],
        "method": "manual_labels",
        "reviewer": reviewer,
        "review": {
            "answer_complete": answer_complete,
            "citations_supported": citations_supported,
            "reason": reason.strip(),
        },
        # 保留当时对照的材料，原始答卷及其中review空值保持不变。
        "case_snapshot": packet["case"],
        "run_snapshot": packet["row"]["run"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="展示已有答卷，另存人工复核记录，不调用模型。")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--record", action="store_true", help="另存所输入的复核结论。")
    parser.add_argument("--answer-complete", choices=["yes", "no"])
    parser.add_argument("--citations-supported", choices=["yes", "no"])
    parser.add_argument("--reason", default="")
    parser.add_argument("--reviewer", choices=["user", "assistant"], default="user")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.case_id):
        parser.error("题号只能包含英文字母、数字、下划线或短横线。")
    if not args.record and any([args.answer_complete, args.citations_supported, args.reason]):
        parser.error("要保存复核结论，请同时指定--record。")
    if args.record and (args.answer_complete is None or args.citations_supported is None or not args.reason.strip()):
        parser.error("记录时需要两项结论及非空理由。")
    try:
        packet = load_review_packet(args.report, args.case_id)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.error(f"无法读取待复核答卷：{error}")

    case = packet["case"]
    run = packet["row"]["run"]
    print("题号：", case["id"])
    print("问题：", case["question"])
    print("参考要点：", case["reference_facts"])
    print("实际答案：", run["answer"])
    cited_ids = run["citation_ids"]
    print("引用编号：", cited_ids)
    for doc in run["retrieved_docs"]:
        if doc["metadata"]["chunk_id"] in cited_ids:
            print(f"\n--- [{doc['metadata']['chunk_id']}] {Path(doc['metadata']['source']).name} ---")
            print(doc["page_content"])
    print("\n复核结论由复核者输入，脚本不自动判断答案或引用的语义。")
    if not args.record:
        print("当前仅展示对照材料，未保存复核结论，未调用模型。")
        return

    record = build_review_record(
        packet, args.answer_complete == "yes", args.citations_supported == "yes",
        args.reason, args.reviewer,
    )
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output = PROJECT_DIR / "evals" / "reviews" / f"{args.report.stem}_{args.case_id}_{stamp}.json"
    save_report(record, output)
    print("已另存复核结论：", record["review"])
    print("复核记录：", output)


if __name__ == "__main__":
    main()
