"""加载已保存的文档向量索引，计算新问题向量并返回原文块。"""

import argparse
from pathlib import Path

from langchain_core.vectorstores import InMemoryVectorStore

from build_index import INDEX_DIR
from retrieve import create_embeddings


def main() -> None:
    parser = argparse.ArgumentParser(description="加载已有索引并检索问题。")
    parser.add_argument("--index", type=Path, default=INDEX_DIR / "full.json", help="已保存的索引文件。")
    parser.add_argument("--question", default="在线提问时，问题应该用与资料相同的嵌入模型编码，还是可以随意换一个？")
    parser.add_argument("--k", type=int, default=3, help="返回的文本块数量，须为正整数。")
    args = parser.parse_args()
    if args.k <= 0:
        parser.error("--k 必须为正整数。")
    index_path = args.index.resolve()
    if not index_path.is_file():
        parser.error(f"找不到索引文件：{index_path}。请先用build_index.py构建，或检查--index路径。")

    print("[1/3] 准备与构建时相同的嵌入模型，用于编码新问题。", flush=True)
    embeddings = create_embeddings()

    print("[2/3] 从文件恢复文档向量、正文和metadata。", flush=True)
    try:
        vectorstore = InMemoryVectorStore.load(str(index_path), embedding=embeddings)
    except (OSError, ValueError, TypeError) as error:
        parser.error(f"索引加载失败：{error}。请检查文件或重新构建。")
    if not vectorstore.store:
        parser.error("索引没有文档记录，请检查文件或重新构建。")
    print("读取索引：", index_path)
    print("恢复的记录数：", len(vectorstore.store))

    print(f"[3/3] 计算问题向量并检索：{args.question}", flush=True)
    retrieved_docs = vectorstore.similarity_search(args.question, k=args.k)
    print(f"\n检索返回 {len(retrieved_docs)} 个块：")
    for rank, doc in enumerate(retrieved_docs, start=1):
        print(f"\n--- 排名 {rank}，原文块 {doc.metadata['chunk_id']} ---")
        print("来源：", Path(doc.metadata["source"]).name)
        print("完整正文字符数：", len(doc.page_content))
        print("前300字符预览：", doc.page_content[:300])


if __name__ == "__main__":
    main()
