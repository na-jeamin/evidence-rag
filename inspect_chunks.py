"""第二阶段：将多份文档切块，保留来源、补编号并观察各文件块数。

复用已验证的加载函数；递归切分沿用 all-in-rag C1，详见 SOURCES.md。
本入口不建立向量索引，也不调用生成模型。
"""

from collections import Counter
from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from inspect_documents import DATA_DIR, load_documents


# 项目先用较短片段观察证据位置；这是实验起点，不代表最优配置。
CHUNK_SIZE = 500
CHUNK_OVERLAP = 100


def prepare_chunks(docs: list[Document]) -> list[Document]:
    """接收完整文档列表，返回保留来源并带本次配置内编号的文本块。"""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        add_start_index=True,
    )
    # 切分器会将原文档的 source 复制到各块 metadata。
    chunks = splitter.split_documents(docs)
    for number, chunk in enumerate(chunks, start=1):
        chunk.metadata["chunk_id"] = f"C{number:03d}"
    return chunks


def main() -> None:
    docs = load_documents(DATA_DIR)
    chunks = prepare_chunks(docs)
    print(f"配置：chunk_size={CHUNK_SIZE}，chunk_overlap={CHUNK_OVERLAP}")
    print(f"完整文档数：{len(docs)}，文本块总数：{len(chunks)}")

    # Counter 只负责统计展示，来源仍来自每块自己的 metadata。
    counts = Counter(Path(chunk.metadata["source"]).name for chunk in chunks)
    print("\n每份资料的文本块数：")
    for doc in docs:
        source_name = Path(doc.metadata["source"]).name
        print(f"  {source_name}：{counts[source_name]} 块")

    print("\n--- 前 3 块预览 ---")
    for chunk in chunks[:3]:
        print(f"\n{chunk.metadata['chunk_id']}，来源：{Path(chunk.metadata['source']).name}")
        print(f"字符数：{len(chunk.page_content)}")
        print(chunk.page_content[:100])
    print("\n当前完成切分与来源观察，尚未建立向量索引或生成回答。")


if __name__ == "__main__":
    main()
