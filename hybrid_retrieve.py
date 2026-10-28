"""Day 10：取得两路候选、合并去重，并按原始名次累计RRF分数。

复用当前资料、切分、Dense与中文BM25流程，融合排序后选原文块，不生成回答。
仅使用已有本地嵌入缓存，不下载新模型，不读取生成模型密钥。
"""

import argparse
from pathlib import Path

from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document

from bm25_retrieve import tokenize
from inspect_chunks import prepare_chunks
from inspect_documents import DATA_DIR, load_documents
from retrieve import build_vectorstore


def merge_candidates(
    dense_docs: list[Document], bm25_docs: list[Document]
) -> list[Document]:
    """按编号去重、保留首次出现的原文块；列表顺序不是融合排名。"""
    merged_docs = []
    seen_ids = set()

    for doc in dense_docs + bm25_docs:
        chunk_id = doc.metadata["chunk_id"]
        if chunk_id in seen_ids:
            continue  # 同一块另一条检索路径已找到，不重复放入。

        merged_docs.append(doc)  # 保存完整原文和metadata，不只是编号。
        seen_ids.add(chunk_id)  # 只记录编号，供后面检查重复。

    return merged_docs


def calculate_rrf_scores(
    dense_docs: list[Document],
    bm25_docs: list[Document],
    rank_constant: int = 60,
) -> dict[str, float]:
    """输入每路不重复的排名列表，返回编号到等权RRF总分的字典。"""
    if rank_constant <= 0:
        raise ValueError("rank_constant 必须大于0。")
    scores = {}

    # 分别处理原来的两份排名；不能用合并后的列表位置替代。
    for result_list in [dense_docs, bm25_docs]:
        for rank, doc in enumerate(result_list, start=1):
            chunk_id = doc.metadata["chunk_id"]
            contribution = 1.0 / (rank_constant + rank)
            if chunk_id not in scores:
                scores[chunk_id] = 0.0
            scores[chunk_id] += contribution  # 同编号可累加另一路贡献。

    return scores


def rank_candidates(
    merged_docs: list[Document], rrf_scores: dict[str, float]
) -> list[Document]:
    """按RRF总分从高到低排完整原文块；同分保留合并时的先后。"""
    def get_score(doc: Document) -> float:
        return rrf_scores[doc.metadata["chunk_id"]]

    # sorted是稳定排序：同分时保持首次出现顺序（本基线Dense优先）。
    # 同分先后是固定处理规则，不代表对原文内容的进一步判断。
    return sorted(merged_docs, key=get_score, reverse=True)


def print_results(label: str, docs: list[Document]) -> None:
    """只负责展示：两路都显示完整原文，方便人工核对依据。"""
    print(f"\n--- {label}：返回 {len(docs)} 个原文块 ---")
    for rank, doc in enumerate(docs, start=1):
        print(f"\n排名 {rank}，编号 {doc.metadata['chunk_id']}")
        print("来源：", Path(doc.metadata["source"]).name)
        print("正文字符数：", len(doc.page_content))
        print(doc.page_content)


def main() -> None:
    parser = argparse.ArgumentParser(description="混合检索准备：同一问题分别查Dense和BM25。")
    parser.add_argument("--question", default="文本切分为什么要设置重叠？", help="两路共用的问题。")
    parser.add_argument("--candidate-k", type=int, default=3, help="每一路各取几块，不是最终融合数量。")
    parser.add_argument("--k", type=int, default=3, help="融合排序后最终保留几块。")
    args = parser.parse_args()
    if args.candidate_k <= 0:
        parser.error("--candidate-k 必须为正整数。")
    if args.k <= 0:
        parser.error("--k 必须为正整数。")
    if not tokenize(args.question):
        parser.error("问题须包含有效文字或数字。")

    question = args.question
    candidate_k = args.candidate_k
    print("[1/6] 只加载、切分一次，给两路提供同一批带编号的块。", flush=True)
    docs = load_documents(DATA_DIR)
    chunks = prepare_chunks(docs)
    if not chunks:
        raise ValueError("没有文本块，无法建立检索索引。")
    print(f"文档数：{len(docs)}，文本块数：{len(chunks)}", flush=True)

    print("[2/6] 准备两种检索工具：本地向量库和中文BM25。", flush=True)
    vectorstore = build_vectorstore(chunks)
    bm25_retriever = BM25Retriever.from_documents(
        chunks,
        preprocess_func=tokenize,
        k=candidate_k,
    )

    print(f"[3/6] 同一个问题分别查询两路：{question}", flush=True)
    # 两路使用同一批编号和同一个问题，返回值分别保存，下一阶段才能融合。
    dense_docs = vectorstore.similarity_search(question, k=candidate_k)
    bm25_docs = bm25_retriever.invoke(question)

    print_results("Dense向量检索", dense_docs)
    print_results("BM25关键词检索", bm25_docs)

    print("\n[4/6] 合并两份结果，按原文块编号去重。", flush=True)
    merged_docs = merge_candidates(dense_docs, bm25_docs)
    print("合并前条数：", len(dense_docs) + len(bm25_docs))
    print("去重后块数：", len(merged_docs))
    print("候选编号（首次出现顺序，并非融合排名）：", [doc.metadata["chunk_id"] for doc in merged_docs])
    print("\n[5/6] 使用两路原始名次累计RRF分数，常数为60。", flush=True)
    rrf_scores = calculate_rrf_scores(dense_docs, bm25_docs)
    for doc in merged_docs:
        chunk_id = doc.metadata["chunk_id"]
        print(f"{chunk_id}：{rrf_scores[chunk_id]:.8f}")
    print("\n[6/6] 按总分降序排列，同分保持首次出现顺序。", flush=True)
    ranked_docs = rank_candidates(merged_docs, rrf_scores)
    final_docs = ranked_docs[:args.k]
    print("全部融合排名：", [doc.metadata["chunk_id"] for doc in ranked_docs])
    print(f"最终取前 {args.k} 块，实际返回 {len(final_docs)} 块。")
    print_results("融合检索最终原文", final_docs)
    print("\n当前完成融合检索，仍需人工核对最终块是否支持问题；未调用生成模型。")


if __name__ == "__main__":
    main()
