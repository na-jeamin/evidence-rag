"""加载参考仓库的 Markdown 资料，观察文档列表。

沿用 all-in-rag C1 的加载步骤，扩展为多文件汇总；来源和差异见 SOURCES.md。
本入口不切分、不加载嵌入模型，也不请求生成模型。
"""

import argparse
from pathlib import Path

from langchain_community.document_loaders import TextLoader
from langchain_core.documents import Document


DATA_DIR = Path(__file__).resolve().parent / "data" / "documents"
FULL_DATA_DIR = Path(__file__).resolve().parent / "data" / "documents-full"
CORPUS_DIRS = {"baseline": DATA_DIR, "full": FULL_DATA_DIR}


def load_documents(data_dir: Path) -> list[Document]:
    """读取指定目录的 Markdown，返回汇总后的文档列表。"""
    file_paths = sorted(data_dir.glob("*.md"))
    if not file_paths:
        raise FileNotFoundError(f"资料目录没有 Markdown 文件：{data_dir}")

    docs = []
    for path in file_paths:
        loader = TextLoader(str(path), encoding="utf-8")
        loaded_docs = loader.load()
        # load 返回列表；extend 将其中的文档逐个加入总列表，避免嵌套列表。
        docs.extend(loaded_docs)
    return docs


def main() -> None:
    parser = argparse.ArgumentParser(description="加载原三篇或正式21篇资料，观察正文与来源。")
    parser.add_argument("--corpus", choices=CORPUS_DIRS, default="baseline", help="baseline为原三篇，full为固定版本21篇。")
    args = parser.parse_args()
    # 先选资料目录，后续仍复用同一个加载函数。
    data_dir = CORPUS_DIRS[args.corpus]
    docs = load_documents(data_dir)
    print(f"资料选择：{args.corpus}")
    print(f"资料目录：{data_dir}")
    print(f"加载的文档数：{len(docs)}")
    for number, doc in enumerate(docs, start=1):
        print(f"\n--- 文档 {number}：{Path(doc.metadata['source']).name} ---")
        print(f"正文字符数：{len(doc.page_content)}")
        print("前 100 字符预览：", doc.page_content[:100])
    print("\n当前只加载并汇总文档，尚未切分、建立索引或生成回答。")


if __name__ == "__main__":
    main()
