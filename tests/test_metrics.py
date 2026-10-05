import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from backend.metrics import measured_call
from backend.conversation import ConversationState
from backend.rag_utils import RAGSystem


class MetricsTests(unittest.TestCase):
    def test_usage_and_response_preserved_without_prompt_logging(self):
        metrics = {}
        response = SimpleNamespace(usage=SimpleNamespace(prompt_tokens=12, completion_tokens=3, total_tokens=15))
        operation = Mock(return_value=response)
        with patch("backend.metrics.perf_counter", side_effect=[1., 1.25]):
            result = measured_call(metrics, "select", "chat", operation, model="test", messages=["PRIVATE"])
        self.assertIs(result, response)
        self.assertEqual(metrics["reported_total_tokens"], 15)
        self.assertEqual(metrics["calls"][0]["elapsed_ms"], 250)
        self.assertNotIn("PRIVATE", str(metrics))
        operation.assert_called_once_with(model="test", messages=["PRIVATE"])

    def test_missing_usage_is_explicit(self):
        metrics = {}
        measured_call(metrics, "select", "chat", lambda **kw: SimpleNamespace(), model="test")
        self.assertIsNone(metrics["calls"][0]["total_tokens"])
        self.assertEqual(metrics["usage_missing_calls"], 1)

    def test_failure_is_counted_and_reraised_without_error_text(self):
        metrics = {}
        operation = Mock(side_effect=RuntimeError("PRIVATE ERROR"))
        with self.assertRaises(RuntimeError):
            measured_call(metrics, "select", "chat", operation, model="test")
        self.assertEqual(metrics["failed_calls"], 1)
        self.assertNotIn("PRIVATE", str(metrics))

    def test_turn_metrics_reset_and_stay_session_local(self):
        rag = RAGSystem.__new__(RAGSystem)
        rag.state = ConversationState(last_metrics={"old": True})
        rag._ask = Mock(return_value="answer")
        other = rag.for_conversation(ConversationState())
        with patch.dict("os.environ", {"RAG_LOG_METRICS": "0"}):
            self.assertEqual(rag.ask("question"), "answer")
        self.assertNotIn("old", rag.state.last_metrics)
        self.assertTrue(rag.state.last_metrics["turn_success"])
        self.assertEqual(other.state.last_metrics, {})

    def test_turn_failure_records_timing(self):
        rag = RAGSystem.__new__(RAGSystem)
        rag.state = ConversationState()
        rag._ask = Mock(side_effect=RuntimeError("error"))
        with patch.dict("os.environ", {"RAG_LOG_METRICS": "0"}), self.assertRaises(RuntimeError):
            rag.ask("question")
        self.assertFalse(rag.state.last_metrics["turn_success"])
        self.assertGreaterEqual(rag.state.last_metrics["turn_elapsed_ms"], 0)

    def test_details_bounded_but_totals_include_all_calls(self):
        metrics = {}
        for i in range(65):
            measured_call(metrics, "test", "chat", lambda: None)
        self.assertEqual(len(metrics["calls"]), 64)
        self.assertEqual(metrics["model_calls"], 65)
        self.assertEqual(metrics["omitted_call_details"], 1)


if __name__ == "__main__":
    unittest.main()
