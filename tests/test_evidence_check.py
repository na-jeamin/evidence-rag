"""测试 check_evidence.validate_evidence_quotes 的逐字原句核对规则。"""

from pathlib import Path
import sys
import unittest

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from base import BaseCase  # noqa: E402
from check_evidence import (  # noqa: E402
    EvidenceCheckResult,
    EvidenceQuote,
    validate_evidence_quotes,
)


class TestEvidenceCheck(BaseCase):
    def test_exact_quote_in_matching_chunk_passes(self) -> None:
        docs = self.make_sample_chunks()[:2]
        result = EvidenceCheckResult(
            sufficient=True,
            reason="C002 明确说明重叠保持上下文连续性。",
            evidence=[
                EvidenceQuote(chunk_id="C002", quote="保持相邻块之间的上下文连续性")
            ],
        )
        validate_evidence_quotes(result, docs)

    def test_paraphrased_quote_raises_value_error(self) -> None:
        docs = self.make_sample_chunks()[:2]
        result = EvidenceCheckResult(
            sufficient=True,
            reason="尝试用改写句作为依据。",
            evidence=[
                EvidenceQuote(chunk_id="C002", quote="保持前后文本连贯")
            ],
        )
        with self.assertRaises(ValueError):
            validate_evidence_quotes(result, docs)

    def test_partial_valid_and_invalid_quotes_raise_value_error(self) -> None:
        docs = self.make_sample_chunks()[:2]
        result = EvidenceCheckResult(
            sufficient=False,
            reason="只找到部分原句，第二条摘录不在对应块中。",
            evidence=[
                EvidenceQuote(chunk_id="C001", quote="还会抽取来源路径和页码作为元数据"),
                EvidenceQuote(chunk_id="C002", quote="不在 C002 中的句子"),
            ],
        )
        with self.assertRaises(ValueError):
            validate_evidence_quotes(result, docs)


if __name__ == "__main__":
    unittest.main()
