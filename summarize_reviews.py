"""汇总一份答卷报告对应的人工复核记录，不调用模型或重新判分。"""

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent


def summarize_review_rows(report: dict, report_sha256: str, reviews: list[dict]) -> dict:
    """按原报告标识及题号配对，未复核不计为不通过。"""
    latest = {}
    for record in reviews:
        if record.get("source_report_sha256") != report_sha256:
            continue
        if record.get("method") != "manual_labels":
            raise ValueError("本入口目前只汇总明确标注的人工复核记录。")
        review = record["review"]
        for key in ["answer_complete", "citations_supported"]:
            if type(review[key]) is not bool:
                raise ValueError("复核结论须为明确布尔值，空值不能当作不通过。")
        reviewed_at = datetime.fromisoformat(record["created_at_utc"])
        if reviewed_at.tzinfo is None:
            raise ValueError("复核时间须包含时区。")
        case_id = record["case_id"]
        # 同一答卷重复复核时，每题只统计最后一次记录。
        if case_id not in latest or reviewed_at > latest[case_id][0]:
            latest[case_id] = (reviewed_at, record)

    summary = {
        "reviewed": 0, "pending": 0, "without_answer": 0,
        "answer_complete_count": 0, "citations_supported_count": 0, "rows": [],
    }
    case_ids = [row["case_id"] for row in report["results"]]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("同一报告题号重复，不能唯一配对复核结果。")
    for row in report["results"]:
        case_id = row["case_id"]
        status = row["run"]["status"]
        if status != "answered":
            summary["without_answer"] += 1
            summary["rows"].append({"case_id": case_id, "state": "without_answer", "run_status": status})
        elif case_id not in latest:
            summary["pending"] += 1
            summary["rows"].append({"case_id": case_id, "state": "pending"})
        else:
            record = latest[case_id][1]
            review = record["review"]
            summary["reviewed"] += 1
            if review["answer_complete"]:
                summary["answer_complete_count"] += 1
            if review["citations_supported"]:
                summary["citations_supported_count"] += 1
            summary["rows"].append({"case_id": case_id, "state": "reviewed",
                                    "reviewer": record["reviewer"], "review": review})
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="汇总既有答卷的复核记录，未复核与不通过分开统计。")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--reviews-dir", type=Path, default=PROJECT_DIR / "evals" / "reviews")
    args = parser.parse_args()
    try:
        raw = args.report.read_bytes()
        report = json.loads(raw)
        if not args.reviews_dir.is_dir():
            raise ValueError("复核目录不存在，请检查路径或先记录复核结论。")
        reviews = [json.loads(path.read_text(encoding="utf-8"))
                   for path in sorted(args.reviews_dir.glob("*.json"))]
        summary = summarize_review_rows(report, hashlib.sha256(raw).hexdigest(), reviews)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.error(f"无法汇总：{error}")

    for row in summary["rows"]:
        if row["state"] == "reviewed":
            print(f"{row['case_id']}：已复核，答全={row['review']['answer_complete']}，"
                  f"引用支持={row['review']['citations_supported']}，复核者={row['reviewer']}")
        elif row["state"] == "pending":
            print(f"{row['case_id']}：待复核，不能计为通过或不通过。")
        else:
            print(f"{row['case_id']}：运行状态{row['run_status']}，无答案，不计答案内容评分。")
    print(f"已复核：{summary['reviewed']}，待复核：{summary['pending']}，无答案：{summary['without_answer']}")
    print(f"已复核答卷中，答全{summary['answer_complete_count']}份，引用支持{summary['citations_supported_count']}份。")
    print("以上统计所输入的复核结论，不是本脚本自动判分；未调用模型，未修改文件。")


if __name__ == "__main__":
    main()
