"""Day 11：第一题或全部开发题的Dense检索与标注依据检查。

--inspect-only仅展示题目；默认复用本地嵌入缓存，不请求生成模型。
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


CASES_PATH = Path(__file__).resolve().parent / "evals" / "retrieval_cases.json"


def load_cases(path: Path) -> list[dict]:
    """文件路径→JSON文字→Python字典→题目列表。"""
    text = path.read_text(encoding="utf-8")
    data = json.loads(text)
    cases = data["cases"]
    if not isinstance(cases, list) or not cases:
        raise ValueError("评估文件的cases必须是非空列表。")
    return cases


def has_labeled_evidence(case: dict, retrieved_docs: list) -> bool:
    """检查是否有一个返回块包含标注依据；未命中仍需人工复核。"""
    for doc in retrieved_docs:
        source = Path(doc.metadata["source"]).name
        for option in case["evidence_options"]:
            # 同一块同时满足来源与正文，任一备选依据命中即可。
            if source == option["source"] and option["quote"] in doc.page_content:
                return True

    # 所有块、所有备选都检查完，仍未找到标注依据。
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Dense检索的标注依据检查，默认第一题，可检查全部题目。")
    parser.add_argument("--inspect-only", action="store_true", help="只读取展示题目，不检索。")
    parser.add_argument("--k", type=int, default=3, help="每道题Dense返回块数，须为正整数。")
    parser.add_argument("--all-cases", action="store_true", help="检查文件中的全部题目，默认只检查第一题。")
    args = parser.parse_args()
    if args.k <= 0:
        parser.error("--k 必须为正整数。")

    cases = load_cases(CASES_PATH)
    print("加载评估题数：", len(cases))

    for case in cases:
        print(f"\n--- {case['id']} ---")
        print("问题：", case["question"])
        print("参考回答（供人工理解）：", case["reference_answer"])
        print("可接受的原文依据数：", len(case["evidence_options"]))
        for number, option in enumerate(case["evidence_options"], start=1):
            print(f"  依据{number}，来源：{option['source']}")
            print("  原文：", option["quote"])

    if args.inspect_only:
        print("\n当前只读取并展示预先准备的题目和依据，尚未检索或计算命中结果。")
        return

    # 只展示题目时不导入检索依赖；本实验仅复用已经验证过的本地索引构建。
    from inspect_documents import DATA_DIR, load_documents
    from inspect_chunks import CHUNK_SIZE, CHUNK_OVERLAP, prepare_chunks
    from retrieve import build_vectorstore

    selected_cases = cases if args.all_cases else cases[:1]
    print(f"\n[1/3] 加载原资料、切分；本次检查{len(selected_cases)}题。", flush=True)
    docs = load_documents(DATA_DIR)
    chunks = prepare_chunks(docs)
    print(f"文档数：{len(docs)}，文本块数：{len(chunks)}", flush=True)
    print("[2/3] 复用缓存嵌入模型，建立内存向量索引。", flush=True)
    vectorstore = build_vectorstore(chunks)

    print("[3/3] 复用同一个索引，逐题检索并核对标注依据。", flush=True)
    hit_count = 0
    results = []
    for case in selected_cases:
        question = case["question"]  # 只传问题，不把标注依据交给检索器。
        retrieved_docs = vectorstore.similarity_search(question, k=args.k)
        hit = has_labeled_evidence(case, retrieved_docs)
        if hit:
            hit_count += 1  # 每题最多计1次，不按命中的块数计数。

        print(f"\n{case['id']}：{question}", flush=True)
        print("返回编号：", [doc.metadata["chunk_id"] for doc in retrieved_docs])
        print("标注依据命中：", hit)
        # 完整正文保存进报告，控制台只显示摘要，便于逐题人工复核。
        results.append({
            "case_id": case["id"],
            "question": question,
            "labeled_evidence_hit": hit,
            "retrieved_docs": [
                {"chunk_id": doc.metadata["chunk_id"],
                 "source": Path(doc.metadata["source"]).name,
                 "page_content": doc.page_content}
                for doc in retrieved_docs
            ],
        })

    print(f"\n标注依据命中题数：{hit_count}/{len(selected_cases)}")
    print("未命中的题仍需人工复核其他有效依据或标注遗漏。")

    # 保存本次题目/标注与实际返回原文，不覆盖以前的实验报告。
    now = datetime.now(timezone.utc)
    report = {
        "created_at_utc": now.isoformat(),
        "scope": "标注依据命中题数，开发集检查；不是独立测试或生成答案准确率。",
        "configuration": {"retriever": "dense", "k": args.k,
                          "embedding_model": "BAAI/bge-small-zh-v1.5",
                          "document_count": len(docs), "chunk_count": len(chunks),
                          "chunk_size": CHUNK_SIZE, "chunk_overlap": CHUNK_OVERLAP},
        "case_count": len(selected_cases), "hit_count": hit_count,
        "cases_snapshot": selected_cases, "results": results,
        "generation_called": False,
    }
    output_dir = CASES_PATH.parent / "results"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"dense_k{args.k}_{now.strftime('%Y%m%dT%H%M%S%fZ')}.json"
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("报告已保存：", output_path)
    print("本次只检查Dense一种方式；结果限本题组和配置，未调用生成模型。")


if __name__ == "__main__":
    main()
