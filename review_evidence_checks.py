"""三题开发回归：默认列题，--check才逐题检索并请求资料检查模型。"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from check_evidence import build_check_prompt, check_evidence, validate_evidence_quotes
from inspect_chunks import prepare_chunks
from inspect_documents import DATA_DIR, load_documents
from retrieve import build_vectorstore


# 这里只保存问题与检索数量，不将参考答案/人工预期交给模型。
CASES = [
    {"id": "P001", "question": "文本切分为什么要设置重叠？", "k": 6},
    {"id": "P002", "question": "文档加载器除了提取正文，还会抽取哪些信息作为元数据？", "k": 3},
    {"id": "P003", "question": "这些教程的演示实验使用的电脑CPU完整型号是什么？", "k": 3},
]
OUTPUT_DIR = Path(__file__).resolve().parent / "evals" / "results"


def main() -> None:
    parser = argparse.ArgumentParser(description="三题资料检查开发回归，不生成答案、不自动重试。")
    parser.add_argument("--check", action="store_true", help="执行三题检查，最多三次模型请求。")
    parser.add_argument("--env-file", type=Path, default=Path(__file__).with_name(".env"))
    args = parser.parse_args()
    for case in CASES:
        print(f"{case['id']}，k={case['k']}：{case['question']}")
    if not args.check:
        print("当前只列出题目；增加--check才检索并调用模型。")
        return
    if not args.env_file.is_file():
        parser.error("配置文件不存在，请用--env-file指定本机.env。")

    print("\n[准备] 加载、切分并建立一次缓存嵌入模型的内存索引。", flush=True)
    docs = load_documents(DATA_DIR)
    chunks = prepare_chunks(docs)
    vectorstore = build_vectorstore(chunks)
    print(f"文档数：{len(docs)}，文本块数：{len(chunks)}", flush=True)
    results = []

    for case in CASES:
        print(f"\n--- {case['id']}：{case['question']} ---", flush=True)
        retrieved_docs = vectorstore.similarity_search(case["question"], k=case["k"])
        print("返回编号：", [doc.metadata["chunk_id"] for doc in retrieved_docs])
        prompt = build_check_prompt(case["question"], retrieved_docs)
        row = {
            **case,
            "prompt": prompt,
            "retrieved_docs": [
                {"chunk_id": doc.metadata["chunk_id"], "source": Path(doc.metadata["source"]).name,
                 "page_content": doc.page_content}
                for doc in retrieved_docs
            ],
            "model_result": None,
            "quote_check": "not_completed",
        }
        try:
            # 每题只发一次判断请求；不把标准答案放进prompt，不生成问题答案。
            result = check_evidence(prompt, args.env_file)
            row["model_result"] = result.model_dump()
            print("资料是否足够：", result.sufficient)
            print("理由：", result.reason)
            for item in result.evidence:
                print(f"依据[{item.chunk_id}]：{item.quote}")
            validate_evidence_quotes(result, retrieved_docs)
            row["quote_check"] = "passed"
            print("编号/原句存在性：通过；判断是否合理仍需人工核对。")
        except Exception as exc:
            # 单题失败也保留已返回的结果，继续其他题；不自动重试，不当成False。
            row["quote_check"] = "error"
            row["error_type"] = type(exc).__name__
            print(f"本题检查失败（{type(exc).__name__}），不计为资料不足。")
        results.append(row)

    report = {
        "scope": "三题开发回归；只核对摘录存在性，不自动计算语义准确率。已知题不是冻结测试。",
        "check_format": "sufficient/reason/evidence(chunk_id,quote)",
        "document_count": len(docs), "chunk_count": len(chunks),
        "results": results,
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    report_path = OUTPUT_DIR / f"evidence_review3_{stamp}.json"
    with report_path.open("w", encoding="utf-8", newline="\n") as file:
        file.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print("\n报告已保存：", report_path)
    print("请人工比较每题问题、原句和理由；当前未生成答案或执行自动恢复。")


if __name__ == "__main__":
    main()
