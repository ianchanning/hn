"""Tests for corpus integrity and ranker output contract."""

import copy
import json
import math
from pathlib import Path
import sys

import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ranker

CORPUS_PATH = Path(__file__).resolve().parents[1] / "data" / "corpus_v2.json"


class TestEpistemicRanker(unittest.TestCase):
    """Contract and epistemic sanity suite (compatible with unittest and pytest)."""

    def test_rank_comments_contract_and_invariants(self) -> None:
        """Verify rank_comments preserves IDs, enforces invariants, and beats naive ordering."""
        corpus = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
        ranked = ranker.rank_comments(copy.deepcopy(corpus))

        self.assertEqual(len(ranked), 3010)
        self.assertEqual([c["signal_rank"] for c in ranked], list(range(1, 3011)))
        self.assertEqual({c["id"] for c in ranked}, {c["id"] for c in corpus})

        prev = float("inf")
        for c in ranked:
            self.assertTrue(math.isfinite(c["signal_score"]))
            self.assertLess(c["signal_score"], prev)
            prev = c["signal_score"]
            self.assertIn(
                c["tier"],
                {
                    "epistemic_gold",
                    "grounded_analysis",
                    "crowd_chatter",
                    "meme_or_snark",
                    "bullshit_or_flamewar",
                    "downvoted_sink",
                },
            )
            self.assertIn("components", c)

        self.assertTrue(all(c["downvote_tier"] < 2 for c in ranked[:35]))
        self.assertTrue(all(not c["is_mod_rebuked"] for c in ranked[:60]))
        self.assertTrue(
            all(
                c["own_word_count"] >= 2 and (c["own_word_count"] + c["quoted_word_count"]) >= 8
                for c in ranked[:50]
            )
        )
        self.assertTrue(all(c["max_older_dup_cos"] < 0.85 for c in ranked[:40]))

    def test_epistemic_adversarial_sanity_on_dev_pairs(self) -> None:
        """Verify key dev-only epistemic separations (no holdout IDs referenced)."""
        corpus = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
        ranked = ranker.rank_comments(copy.deepcopy(corpus))
        pos = {c["id"]: c["signal_rank"] for c in ranked}

        self.assertLess(pos[50472726], pos[50477258])
        self.assertLess(pos[50476287], pos[50477314])
        self.assertLess(pos[50477795], pos[50467793])


if __name__ == "__main__":
    unittest.main()
