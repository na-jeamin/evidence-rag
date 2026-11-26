"""测试 api.py 的健康检查、参数校验、缺失索引启动失败与 /ask 不足分支。"""

from pathlib import Path
import sys
import unittest
from unittest.mock import patch

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from fastapi.testclient import TestClient  # noqa: E402

import api  # noqa: E402
from base import BaseCase  # noqa: E402


class FakeVectorStore:
    def __init__(self, docs) -> None:
        self._docs = docs
        self.store = {doc.metadata["chunk_id"]: doc for doc in docs}

    def get_by_ids(self, ids):
        return [self.store[cid] for cid in ids if cid in self.store]

    def similarity_search(self, question: str, k: int = 3):
        return self._docs[:k]


class TestApi(BaseCase):
    def test_health_returns_200_with_indexed_chunk_count(self) -> None:
        docs = self.make_sample_chunks()
        fake_store = FakeVectorStore(docs)
        with patch.object(api, "load_index", return_value=fake_store):
            with TestClient(api.app) as client:
                response = client.get("/health")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), {"status": "ok", "indexed_chunks": len(docs)})

    def test_retrieve_rejects_invalid_k_with_422(self) -> None:
        fake_store = FakeVectorStore(self.make_sample_chunks())
        with patch.object(api, "load_index", return_value=fake_store):
            with TestClient(api.app) as client:
                res_zero = client.post("/retrieve", json={"question": "测试问题", "k": 0})
                res_eleven = client.post("/retrieve", json={"question": "测试问题", "k": 11})
                self.assertEqual(res_zero.status_code, 422)
                self.assertEqual(res_eleven.status_code, 422)

    def test_missing_index_fails_at_startup(self) -> None:
        missing_path = Path(__file__).resolve().parent / "nonexistent_index_for_test.json"
        with patch.object(api, "INDEX_PATH", missing_path):
            with self.assertRaises(RuntimeError):
                with TestClient(api.app):
                    pass

    def test_ask_returns_null_answer_and_supplemented_true_when_insufficient(self) -> None:
        docs = self.make_sample_chunks()
        fake_store = FakeVectorStore(docs)
        fake_result = {
            "question": "演示电脑的CPU完整型号是什么？",
            "status": "insufficient",
            "answer": None,
            "checks": [{"used_ids": ["C001", "C002", "C003", "C004"], "result": {"sufficient": False, "reason": "资料未说明CPU型号", "evidence": []}}],
            "citation_ids": [],
            "supplemented": True,
            "check_calls": 2,
            "answer_calls": 0,
            "retrieved_docs": [doc.model_dump() for doc in docs],
        }
        with (
            patch.object(api, "load_index", return_value=fake_store),
            patch.object(api, "MODEL_ENV_FILE", Path(__file__)),
            patch("check_evidence.build_hybrid_candidates", return_value=docs),
            patch("check_evidence.run_checked_rag", return_value=fake_result),
        ):
            with TestClient(api.app) as client:
                response = client.post("/ask", json={"question": "演示电脑的CPU完整型号是什么？"})
                self.assertEqual(response.status_code, 200)
                body = response.json()
                self.assertEqual(body["status"], "insufficient")
                self.assertIsNone(body["answer"])
                self.assertTrue(body["supplemented"])
                self.assertEqual(body["check_calls"], 2)
                self.assertEqual(body["answer_calls"], 0)


if __name__ == "__main__":
    unittest.main()
