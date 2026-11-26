"""测试 inspect_chunks.prepare_chunks 的切分、编号、来源保留与边界行为。"""

from pathlib import Path
import sys
import unittest

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from langchain_core.documents import Document  # noqa: E402

from base import BaseCase  # noqa: E402
from inspect_chunks import CHUNK_OVERLAP, CHUNK_SIZE, prepare_chunks  # noqa: E402


class TestChunking(BaseCase):
    def test_chunk_ids_are_consecutive_from_one_and_start_index_from_zero(self) -> None:
        docs = self.make_sample_documents()
        chunks = prepare_chunks(docs)

        self.assertGreater(len(chunks), len(docs))
        expected_ids = [f"C{i:03d}" for i in range(1, len(chunks) + 1)]
        actual_ids = [chunk.metadata["chunk_id"] for chunk in chunks]
        self.assertEqual(actual_ids, expected_ids)
        self.assertEqual(chunks[0].metadata["start_index"], 0)

    def test_source_metadata_is_preserved(self) -> None:
        docs = self.make_sample_documents()
        chunks = prepare_chunks(docs)
        expected_sources = {doc.metadata["source"] for doc in docs}

        for chunk in chunks:
            self.assertIn("source", chunk.metadata)
            self.assertIn(chunk.metadata["source"], expected_sources)

    def test_chunk_overlap_creates_shared_text_between_adjacent_chunks(self) -> None:
        long_doc = Document(
            page_content="".join(f"片段{i:03d}内容保持上下文连续。" for i in range(1, 60)),
            metadata={"source": "05_text_chunking.md"},
        )
        chunks = prepare_chunks([long_doc])

        self.assertGreaterEqual(len(chunks), 2)
        first, second = chunks[0], chunks[1]
        self.assertLessEqual(len(first.page_content), CHUNK_SIZE)
        self.assertGreater(CHUNK_OVERLAP, 0)
        # 相邻块存在起始索引回退与实际文本重叠。
        self.assertLess(
            second.metadata["start_index"],
            first.metadata["start_index"] + len(first.page_content),
        )
        overlap_len = first.metadata["start_index"] + len(first.page_content) - second.metadata["start_index"]
        self.assertGreater(overlap_len, 0)
        self.assertEqual(first.page_content[-overlap_len:], second.page_content[:overlap_len])

    def test_empty_document_returns_empty_without_error(self) -> None:
        empty_doc = Document(page_content="", metadata={"source": "empty.md"})
        self.assertEqual(prepare_chunks([empty_doc]), [])
        self.assertEqual(prepare_chunks([]), [])


if __name__ == "__main__":
    unittest.main()
