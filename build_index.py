"""读取所选资料，构建向量库并保存到本地文件。

复用已有加载、切分和CPU嵌入流程，默认使用正式21篇资料。
"""

import argparse
from pathlib import Path
from tempfile import NamedTemporaryFile

from langchain_core.vectorstores import InMemoryVectorStore

from inspect_chunks import prepare_chunks
from inspect_documents import CORPUS_DIRS, load_documents
from retrieve import build_vectorstore


INDEX_DIR = Path(__file__).resolve().parent / "artifacts" / "indexes"


def save_vectorstore(vectorstore: InMemoryVectorStore, index_path: Path) -> None:
    """完整写好临时文件后替换目标，避免中途失败损坏已有索引。"""
    index_path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        dir=index_path.parent, prefix=f".{index_path.name}.", suffix=".tmp", delete=False
    ) as temporary:
        temporary_path = Path(temporary.name)
    try:
        vectorstore.dump(str(temporary_path))
        temporary_path.replace(index_path)
    finally:
        temporary_path.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="构建并保存文档向量索引。")
    parser.add_argument("--corpus", choices=CORPUS_DIRS, default="full", help="full为正式21篇，baseline为原三篇。")
    parser.add_argument("--output", type=Path, help="索引文件路径，默认artifacts/indexes/<corpus>.json。")
    args = parser.parse_args()
    index_path = (args.output or INDEX_DIR / f"{args.corpus}.json").resolve()

    print("[1/3] 加载资料并切分。", flush=True)
    docs = load_documents(CORPUS_DIRS[args.corpus])
    chunks = prepare_chunks(docs)
    if not chunks:
        raise ValueError("切分结果为空，无法构建索引。")
    print(f"资料选择：{args.corpus}，文档数：{len(docs)}，文本块数：{len(chunks)}", flush=True)

    print("[2/3] 用缓存的CPU嵌入模型计算块向量，建立内存向量库。", flush=True)
    vectorstore = build_vectorstore(chunks)

    print("[3/3] 保存向量、正文和metadata。", flush=True)
    save_vectorstore(vectorstore, index_path)
    print("索引记录数：", len(vectorstore.store))
    print("索引已保存：", index_path)


if __name__ == "__main__":
    main()
