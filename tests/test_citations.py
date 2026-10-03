import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from backend.citations import SUBJECT_AREAS, citation_from_chunk, load_subject_areas, subject_area
from backend.rag_utils import RAGSystem
import test_chat_sessions as chat_tests


class SubjectAreaTests(unittest.TestCase):
    def test_all_44_modules_and_boundaries(self):
        expected = [(1, 9, "1"), (10, 15, "2"), (16, 21, "3"),
                    (22, 29, "4"), (30, 36, "5"), (37, 44, "6")]
        self.assertEqual(set(SUBJECT_AREAS), set(range(1, 45)))
        for start, end, area in expected:
            for module in range(start, end + 1):
                self.assertEqual(subject_area(f"{module:02}")["subject_area_number"], area)
        self.assertEqual(subject_area("01"), subject_area(1))
        self.assertEqual(subject_area("x")["subject_area_name"], "Nicht zugeordnet")
        self.assertEqual(subject_area("45")["subject_area_number"], "")

    def test_duplicate_and_missing_assignments_fail(self):
        original = json.loads(Path("backend/subject_areas.json").read_text())
        with TemporaryDirectory() as temp:
            path = Path(temp) / "areas.json"
            original[1]["modules"].append(1)
            path.write_text(json.dumps(original))
            with self.assertRaises(ValueError):
                load_subject_areas(path)
            original[1]["modules"].pop()
            original[0]["modules"].remove(1)
            path.write_text(json.dumps(original))
            with self.assertRaises(ValueError):
                load_subject_areas(path)

    def test_quote_preserved_and_not_truncated(self):
        quote = 'Wörtlich: "Q(U)" & <Schutz>.\n  Zweite Zeile. ' + "Fachtext " * 60
        citation = citation_from_chunk({"module_number": "43", "text": quote})
        self.assertEqual(citation["text"], quote.strip())
        self.assertGreater(len(citation["text"]), 300)
        self.assertEqual(citation["subject_area_number"], "6")
        self.assertNotIn("score", citation)


class CitationAPITests(unittest.TestCase):
    setUp = chat_tests.ChatSessionTests.setUp
    chat = chat_tests.ChatSessionTests.chat

    def test_only_selected_sources_and_exact_answer_quote(self):
        def two_candidates(rag, query, top_k=None):
            first = chat_tests.retrieve(rag, query)[0]
            first["text"] = 'Wörtliches Zitat: "NA-Schutz".\n' + "Quelle " * 70
            second = dict(first, text="Nicht zitierter Kandidat", module_number="22")
            rag.state.last_retrieved_chunks = [first, second]
            return [first, second]

        with patch.object(RAGSystem, "retrieve", two_candidates):
            response = self.chat("Schutzfunktion").json()
        citations = response["citations"]
        self.assertEqual(len(citations), 1)
        self.assertEqual(response["sources"], citations)
        self.assertEqual(citations[0]["subject_area_name"], "Komponenten der Photovoltaik")
        self.assertIn(citations[0]["text"], response["answer"])
        self.assertIn("Fachbereich 1", response["answer"])
        self.assertNotIn("Nicht zitierter Kandidat", response["answer"])
        self.assertNotIn("score", citations[0])
        actual = self.client.get("/sources", headers={"X-Conversation-ID": response["conversation_id"]}).json()
        self.assertEqual(actual, citations)

    def test_smalltalk_clears_citations_but_preserves_followup_context(self):
        token = self.chat("Stromwandler").json()["conversation_id"]
        with patch.object(RAGSystem, "is_smalltalk", return_value=True):
            response = self.chat("Danke", token).json()
        self.assertEqual(response["citations"], [])
        self.assertEqual(self.client.get("/sources", headers={"X-Conversation-ID": token}).json(), [])
        self.assertIn("Stromwandler", self.chat("Warum?", token).json()["citations"][0]["text"])

    def test_declined_question_and_pending_clarification_have_no_citations(self):
        token = self.chat("Stromwandler").json()["conversation_id"]
        with patch.object(RAGSystem, "classify_request_with_context", return_value="NON_DOMAIN"):
            self.assertEqual(self.chat("Kuchen", token).json()["citations"], [])
        self.assertEqual(self.chat("Schutz", token).json()["citations"], [])
        with patch.object(RAGSystem, "resolve_clarification_option", return_value=None):
            self.assertEqual(self.chat("unklar", token).json()["citations"], [])
        self.assertEqual(len(self.chat("1", token).json()["citations"]), 1)


if __name__ == "__main__":
    unittest.main()
