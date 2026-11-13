#!/usr/bin/env python3
"""External Judge v1.0.0 for HN Epistemic Signal vs Bullshit Tournament.

Usage:
    uv run --no-project python judge_v1.py <candidate_repo_or_hn_comments_dir>

Outputs `{valid: bool, score: float, ...}` JSON on stdout and concise diagnostics
on stderr (reporting dev breakdown ONLY so holdout IDs never leak to workers).
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

JUDGE_VERSION = "1.0.0"
JUDGE_DIR = Path(__file__).resolve().parent
FIXTURES_PATH = JUDGE_DIR / "epistemic_fixtures_v1.json"
CANONICAL_CORPUS_PATH = JUDGE_DIR.parent / "data" / "corpus_v2.json"


def compute_ndcg(ordered_ids: list[int], grade_map: dict[int, int], k: int = 25) -> float:
    """Compute graded NDCG@k over judged items ordered by their induced global ranking.

    :param ordered_ids: Full global ranking of comment IDs (best first).
    :param grade_map: Mapping of judged comment ID -> grade (0..3).
    :param k: Cutoff rank within judged pool.
    :return: NDCG@k in [0, 1].
    """
    judged_ordered = [cid for cid in ordered_ids if cid in grade_map][:k]
    dcg = 0.0
    for idx, cid in enumerate(judged_ordered):
        gain = (2 ** grade_map[cid]) - 1.0
        dcg += gain / math.log2(idx + 2.0)

    ideal_grades = sorted(grade_map.values(), reverse=True)[:k]
    idcg = sum(((2**g) - 1.0) / math.log2(idx + 2.0) for idx, g in enumerate(ideal_grades))
    return (dcg / idcg) if idcg > 0 else 0.0


def compute_all_pairs_concordance(ordered_ids: list[int], grade_map: dict[int, int]) -> float:
    """Compute generalized Kendall/ROC concordance across all strictly ordered grade pairs.

    :param ordered_ids: Full global ranking of comment IDs (best first).
    :param grade_map: Mapping of judged comment ID -> grade (0..3).
    :return: Fraction of (high_grade, low_grade) pairs ranked in the right direction.
    """
    pos = {cid: idx for idx, cid in enumerate(ordered_ids)}
    items = [(cid, g) for cid, g in grade_map.items() if cid in pos]
    wins = 0.0
    total = 0.0
    for i in range(len(items)):
        id_a, g_a = items[i]
        for j in range(i + 1, len(items)):
            id_b, g_b = items[j]
            if g_a == g_b:
                continue
            hi, lo = (id_a, id_b) if g_a > g_b else (id_b, id_a)
            weight = float(abs(g_a - g_b))
            total += weight
            if pos[hi] < pos[lo]:
                wins += weight
    return (wins / total) if total > 0 else 0.0


def compute_top20_diversity(top20: list[dict[str, Any]]) -> float:
    """Measure submodular facet entropy * (1 - mean pairwise TF-IDF cosine) on Global Top 20.

    :param top20: Top 20 ranked comment dicts.
    :return: Diversity score in [0, 1].
    """
    if not top20:
        return 0.0
    # 1. Normalized Shannon entropy over the 5 substantive facets
    facet_counts: dict[str, int] = {}
    for c in top20:
        f = c.get("facet", "general_commentary")
        facet_counts[f] = facet_counts.get(f, 0) + 1
    n = float(len(top20))
    entropy = -sum((cnt / n) * math.log2(cnt / n) for cnt in facet_counts.values())
    norm_entropy = min(1.0, entropy / math.log2(5.0))

    # 2. Pairwise TF-IDF non-redundancy
    vecs = [{k: v for k, v in (c.get("tfidf_top") or [])} for c in top20]
    sim_sum = 0.0
    pairs = 0
    for i in range(len(vecs)):
        for j in range(i + 1, len(vecs)):
            sim = sum(w * vecs[j].get(t, 0.0) for t, w in vecs[i].items())
            sim_sum += min(1.0, sim)
            pairs += 1
    mean_sim = (sim_sum / pairs) if pairs > 0 else 0.0
    # 3. Root diversity (penalize single-subtree monopoly)
    unique_roots = len({c.get("root_id") or c["id"] for c in top20}) / n
    return 0.45 * norm_entropy + 0.35 * (1.0 - mean_sim) + 0.20 * min(1.0, unique_roots / 0.75)


def score_ordering(
    ordered_comments: list[dict[str, Any]],
    fixtures: dict[str, Any],
    split_filter: str | None = None,
) -> dict[str, float]:
    """Compute component metrics and scalar 0..100 score for any ordering of the corpus."""
    ordered_ids = [c["id"] for c in ordered_comments]
    pos = {cid: idx + 1 for idx, cid in enumerate(ordered_ids)}

    graded = [
        x
        for x in fixtures["graded_items"]
        if split_filter is None or x["split"] == split_filter
    ]
    grade_map = {x["id"]: int(x["grade"]) for x in graded}

    ndcg20 = compute_ndcg(ordered_ids, grade_map, k=20)
    concordance = compute_all_pairs_concordance(ordered_ids, grade_map)

    adv_pairs = [
        p
        for p in fixtures["adversarial_pairs"]
        if split_filter is None or p["split"] == split_filter
    ]
    adv_wins = sum(
        1 for p in adv_pairs if pos.get(p["winner_id"], 9999) < pos.get(p["loser_id"], 9999)
    )
    adv_acc = adv_wins / max(1, len(adv_pairs))

    # Global recall: Grade-3 items buried at HN DOM > 500 rescued into Global Top 45 (top 1.5% of 3,010!)
    by_id = {c["id"]: c for c in ordered_comments}
    buried_gold = [
        cid
        for cid, g in grade_map.items()
        if g == 3 and (by_id[cid].get("live_dom_rank") or 9999) > 500
    ]
    rescued = sum(1 for cid in buried_gold if pos.get(cid, 9999) <= 45)
    buried_recall = rescued / max(1, len(buried_gold))

    # Noise suppression: mean global percentile of Grade-0 bullshit items (1.0 = pushed to bottom!)
    n_total = float(len(ordered_comments))
    g0_ids = [cid for cid, g in grade_map.items() if g == 0]
    bullshit_sink = (
        sum((pos[cid] - 1.0) / max(1.0, n_total - 1.0) for cid in g0_ids) / max(1, len(g0_ids))
    )

    diversity = compute_top20_diversity(ordered_comments[:20])

    scalar = 100.0 * (
        0.26 * ndcg20
        + 0.24 * concordance
        + 0.20 * adv_acc
        + 0.12 * buried_recall
        + 0.10 * bullshit_sink
        + 0.08 * diversity
    )
    return {
        "score": round(scalar, 4),
        "ndcg20": round(ndcg20, 4),
        "pairwise_concordance": round(concordance, 4),
        "adversarial_acc": round(adv_acc, 4),
        "buried_gold_recall_top45": round(buried_recall, 4),
        "bullshit_sink_percentile": round(bullshit_sink, 4),
        "top20_diversity": round(diversity, 4),
    }


def check_invariants(ranked: list[dict[str, Any]], expected_ids: set[int]) -> list[str]:
    """Enforce hard Anti-Goodhart invariants before accepting any candidate score."""
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

    # Anti-Goodhart structural invariants on Global Top 35..50
    top35 = ranked[:35]
    top50 = ranked[:50]
    deep_faded_top35 = [c["id"] for c in top35 if int(c.get("downvote_tier", 0)) >= 2]
    if deep_faded_top35:
        errors.append(f"Deeply downvoted (c73..cDD) comments in Top 35: {deep_faded_top35[:5]}")

    mod_rebuked_top60 = [c["id"] for c in ranked[:60] if c.get("is_mod_rebuked")]
    if mod_rebuked_top60:
        errors.append(f"Moderator-rebuked comments in Top 60: {mod_rebuked_top60}")

    stubs_top50 = [c["id"] for c in top50 if int(c.get("own_word_count", 0)) < 8]
    if stubs_top50:
        errors.append(f"Bare stub (<8 own words) comments in Top 50: {stubs_top50[:5]}")

    exact_dups_top40 = [c["id"] for c in ranked[:40] if float(c.get("max_older_dup_cos", 0.0)) >= 0.85]
    if exact_dups_top40:
        errors.append(f"Near-exact copy-paste duplicates in Top 40: {exact_dups_top40}")

    return errors


def resolve_ranker_path(target: Path) -> Path:
    """Locate `ranker.py` inside either workspace root or `hn-comments` subdir."""
    if (target / "hn-comments" / "ranker.py").exists():
        return target / "hn-comments" / "ranker.py"
    if (target / "ranker.py").exists():
        return target / "ranker.py"
    raise FileNotFoundError(f"Could not locate ranker.py under {target}")


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: judge_v1.py <candidate_dir>", file=sys.stderr)
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

    # Baseline 0: Live Hacker News DOM Rank on exact same benchmark!
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

    inv_errors = check_invariants(ranked, expected_ids)
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

    # Concise worker-safe diagnostics on stderr (NEVER prints holdout comment IDs!)
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
