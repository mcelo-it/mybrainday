import os
import unittest
from unittest.mock import patch

os.environ.setdefault("OPENAI_API_KEY", "test-placeholder-not-a-real-key")

from fastapi.testclient import TestClient
from backend import app as api
from backend.conversation import ConversationState
from backend.rag_utils import RAGSystem
from backend.sessions import SessionStore


def retrieve(rag, query, top_k=None):
    chunks = [{"text": query, "score": 0.9, "module_number": "01",
               "module_name": query, "video_number": "1", "video_name": query,
               "time_range": "(0:00:00 - 0:00:30)", "filename": query + ".txt"}]
    rag.state.last_retrieved_chunks = chunks
    return chunks


class ChatSessionTests(unittest.TestCase):
    def setUp(self):
        self.patches = [
            patch.object(api, "sessions", SessionStore()),
            patch.object(api, "initialize_rag"),
            patch.object(RAGSystem, "retrieve", retrieve),
            patch.object(RAGSystem, "is_smalltalk", return_value=False),
            patch.object(RAGSystem, "detect_turn_type", lambda rag, query:
                         "FOLLOW_UP" if query == "Warum?" and rag.state.last_selected_chunks else "NEW"),
            patch.object(RAGSystem, "classify_request_with_context", lambda rag, query, context:
                         "DOMAIN_GENERIC" if query == "Schutz" else "DOMAIN_SPECIFIC"),
            patch.object(RAGSystem, "select_relevant_quotes", return_value=[1]),
            patch.object(RAGSystem, "summarize_topic", lambda rag, query, chunks: query),
            patch.object(RAGSystem, "build_clarification_options", return_value=[
                {"label": "Schutzkonzept", "source_numbers": [1]}]),
            patch.object(RAGSystem, "resolve_clarification_option", return_value=0),
        ]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)
        self.client = self.enterContext(TestClient(api.app, raise_server_exceptions=False))

    def chat(self, message, token=None):
        return self.client.post("/chat", json={"message": message},
                                headers={"X-Conversation-ID": token} if token else {})

    def test_interleaved_followups_and_sources(self):
        a = self.chat("NA-Schutz").json()
        b = self.chat("Stromwandler").json()
        self.assertNotEqual(a["conversation_id"], b["conversation_id"])
        for first, topic, other in [(a, "NA-Schutz", "Stromwandler"), (b, "Stromwandler", "NA-Schutz")]:
            reply = self.chat("Warum?", first["conversation_id"])
            self.assertEqual(reply.status_code, 200)
            self.assertIn(topic, reply.json()["answer"])
            self.assertNotIn(other, reply.json()["answer"])
            sources = self.client.get("/sources", headers={"X-Conversation-ID": first["conversation_id"]}).json()
            self.assertEqual(sources[0]["text_preview"], topic)
        self.assertEqual(self.client.get("/sources").json(), [])
        self.assertIsNone(api.rag.state.last_user_query)

    def test_pending_clarification_belongs_to_only_one_session(self):
        a = self.chat("Schutz").json()
        b = self.chat("Transformator").json()
        self.assertIn("Transformator", b["answer"])
        answer = self.chat("1", a["conversation_id"]).json()["answer"]
        self.assertIn("Schutzkonzept", answer)
        self.assertNotIn("Transformator", answer)

    def test_missing_invalid_expired_and_empty_requests(self):
        self.assertEqual(self.chat(" ").status_code, 400)
        self.assertEqual(self.chat("x" * 8001).status_code, 422)
        self.assertEqual(self.chat("Hallo", "unknown").status_code, 404)
        self.assertEqual(self.client.get("/sources", headers={"X-Conversation-ID": "unknown"}).status_code, 404)
        self.assertEqual(self.chat("Hallo", "x" * 129).status_code, 422)
        clock = [0]
        api.sessions = SessionStore(ttl_seconds=10, clock=lambda: clock[0])
        token = self.chat("NA-Schutz").json()["conversation_id"]
        clock[0] = 11
        self.assertEqual(self.chat("Warum?", token).status_code, 404)
        self.assertEqual(self.chat("Neuer Chat").status_code, 200)

    def test_provider_failure_does_not_commit_partial_turn(self):
        token = self.chat("NA-Schutz").json()["conversation_id"]
        with patch.object(RAGSystem, "summarize_topic", side_effect=RuntimeError("provider failed")):
            self.assertEqual(self.chat("Stromwandler", token).status_code, 500)
        reply = self.chat("Warum?", token).json()
        self.assertIn("NA-Schutz", reply["answer"])
        self.assertNotIn("Stromwandler", reply["answer"])

    def test_index_shared_dialogue_separate(self):
        a, b = api.rag.for_conversation(ConversationState()), api.rag.for_conversation(ConversationState())
        self.assertIs(a.embeddings, b.embeddings)
        self.assertIs(a.chunks, b.chunks)
        self.assertIs(a.client, b.client)
        a.state.chat_history.append({"role": "user", "content": "A"})
        self.assertEqual(b.state.chat_history, [])

    def test_rebuild_publishes_only_complete_snapshot(self):
        old_index = api.rag
        self.addCleanup(setattr, api, "rag", old_index)
        old_worker = old_index.for_conversation(ConversationState())

        def load_documents(replacement):
            replacement.documents = [{"filename": "new.txt"}]

        with patch.dict(os.environ, {"REBUILD_TOKEN": "test-rebuild"}), \
                patch.object(RAGSystem, "load_documents", load_documents), \
                patch.object(RAGSystem, "build_chunks"), \
                patch.object(RAGSystem, "create_embeddings"), \
                patch.object(RAGSystem, "save_cache", side_effect=RuntimeError("disk failure")):
            failed = self.client.post("/rebuild", headers={"X-Rebuild-Token": "test-rebuild"})
            self.assertEqual(failed.status_code, 500)
            self.assertIs(api.rag, old_index)
            with patch.object(RAGSystem, "save_cache"):
                success = self.client.post("/rebuild", headers={"X-Rebuild-Token": "test-rebuild"})
                self.assertEqual(success.status_code, 200)
        self.assertIsNot(api.rag, old_index)
        self.assertEqual(api.rag.documents, [{"filename": "new.txt"}])
        self.assertIs(old_worker.documents, old_index.documents)
        self.assertIsNot(old_worker.documents, api.rag.documents)


if __name__ == "__main__":
    unittest.main()
