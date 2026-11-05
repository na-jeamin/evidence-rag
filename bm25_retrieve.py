"""Day 9：用相同中文分词规则处理资料和问题，返回 BM25 原文块。

--inspect-only 可只观察问题分词。评分与中文分词来源见 SOURCES.md。
不加载嵌入/生成模型，不读取密钥；索引当前在内存里每次重建。
"""

import argparse
from pathlib import Path

import jieba
from langchain_community.retrievers import BM25Retriever

from inspect_chunks import prepare_chunks
from inspect_documents import CORPUS_DIRS, load_documents


def tokenize(text: str) -> list[str]:
    """中文切词、英文转小写，去掉空白和纯标点，返回词列表。"""
    raw_terms = jieba.lcut(text)
    terms = []
    for term in raw_terms:
        word = term.strip().lower()
        # 清理 jieba 已切好的词；chunk_overlap 实际会被拆开，纯下划线被过滤。
        if word and any(char.isalnum() for char in word):
            terms.append(word)
    return terms


def main() -> None:
    parser = argparse.ArgumentParser(description="中文 BM25 检索，或只观察问题分词。")
    parser.add_argument("--question", default="文本切分为什么要设置重叠？", help="本次检索的问题。")
    parser.add_argument("--k", type=int, default=3, help="返回的原文块数量，须为正整数。")
    parser.add_argument("--inspect-only", action="store_true", help="只观察分词，不建索引或检索。")
    parser.add_argument("--corpus", choices=CORPUS_DIRS, default="baseline", help="baseline为原三篇，full为固定版本21篇。")
    args = parser.parse_args()
    if args.k <= 0:
        parser.error("--k 必须为正整数。")

    question = args.question
    print("原问题：", question)
    print("仅按空格拆分：", question.split())
    query_terms = tokenize(question)
    print("中文分词并清理：", query_terms)
    if not query_terms:
        raise ValueError("问题没有有效词项，请输入文字或数字。")
    if args.inspect_only:
        print("\n当前只观察问题分词，尚未为文本块建立 BM25 索引或返回检索结果。")
        return

    print("\n[1/3] 复用相同资料与切分配置。", flush=True)
    docs = load_documents(CORPUS_DIRS[args.corpus])
    chunks = prepare_chunks(docs)
    if not chunks:
        raise ValueError("切分后没有文本块，不能建立 BM25 索引。")
    print(f"资料选择：{args.corpus}", flush=True)
    print(f"完整文档数：{len(docs)}，文本块数：{len(chunks)}", flush=True)

    print("[2/3] 用同一分词规则处理各块正文，建立 BM25 索引。", flush=True)
    # 交入的是函数本身：检索器在建索引、处理问题时分别调用它。
    retriever = BM25Retriever.from_documents(
        chunks,
        preprocess_func=tokenize,
        k=args.k,
    )

    print(f"[3/3] 按问题检索：{question}", flush=True)
    # invoke 接收原问题字符串，内部按 tokenize 处理后评分；不是传词列表。
    retrieved_docs = retriever.invoke(question)
    print(f"\nBM25 返回 {len(retrieved_docs)} 个块：")
    for rank, doc in enumerate(retrieved_docs, start=1):
        print(f"\n--- 排名 {rank}，原文块 {doc.metadata['chunk_id']} ---")
        print("来源：", Path(doc.metadata["source"]).name)
        print("完整正文字符数：", len(doc.page_content))
        print("完整正文：")
        print(doc.page_content)
    print("\n当前输出为 BM25 检索原文，需对照内容判断依据是否充分；尚未调用生成模型。")


if __name__ == "__main__":
    main()
