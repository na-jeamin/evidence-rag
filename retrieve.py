"""Dense 检索基线：为已切好的块计算向量，按问题返回原文片段。

沿用 all-in-rag C1 的 BGE/内存索引流程，复用本项目加载与切分函数。
仅使用本地缓存的嵌入模型，不读取生成配置或请求生成模型。
"""

import argparse
from pathlib import Path

from langchain_core.documents import Document
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_huggingface import HuggingFaceEmbeddings

from inspect_chunks import prepare_chunks
from inspect_documents import CORPUS_DIRS, load_documents


def create_embeddings() -> HuggingFaceEmbeddings:
    """构建和加载索引共用同一套嵌入模型配置。"""
    return HuggingFaceEmbeddings(
        model_name="BAAI/bge-small-zh-v1.5",
        model_kwargs={"device": "cpu", "local_files_only": True},
        encode_kwargs={"normalize_embeddings": True},
    )


def build_vectorstore(chunks: list[Document]) -> InMemoryVectorStore:
    """让向量库调用嵌入模型计算各块向量，并对应保存正文与 metadata。"""
    vectorstore = InMemoryVectorStore(create_embeddings())
    vectorstore.add_documents(chunks)
    return vectorstore


def main() -> None:
    parser = argparse.ArgumentParser(description="本地向量检索，输出带编号与来源的原文片段。")
    parser.add_argument("--question", default="文本切分为什么要设置重叠？", help="本次检索的问题。")
    parser.add_argument("--k", type=int, default=3, help="返回的文本块数量，须为正整数。")
    parser.add_argument("--corpus", choices=CORPUS_DIRS, default="baseline", help="baseline为原三篇，full为固定版本21篇。")
    args = parser.parse_args()
    if args.k <= 0:
        parser.error("--k 必须为正整数。")

    print("[1/3] 复用加载与切分，准备带编号和来源的文本块。", flush=True)
    # 先选择资料，后续切分、向量计算和检索复用原流程。
    docs = load_documents(CORPUS_DIRS[args.corpus])
    chunks = prepare_chunks(docs)
    print(f"资料选择：{args.corpus}", flush=True)
    print(f"完整文档数：{len(docs)}，文本块数：{len(chunks)}", flush=True)

    print("[2/3] 读取缓存的 CPU 嵌入模型，计算块向量并建立内存索引。", flush=True)
    vectorstore = build_vectorstore(chunks)

    print(f"[3/3] 按问题检索：{args.question}", flush=True)
    # 库会用同一模型编码问题，比较向量后返回完整文档记录及其 metadata。
    retrieved_docs = vectorstore.similarity_search(args.question, k=args.k)
    print(f"\n检索返回 {len(retrieved_docs)} 个块：")
    for rank, doc in enumerate(retrieved_docs, start=1):
        print(f"\n--- 排名 {rank}，原文块 {doc.metadata['chunk_id']} ---")
        print("来源：", Path(doc.metadata["source"]).name)
        print("完整正文字符数：", len(doc.page_content))
        print("前 300 字符预览：", doc.page_content[:300])
    print("\n当前输出是检索原文，尚未调用生成模型；相关性及答案依据需要核对。")


if __name__ == "__main__":
    main()
