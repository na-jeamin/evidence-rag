"""测试 eval_retrieval.py 的 Hit@K、MRR@K 与必需依据组覆盖计算。"""

from pathlib import Path
import sys
import unittest

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from base import BaseCase  # noqa: E402
from eval_retrieval import (  # noqa: E402
    first_labeled_evidence_rank,
    has_all_evidence_groups,
    has_labeled_evidence,
)


class TestMetrics(BaseCase):
    def test_hand_computed_hit_and_mrr_across_three_cases(self) -> None:
        chunks = self.make_sample_chunks()
        # 返回顺序固定为 [C001, C002, C003]
        retrieved = chunks[:3]
        cases = [
            {"evidence_options": [{"source": "04_data_load.md", "quote": "抽取来源路径和页码"}]},
            {"evidence_options": [{"source": "05_text_chunking.md", "quote": "上下文连续性"}]},
            {"evidence_options": [{"source": "06_vector_embedding.md", "quote": "不存在的原句"}]},
        ]

        ranks = [first_labeled_evidence_rank(case, retrieved) for case in cases]
        self.assertEqual(ranks, [1, 2, None])

        hits = [has_labeled_evidence(case, retrieved) for case in cases]
        self.assertEqual(hits, [True, True, False])

        hit_rate = sum(hits) / len(cases)
        mrr = sum(0.0 if rank is None else 1.0 / rank for rank in ranks) / len(cases)
        self.assertAlmostEqual(hit_rate, 2 / 3)
        self.assertAlmostEqual(mrr, (1.0 + 0.5 + 0.0) / 3)

    def test_miss_contributes_zero_to_numerator_and_one_to_denominator(self) -> None:
        chunks = self.make_sample_chunks()
        retrieved = chunks[:3]
        cases = [
            {"evidence_options": [{"source": "04_data_load.md", "quote": "抽取来源路径和页码"}]},
            {"evidence_options": [{"source": "11_hybrid_search.md", "quote": "关键词匹配分数"}]},
        ]

        ranks = [first_labeled_evidence_rank(case, retrieved) for case in cases]
        self.assertEqual(ranks, [1, None])
        mrr = sum(0.0 if rank is None else 1.0 / rank for rank in ranks) / len(cases)
        self.assertAlmostEqual(mrr, 0.5)

    def test_evidence_groups_require_all_groups_to_match(self) -> None:
        chunks = self.make_sample_chunks()
        case = {
            "evidence_options": [
                {"source": "06_vector_embedding.md", "quote": "同空间匹配"},
                {"source": "11_hybrid_search.md", "quote": "关键词匹配分数"},
            ],
            "evidence_groups": [
                {"evidence_options": [{"source": "06_vector_embedding.md", "quote": "同空间匹配"}]},
                {"evidence_options": [{"source": "11_hybrid_search.md", "quote": "关键词匹配分数"}]},
            ],
        }

        # 只有第 1 组命中、第 2 组缺失时，组覆盖必须为 False。
        self.assertTrue(has_labeled_evidence(case, chunks[:3]))
        self.assertFalse(has_all_evidence_groups(case, chunks[:3]))
        # 两组均命中时为 True。
        self.assertTrue(has_all_evidence_groups(case, chunks))


if __name__ == "__main__":
    unittest.main()
