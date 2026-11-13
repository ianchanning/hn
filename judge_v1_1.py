#!/usr/bin/env python3
"""External Judge v1.1.0 for HN Epistemic Signal vs Bullshit Evaluation.

Fixes v1.0.0 stub invariant so pinpointed documentary excerpts (`own + quoted >= 8`)
are permitted in Top 50 while true bare link-drops & 1-word stubs (`own + quoted < 8`)
remain strictly barred.
"""

import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import time
from typing import Any

from judge_v1 import (
    CANONICAL_CORPUS_PATH,
    FIXTURES_PATH,
    resolve_ranker_path,
    score_ordering,
)

JUDGE_VERSION = "1.1.0"


def check_invariants_v1_1(ranked: list[dict[str, Any]], expected_ids: set[int]) -> list[str]:
    """Enforce hard Anti-Goodhart invariants (v1.1.0)."""
    errors: list[str] = []
    if len(ranked) != len(expected_ids):
        errors.append(f"Expected {len(expected_ids)} comments, got {len(ranked)}")
        return errors

    got_ids = [c.get("id") for c in ranked]
    if set(got_ids) != expected_ids:
        errors.append("Returned IDs do not match canonical corpus IDs")
        return errors

    ranks = [c.get("signal_rank") for c in ranked]
    if ranks != list(range(1, len(expected_ids) + 1)):
        errors.append("signal_rank must be contiguous 1..N in returned order")

    for c in ranked:
        sc = c.get("signal_score")
        if not isinstance(sc, (int, float)) or not math.isfinite(sc):
            errors.append(f"Non-finite signal_score on comment {c.get('id')}")
            break

    deep_faded_top35 = [c["id"] for c in ranked[:35] if int(c.get("downvote_tier", 0)) >= 2]
    if deep_faded_top35:
        errors.append(f"Deeply downvoted (c73..cDD) comments in Top 35: {deep_faded_top35[:5]}")

    mod_rebuked_top60 = [c["id"] for c in ranked[:60] if c.get("is_mod_rebuked")]
    if mod_rebuked_top60:
        errors.append(f"Moderator-rebuked comments in Top 60: {mod_rebuked_top60}")

    # True bare link-drops / 1-word stubs have own_word_count + quoted_word_count < 8
    stubs_top50 = [
        c["id"]
        for c in ranked[:50]
        if (int(c.get("own_word_count", 0)) + int(c.get("quoted_word_count", 0))) < 8
        or int(c.get("own_word_count", 0)) < 2
    ]
    if stubs_top50:
        errors.append(f"Bare stub comments in Top 50: {stubs_top50[:5]}")

    exact_dups_top40 = [
        c["id"] for c in ranked[:40] if float(c.get("max_older_dup_cos", 0.0)) >= 0.85
    ]
    if exact_dups_top40:
        errors.append(f"Near-exact copy-paste duplicates in Top 40: {exact_dups_top40}")

    return errors


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: judge_v1_1.py <candidate_dir>", file=sys.stderr)
        sys.exit(2)

    cand_dir = Path(sys.argv[1]).resolve()
    fixtures = json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))
    raw_bytes = CANONICAL_CORPUS_PATH.read_bytes()
    actual_sha = hashlib.sha256(raw_bytes).hexdigest()
    if actual_sha != fixtures["corpus_sha256"]:
        print(json.dumps({"valid": False, "score": 0.0, "error": "Canonical corpus SHA mismatch"}))
        sys.exit(1)

    canonical_corpus = json.loads(raw_bytes.decode("utf-8"))
    expected_ids = {c["id"] for c in canonical_corpus}

    hn_ordered = sorted(canonical_corpus, key=lambda c: c.get("live_dom_rank") or 99999)
    hn_metrics = score_ordering(hn_ordered, fixtures, split_filter=None)

    try:
        ranker_path = resolve_ranker_path(cand_dir)
        spec = importlib.util.spec_from_file_location("candidate_ranker", ranker_path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Unable to load {ranker_path}")
        mod = importlib.util.module_from_spec(spec)
        t0 = time.perf_counter()
        spec.loader.exec_module(mod)
        ranked = mod.rank_comments(copy.deepcopy(canonical_corpus))
        elapsed = time.perf_counter() - t0
    except Exception as exc:
        out = {
            "valid": False,
            "score": 0.0,
            "judge_version": JUDGE_VERSION,
            "error": f"{type(exc).__name__}: {exc}",
        }
        print(json.dumps(out))
        print(f"[JUDGE ERROR] {out['error']}", file=sys.stderr)
        sys.exit(0)

    inv_errors = check_invariants_v1_1(ranked, expected_ids)
    if elapsed > 4.0:
        inv_errors.append(f"Runtime {elapsed:.2f}s exceeded 4.0s deterministic budget")

    dev_m = score_ordering(ranked, fixtures, split_filter="dev")
    holdout_m = score_ordering(ranked, fixtures, split_filter="holdout")
    full_m = score_ordering(ranked, fixtures, split_filter=None)

    valid = len(inv_errors) == 0
    final_score = full_m["score"] if valid else 0.0

    result = {
        "valid": valid,
        "score": final_score,
        "judge_version": JUDGE_VERSION,
        "runtime_sec": round(elapsed, 4),
        "hn_live_baseline_score": hn_metrics["score"],
        "delta_vs_hn": round(final_score - hn_metrics["score"], 4) if valid else None,
        "dev_score": dev_m["score"],
        "holdout_score": holdout_m["score"],
        "full_metrics": full_m,
        "hn_live_metrics": hn_metrics,
        "invariant_errors": inv_errors,
    }
    print(json.dumps(result, indent=2))
    print(
        f"[Judge v{JUDGE_VERSION}] valid={valid} score={final_score:.4f} "
        f"(HN live={hn_metrics['score']:.4f}) runtime={elapsed:.3f}s | "
        f"dev={dev_m['score']:.2f} ndcg20={dev_m['ndcg20']:.3f} "
        f"concord={dev_m['pairwise_concordance']:.3f} adv={dev_m['adversarial_acc']:.3f} "
        f"rescue={dev_m['buried_gold_recall_top45']:.3f} sink={dev_m['bullshit_sink_percentile']:.3f} "
        f"div={dev_m['top20_diversity']:.3f}"
        + (f" | ERRORS={inv_errors}" if inv_errors else ""),
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
