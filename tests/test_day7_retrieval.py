"""Kiểm tra retrieval Day 7: BM25, RRF, context packing, định nghĩa hit."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from retrieval.bm25 import BM25Index
from retrieval.context import pack_context
from retrieval.evaluate import is_hit
from retrieval.hybrid import rrf_fuse


def chunk(chunk_id, text, book=1, page=1, source_id="doc"):
    return {
        "id": chunk_id,
        "text": text,
        "source_id": source_id,
        "source": "example://doc",
        "page": page,
        "metadata": {"book": book, "section": f"BOOK {book}"},
    }


class BM25Tests(unittest.TestCase):
    def setUp(self):
        self.chunks = [
            chunk("a", "Justice is speaking the truth and paying debts.", book=1, page=1),
            chunk("b", "The guardians receive no private property.", book=2, page=2),
            chunk("c", "Harmony of the soul is produced by music and gymnastic.", book=3, page=3),
        ]
        self.index = BM25Index(self.chunks)

    def test_ranks_matching_unit_first(self):
        hits = self.index.search("what is justice", top_k=2)
        self.assertEqual([hit["id"] for hit in hits], ["a"])
        self.assertEqual(hits[0]["rank"], 1)

    def test_two_term_query_orders_by_score(self):
        hits = self.index.search("guardians property", top_k=2)
        self.assertEqual(hits[0]["id"], "b")
        self.assertEqual([hit["rank"] for hit in hits], [1])

    def test_filter_restricts_candidates(self):
        hits = self.index.search("justice", top_k=3, filters={"book": 3})
        self.assertTrue(all(hit["metadata"]["book"] == 3 for hit in hits))

    def test_unknown_term_returns_empty(self):
        self.assertEqual(self.index.search("zeppelin", top_k=3), [])

    def test_stopwords_only_query_returns_empty(self):
        self.assertEqual(self.index.search("the of and", top_k=3), [])


class FusionTests(unittest.TestCase):
    def test_rrf_prefers_document_ranked_by_both(self):
        dense = [{"id": "a", "score": 0.9}, {"id": "b", "score": 0.8}]
        lexical = [{"id": "b", "score": 12.0}, {"id": "a", "score": 3.0}]
        fused = rrf_fuse([dense, lexical], k=60, top_k=2)
        self.assertEqual({hit["id"] for hit in fused}, {"a", "b"})
        # a: dense rank 1 (1/61) + lexical rank 2 (1/62)
        self.assertAlmostEqual(fused[0]["score"], 1 / 61 + 1 / 62, places=6)
        self.assertEqual(fused[0]["id"], "a")

    def test_rrf_deduplicates(self):
        fused = rrf_fuse([[{"id": "a"}], [{"id": "a"}]], k=60, top_k=5)
        self.assertEqual(len(fused), 1)


class ContextTests(unittest.TestCase):
    def test_budget_and_dedup(self):
        hits = [chunk("a", "x" * 100), chunk("a", "x" * 100), chunk("b", "y" * 100)]
        context, ids = pack_context(hits, budget=400)
        self.assertEqual(ids, ["a", "b"])
        self.assertLessEqual(len(context), 400)
        self.assertIn("[a", context)

    def test_too_small_budget_drops_block(self):
        context, ids = pack_context([chunk("a", "x" * 500)], budget=100)
        self.assertEqual(ids, [])
        self.assertEqual(context, "")


class ErrorHandlingTests(unittest.TestCase):
    def test_bm25_rejects_invalid_arguments(self):
        index = BM25Index([chunk("a", "justice is paying debts")])
        with self.assertRaises(ValueError):
            index.search("justice", top_k=0)
        with self.assertRaises(ValueError):
            BM25Index([], )
        with self.assertRaises(ValueError):
            BM25Index([chunk("a", "x")], k1=0)
        with self.assertRaises(ValueError):
            BM25Index([chunk("a", "x")], b=1.5)

    def test_pack_context_rejects_invalid_budget(self):
        with self.assertRaises(ValueError):
            pack_context([chunk("a", "x")], budget=0)
        with self.assertRaises(ValueError):
            pack_context([chunk("a", "x")], budget=100, block_cap=0)

    def test_filter_validation_rejects_unknown_keys(self):
        from retrieval.dense import validate_filters

        self.assertIsNone(validate_filters(None))
        self.assertIsNone(validate_filters({}))
        self.assertEqual(validate_filters({"book": 2}), {"book": 2})
        self.assertIsNone(validate_filters({"book": None}))
        with self.assertRaises(ValueError):
            validate_filters({"page": 3})


class HitTests(unittest.TestCase):
    def test_hit_requires_source_page_and_evidence(self):
        gold = [{"source_id": "doc", "page": 2, "evidence": "private property"}]
        good = chunk("b", "The guardians receive no private property.", page=2)
        wrong_page = chunk("b", "The guardians receive no private property.", page=3)
        self.assertTrue(is_hit(good, gold))
        self.assertFalse(is_hit(wrong_page, gold))

    def test_alternative_gold_list(self):
        gold = [
            {"source_id": "doc", "page": 9, "evidence": "missing"},
            {"source_id": "doc", "page": 1, "evidence": "Justice"},
        ]
        self.assertTrue(is_hit(chunk("a", "Justice is ...", page=1), gold))


if __name__ == "__main__":
    unittest.main()
