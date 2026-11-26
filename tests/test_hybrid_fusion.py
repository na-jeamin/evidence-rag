"""测试 hybrid_retrieve.py 的候选去重、RRF 累计、排序与截断逻辑。"""

from pathlib import Path
import sys
import unittest

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from base import BaseCase  # noqa: E402
from hybrid_retrieve import (  # noqa: E402
    calculate_rrf_scores,
    merge_candidates,
    rank_candidates,
)


class TestHybridFusion(BaseCase):
    def test_merge_candidates_deduplicates_by_chunk_id(self) -> None:
        chunks = self.make_sample_chunks()
        dense_docs = [chunks[0], chunks[1]]
        bm25_docs = [chunks[1], chunks[2]]

        merged = merge_candidates(dense_docs, bm25_docs)
        self.assertEqual([doc.metadata["chunk_id"] for doc in merged], ["C001", "C002", "C003"])

    def test_shared_candidate_accumulates_rrf_score_and_ranks_first(self) -> None:
        chunks = self.make_sample_chunks()
        dense_docs = [chunks[0], chunks[2]]  # C001 rank 1, C003 rank 2
        bm25_docs = [chunks[3], chunks[2]]   # C004 rank 1, C003 rank 2

        merged = merge_candidates(dense_docs, bm25_docs)
        scores = calculate_rrf_scores(dense_docs, bm25_docs, rank_constant=60)
        ranked = rank_candidates(merged, scores)

        self.assertAlmostEqual(scores["C003"], 1 / 62 + 1 / 62)
        self.assertAlmostEqual(scores["C001"], 1 / 61)
        self.assertEqual(ranked[0].metadata["chunk_id"], "C003")

    def test_ranked_results_truncate_to_k_with_dense_first_tie_break(self) -> None:
        chunks = self.make_sample_chunks()
        dense_docs = [chunks[0], chunks[1]]  # C001 rank 1, C002 rank 2
        bm25_docs = [chunks[2], chunks[3]]   # C003 rank 1, C004 rank 2

        merged = merge_candidates(dense_docs, bm25_docs)
        scores = calculate_rrf_scores(dense_docs, bm25_docs, rank_constant=60)
        ranked = rank_candidates(merged, scores)

        # C001 与 C003 同分 1/61，稳定排序保留 Dense 优先顺序；最终截断到 k=2。
        self.assertEqual([doc.metadata["chunk_id"] for doc in ranked[:2]], ["C001", "C003"])

    def test_empty_route_preserves_other_route_order(self) -> None:
        chunks = self.make_sample_chunks()
        bm25_docs = [chunks[3], chunks[1], chunks[0]]

        merged = merge_candidates([], bm25_docs)
        scores = calculate_rrf_scores([], bm25_docs, rank_constant=60)
        ranked = rank_candidates(merged, scores)

        self.assertEqual([doc.metadata["chunk_id"] for doc in ranked], ["C004", "C002", "C001"])


if __name__ == "__main__":
    unittest.main()
