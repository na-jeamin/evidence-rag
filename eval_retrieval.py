"""Day 11：读取评估题，先对第一题执行Dense检索与标注依据检查。

--inspect-only仅展示题目；默认复用本地嵌入缓存，不请求生成模型。
"""

import argparse
import json
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
    parser = argparse.ArgumentParser(description="评估最小实验：第一题Dense检索与标注依据检查。")
    parser.add_argument("--inspect-only", action="store_true", help="只读取展示题目，不检索。")
    parser.add_argument("--k", type=int, default=3, help="第一题Dense返回块数，须为正整数。")
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
    from inspect_chunks import prepare_chunks
    from retrieve import build_vectorstore

    print("\n[1/3] 加载原资料、切分；最小实验只检查第一题。", flush=True)
    docs = load_documents(DATA_DIR)
    chunks = prepare_chunks(docs)
    print(f"文档数：{len(docs)}，文本块数：{len(chunks)}", flush=True)
    print("[2/3] 复用缓存嵌入模型，建立内存向量索引。", flush=True)
    vectorstore = build_vectorstore(chunks)

    case = cases[0]
    question = case["question"]  # 只把问题交给检索器，标注依据留给事后核对。
    print(f"[3/3] 检索{case['id']}：{question}，k={args.k}", flush=True)
    retrieved_docs = vectorstore.similarity_search(question, k=args.k)
    hit = has_labeled_evidence(case, retrieved_docs)

    print("返回编号：", [doc.metadata["chunk_id"] for doc in retrieved_docs])
    for doc in retrieved_docs:
        print(f"\n--- {doc.metadata['chunk_id']}，来源：{Path(doc.metadata['source']).name} ---")
        print(doc.page_content)
    print("\n标注依据命中：", hit)
    if not hit:
        print("当前返回块未包含标注的原文依据；仍需人工复核其他有效依据或标注遗漏。")
    print("本次只检查第一题的一种检索方式，没有计算3题整体指标，也未调用生成模型。")


if __name__ == "__main__":
    main()
