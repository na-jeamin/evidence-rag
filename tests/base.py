"""离线单元测试公共基类与固定样例数据。"""

from pathlib import Path
import sys
import unittest

from langchain_core.documents import Document


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


class BaseCase(unittest.TestCase):
    """提供固定文档与带编号文本块样例；不读取 .env，不发起网络请求。"""

    def make_sample_documents(self) -> list[Document]:
        long_text = "".join(f"第{i:03d}句用于验证文本切分与重叠。" for i in range(1, 55))
        return [
            Document(
                page_content="数据加载器读取文档正文，并保留来源文件名和页码等元数据。",
                metadata={"source": "data/documents/04_data_load.md"},
            ),
            Document(
                page_content=long_text,
                metadata={"source": "data/documents/05_text_chunking.md"},
            ),
            Document(
                page_content="检索模块利用同样的嵌入模型将问题向量化，并与欧氏距离等度量配合使用。",
                metadata={"source": "data/documents/06_vector_embedding.md"},
            ),
        ]

    def make_sample_chunks(self) -> list[Document]:
        return [
            Document(
                page_content="文档加载器除了提取正文，还会抽取来源路径和页码作为元数据。",
                metadata={"chunk_id": "C001", "source": "04_data_load.md"},
            ),
            Document(
                page_content="文本切分通过 chunk_overlap 保持相邻块之间的上下文连续性。",
                metadata={"chunk_id": "C002", "source": "05_text_chunking.md"},
            ),
            Document(
                page_content="Embedding 模型将用户的问题也转换为一个向量，保证同空间匹配。",
                metadata={"chunk_id": "C003", "source": "06_vector_embedding.md"},
            ),
            Document(
                page_content="BM25 依据词频与逆文档频率计算关键词匹配分数。",
                metadata={"chunk_id": "C004", "source": "11_hybrid_search.md"},
            ),
        ]
