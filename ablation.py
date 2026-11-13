"""Controlled scientific ablation study across the epistemic ranking components."""

import copy
import json
from pathlib import Path
import sys
from typing import Any

HERE = Path(__file__).resolve().parent
JUDGE_DIR = HERE / "judge"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(JUDGE_DIR))

from judge_v1 import score_ordering
import ranker


def run_ablations() -> list[dict[str, Any]]:
    """Evaluate Live HN, naive baselines, and leave-one-pillar-out ablations."""
    corpus = json.loads((HERE / "data" / "corpus_v2.json").read_text(encoding="utf-8"))
    fixtures = json.loads((JUDGE_DIR / "epistemic_fixtures_v1.json").read_text(encoding="utf-8"))

    results: list[dict[str, Any]] = []

    # 1. Live Hacker News DOM Rank
    hn_ord = sorted(corpus, key=lambda c: c.get("live_dom_rank") or 99999)
    results.append({"name": "0. Live Hacker News (Production Page Order)", **score_ordering(hn_ord, fixtures)})

    # 2. Pure Word-Count Heuristic (Next-Token Verbosity Bias)
    wc_ord = sorted(corpus, key=lambda c: (c.get("own_word_count", 0), -(c.get("live_dom_rank") or 9999)), reverse=True)
    results.append({"name": "1. Naive Word-Count Only (Verbosity Bias)", **score_ordering(wc_ord, fixtures)})

    # 3. Pure Author Karma Halo
    karma_ord = sorted(corpus, key=lambda c: (c.get("author_karma", 0), c.get("own_word_count", 0)), reverse=True)
    results.append({"name": "2. Author Total Karma Only (Authority Halo)", **score_ordering(karma_ord, fixtures)})

    # 4. Information Gain Only (No Falsifiability, No Bullshit Filter, No MMR)
    zero_w = {k: 0.0 for k in ranker.DEFAULT_WEIGHTS}
    ig_ord = ranker.rank_comments(copy.deepcopy(corpus), weights={**zero_w, "info_gain": 2.35, "downvote_penalty": 3.10})
    results.append({"name": "3. Shannon/IDF Info Gain + Downvote Gate", **score_ordering(ig_ord, fixtures)})

    # 5. Add Popperian Falsifiability (still no Frankfurtian Bullshit Filter)
    pop_ord = ranker.rank_comments(
        copy.deepcopy(corpus),
        weights={**zero_w, "info_gain": 2.35, "falsifiability": 2.85, "downvote_penalty": 3.10},
    )
    results.append({"name": "4. + Popperian Falsifiability (No BS Filter)", **score_ordering(pop_ord, fixtures)})

    # 6. Add Frankfurtian Bullshit Suppression (no Gravity/Author Precision, no MMR)
    bs_ord = ranker.rank_comments(
        copy.deepcopy(corpus),
        weights={
            **zero_w,
            "info_gain": 2.35,
            "falsifiability": 2.85,
            "bullshit_penalty": 2.65,
            "downvote_penalty": 3.10,
        },
    )
    results.append({"name": "5. + Frankfurtian Bullshit Suppression", **score_ordering(bs_ord, fixtures)})

    # 7. Add Inverse news.arc Physics + Progeny + Bayesian Author Precision (no MMR)
    grav_ord = ranker.rank_comments(
        copy.deepcopy(corpus),
        weights={
            **ranker.DEFAULT_WEIGHTS,
            "mmr_sim_lambda": 0.0,
            "mmr_root_lambda": 0.0,
            "mmr_facet_lambda": 0.0,
        },
    )
    results.append({"name": "6. + Inverse news.arc & Bayesian Precision (No MMR)", **score_ordering(grav_ord, fixtures)})

    # 8. Full Epistemic Signal Engine (with Submodular MMR Portfolio)
    full_ord = ranker.rank_comments(copy.deepcopy(corpus))
    results.append({"name": "7. Full Epistemic Signal Engine (Current Best)", **score_ordering(full_ord, fixtures)})

    out_path = HERE / "data" / "ablation_results.json"
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    return results


if __name__ == "__main__":
    rows = run_ablations()
    for r in rows:
        print(
            f"{r['name']:52s} | score={r['score']:6.2f} | ndcg20={r['ndcg20']:.3f} "
            f"| adv={r['adversarial_acc']:.3f} | rescue={r['buried_gold_recall_top45']:.3f} "
            f"| div={r['top20_diversity']:.3f}"
        )
