import unittest

from backend.context_windows import expand_context, relevance_score


def segment(index, filename="video-a.txt", text=None):
    return {"filename": filename, "chunk_index": index, "chunk_id": index,
            "module_number": "01", "module_name": "Stringdesign",
            "video_number": "2", "video_name": "Kenngrößen",
            "time_range": f"(0:00:{index * 10:02} - 0:00:{index * 10 + 9:02})",
            "text": text or f"Abschnitt {index}"}


class ContextWindowsTests(unittest.TestCase):
    def test_announcement_includes_following_result_without_other_video(self):
        chunks = [segment(i) for i in range(6)] + [segment(2, "video-b.txt")]
        chunks[1]["text"] = "Jetzt berechnen wir die Spannung bei XY."
        chunks[2]["text"] = "Im gezeigten Beispiel sind es 600 Volt."
        result = expand_context([dict(chunks[1], score=0.8)], chunks)
        self.assertEqual([c["chunk_index"] for c in result], [0, 1, 2, 3, 4])
        self.assertTrue(all(c["filename"] == "video-a.txt" for c in result))
        self.assertEqual(result[2]["text"], chunks[2]["text"])
        self.assertEqual(result[2]["time_range"], chunks[2]["time_range"])
        self.assertNotIn("score", result[2])
        self.assertEqual(relevance_score(result[2]), 0.8)
        self.assertNotIn("context_anchor_score", chunks[2])

    def test_overlap_deduplicated_and_chronological(self):
        chunks = [segment(i) for i in range(6)]
        anchors = [dict(chunks[3], score=0.7), dict(chunks[1], score=0.9)]
        result = expand_context(anchors, chunks)
        self.assertEqual([c["chunk_index"] for c in result], list(range(6)))
        self.assertEqual(relevance_score(result[3]), 0.9)

    def test_bounds_and_gaps_never_cross_transcripts(self):
        chunks = [segment(0), segment(2), segment(3, "video-b.txt")]
        result = expand_context([dict(chunks[0], score=0.8)], chunks)
        self.assertEqual([c["chunk_index"] for c in result], [0, 2])

    def test_budget_keeps_whole_text_and_reserves_anchor(self):
        chunks = [segment(i, text="x" * 10) for i in range(6)]
        result = expand_context([dict(chunks[2], score=0.8)], chunks, max_chars=20, max_chunks=2)
        self.assertEqual(len(result), 2)
        self.assertIn(2, [c["chunk_index"] for c in result])
        self.assertTrue(all(c["text"] == "x" * 10 for c in result))

    def test_missing_position_does_not_invent_neighbours(self):
        anchor = {"text": "Standalone", "score": 0.8}
        self.assertEqual(len(expand_context([anchor], [segment(1)])), 1)

    def test_later_direct_seed_survives_neighbour_budget(self):
        chunks = [segment(i) for i in range(10)]
        anchors = [dict(chunks[0], score=.9), dict(chunks[9], score=.7)]
        result = expand_context(anchors, chunks, max_chunks=3)
        self.assertIn(9, [c['chunk_index'] for c in result])
        self.assertEqual(len(result), 3)


if __name__ == "__main__":
    unittest.main()
