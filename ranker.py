"""Epistemic Signal vs Bullshit Ranker (v1.0 Baseline).

Decomposes every comment into five orthogonal epistemic potentials:
1. Specific Information Gain (Shannon/IDF surprisal minus crowd cliché & copy-paste redundancy)
2. Popperian Falsifiability (context-coupled primary citations, quantitative/legal/technical specificity)
3. Inverse `news.arc` Physics & Progeny Catalyst (gravity-corrected survival + t1->t2 velocity + author precision)
4. Frankfurtian Bullshit & Tribal Heat Suppression (unfalsifiable conspiracy, swipes, memes, off-topic drift)
5. Greedy Submodular MMR Portfolio Selection (eliminating semantic redundancy & single-root hijacking)
"""

import math
import re
from typing import Any

DEFAULT_WEIGHTS: dict[str, float] = {
    "info_gain": 2.35,
    "falsifiability": 2.85,
    "gravity_progeny": 1.45,
    "bullshit_penalty": 2.65,
    "downvote_penalty": 3.10,
    "mmr_sim_lambda": 2.30,
    "mmr_root_lambda": 0.42,
    "mmr_facet_lambda": 0.22,
}

_TOKEN_RE = re.compile(r"[a-z0-9]{2,}")
_TAIL_PROFANITY_RE = re.compile(
    r"\b(?:fuck\w*|shit\w*|asshole\w*|bitch\w*|idiot\w*|moron\w*|clown\w*)\b",
    re.IGNORECASE,
)
_TAIL_CONDESCENSION_RE = re.compile(
    r"\b(?:you (?:clearly|obviously|plainly) (?:don't|do not|can't|cannot) understand"
    r"|learn to read|reading comprehension|cope harder)\b",
    re.IGNORECASE,
)
_TAIL_CONSPIRACY_RE = re.compile(
    r"\bwhy now\b|\bhard to believe (?:that )?there (?:isn't|is not) "
    r"(?:(?:a|some) )?(?:plot|conspiracy)\b|\btoo much of a coincidence\b",
    re.IGNORECASE,
)


def _is_short_documentary(c: dict[str, Any]) -> bool:
    own_w = int(c.get("own_word_count", 0))
    quote_w = int(c.get("quoted_word_count", 0))
    url_tier = int(c.get("url_tier", 0))
    return (
        2 <= own_w <= 15
        and own_w + quote_w >= 8
        and ((url_tier >= 2 and quote_w >= 20) or url_tier == 3)
        and int(c.get("meme_hits", 0)) == 0
        and int(c.get("off_topic_hits", 0)) == 0
        and not c.get("is_mod_note", False)
    )


def _quoted_lexical_features(
    comments: list[dict[str, Any]],
) -> list[tuple[float, float] | None]:
    quote_tokens: list[list[str] | None] = []
    quote_terms: set[str] = set()
    for c in comments:
        if (
            not _is_short_documentary(c)
            or int(c.get("quoted_word_count", 0)) == 0
            or int(c.get("downvote_tier", 0)) >= 2
            or bool(c.get("is_dead", False))
            or bool(c.get("is_mod_rebuked", False))
            or float(c.get("max_older_dup_cos", 0.0)) >= 0.85
        ):
            quote_tokens.append(None)
            continue
        text = str(c.get("quoted_text") or c.get("text") or "")
        tokens = _TOKEN_RE.findall(text.casefold())
        quote_tokens.append(tokens or None)
        quote_terms.update(tokens)

    if not quote_terms:
        return [None] * len(comments)

    document_frequency = dict.fromkeys(quote_terms, 0)
    for c in comments:
        text = " ".join(
            str(c.get(field) or "")
            for field in ("text", "quoted_text", "own_text")
        )
        document_terms = set(_TOKEN_RE.findall(text.casefold()))
        for term in quote_terms.intersection(document_terms):
            document_frequency[term] += 1

    document_count = len(comments)
    term_idf = {
        term: math.log2((document_count + 1.0) / (frequency + 1.0))
        for term, frequency in document_frequency.items()
    }
    features: list[tuple[float, float] | None] = []
    for tokens in quote_tokens:
        if not tokens:
            features.append(None)
            continue
        informative = {term for term in tokens if term_idf[term] >= 2.0}
        quote_info_bits = sum(term_idf[term] for term in informative)
        quote_content_ratio = sum(
            term_idf[term] >= 2.0 for term in tokens
        ) / len(tokens)
        features.append((quote_info_bits, quote_content_ratio))
    return features


def classify_epistemic_tier(
    c: dict[str, Any], epistemic_pos: float, bullshit_neg: float, down_neg: float
) -> str:
    """Assign each comment to one of 6 interpretable epistemic classes.

    :param c: Enriched comment dict from `corpus_v2.json`.
    :param epistemic_pos: Positive epistemic + gravity signal.
    :param bullshit_neg: Bullshit / meme / off-topic load.
    :param down_neg: Community downvote / moderation sink load.
    :return: Tier string matching `CONTRACT.md`.
    """
    if c.get("is_dead") or int(c.get("downvote_tier", 0)) >= 2 or down_neg >= 2.5:
        return "downvoted_sink"
    if int(c.get("meme_hits", 0)) > 0 and int(c.get("own_word_count", 0)) < 55:
        return "meme_or_snark"
    if bullshit_neg >= 1.45 and bullshit_neg > 0.65 * epistemic_pos:
        return "bullshit_or_flamewar"
    net = epistemic_pos - bullshit_neg - down_neg
    if net >= 6.6 and (int(c.get("url_tier", 0)) >= 2 or epistemic_pos >= 7.4):
        return "epistemic_gold"
    if net >= 4.1:
        return "grounded_analysis"
    return "crowd_chatter"


def score_single_comment(
    c: dict[str, Any],
    weights: dict[str, float] | None = None,
    *,
    quote_features: tuple[float, float] | None = None,
    n_total: int = 3010,
) -> dict[str, Any]:
    """Compute epistemic sub-potentials and raw score for a single comment.

    :param c: Enriched comment dictionary from `corpus_v2.json` or `corpus_science.py`.
    :param weights: Optional weight overrides.
    :return: Dictionary with `signal_score`, `epistemic_score`, `bullshit_score`, `tier`, `components`.
    """
    w = {**DEFAULT_WEIGHTS, **(weights or {})}

    own_w = int(c.get("own_word_count", 0))
    quote_w = int(c.get("quoted_word_count", 0))
    paras = int(c.get("paragraph_count", 0))
    content_ratio = float(c.get("content_token_ratio", 0.0))
    spec_bits = float(c.get("specific_info_bits", 0.0))
    surprisal = float(c.get("crowd_surprisal_bits", 0.0))
    art_cos = float(c.get("article_tfidf_cos", 0.0))
    anchors = int(c.get("core_anchor_hits", 0))
    off_topic = int(c.get("off_topic_hits", 0))
    dup_cos = float(c.get("max_older_dup_cos", 0.0))
    cluster_dens = float(c.get("crowd_cluster_density", 0.0))

    url_tier = int(c.get("url_tier", 0))
    low_urls = int(c.get("low_cred_url_count", 0))
    primary_urls = int(c.get("primary_url_count", 0))
    quants = int(c.get("quant_count", 0))
    popper = int(c.get("popper_hits", 0))
    calibrated = int(c.get("calibrated_hits", 0))
    conspiracy = int(c.get("conspiracy_hits", 0))
    swipes = int(c.get("swipe_hits", 0))
    memes = int(c.get("meme_hits", 0))

    implied_votes = float(c.get("implied_extra_votes", 0.0))
    surf_idx = float(c.get("surf_mirage_index", 0.0))
    temp_delta = float(c.get("temporal_pct_delta", 0.0))
    newly_down = bool(c.get("newly_downvoted", False))
    down_tier = int(c.get("downvote_tier", 0))
    is_dead = bool(c.get("is_dead", False))
    mod_rebuked = bool(c.get("is_mod_rebuked", False))
    mod_note = bool(c.get("is_mod_note", False))

    short_documentary = _is_short_documentary(c)
    if short_documentary and quote_features is not None:
        quote_info_bits, quote_content_ratio = quote_features
        spec_bits += quote_info_bits
        combined_w = own_w + quote_w
        if combined_w > 0:
            content_ratio = (
                content_ratio * own_w + quote_content_ratio * quote_w
            ) / combined_w

    kpp = float(c.get("author_kpp", 0.0))
    karma = int(c.get("author_karma", 0))
    is_throwaway = bool(c.get("is_throwaway", False))
    author_posts = int(c.get("author_thread_posts", 1))
    ping_pong = int(c.get("ping_pong_depth", 0))
    constructive_kids = int(c.get("constructive_reply_authors", 0))
    faded_kids = int(c.get("faded_reply_count", 0))
    depth = int(c.get("depth", 0))
    dom_rank = int(c.get("live_dom_rank") or max(1, n_total))
    anc_down = bool(c.get("ancestor_downvoted", False))

    # --- 1. Specific Information Gain (Shannon/IDF mass * density * on-topic gate) ---
    info_w = own_w + quote_w if short_documentary else own_w
    if own_w < 8 and not short_documentary:
        info_raw = -0.95
    else:
        # Smooth length curve reaching 0.65 by 42 words so concise sourced rebuttals thrive
        len_factor = math.tanh((info_w - 8.0) / 46.0)
        idf_mass = min(1.85, spec_bits / 21.0)
        density_mod = min(1.22, max(0.35, content_ratio / 0.46))
        surprisal_bonus = min(0.35, max(0.0, (surprisal - 8.2) * 0.12))
        struct_bonus = min(0.32, max(0, paras - 1) * 0.11)

        # Penalize pure hedging vapor (>140 words with zero links, zero numbers, low anchors)
        vapor_damp = 0.52 if (own_w > 135 and url_tier <= 0 and quants == 0 and anchors <= 2) else 1.0
        # Require semantic connection to the Nvidia/governance/chip/intelligence event
        topic_gate = 1.0 if (anchors >= 2 or art_cos >= 0.055) else (0.76 if anchors == 1 else 0.44)
        # Discount predictable crowd clichés
        cliche_damp = max(0.65, 1.0 - 0.35 * min(1.0, cluster_dens)) if url_tier <= 0 else 1.0

        info_raw = (0.55 * len_factor + 0.72 * idf_mass * density_mod + surprisal_bonus + struct_bonus)
        info_raw *= vapor_damp * topic_gate * cliche_damp

    # --- 2. Popperian Falsifiability & Documentary Evidence ---
    fals_raw = 0.0
    is_substantive_context = (
        (own_w >= 15 or short_documentary)
        and memes == 0
        and off_topic == 0
        and not mod_note
    )
    if url_tier >= 3 and is_substantive_context:
        fals_raw += 2.35
    elif url_tier == 2 and is_substantive_context:
        # Guard against 1-line meme-wrapped news links (<20 words without quotes/mechanisms)
        if own_w >= 24 or quote_w >= 8 or popper >= 1 or quants >= 1:
            fals_raw += 1.78
        else:
            fals_raw += 0.45
    elif url_tier == 1 and is_substantive_context and own_w >= 28:
        fals_raw += 0.62

    if (
        url_tier == 2
        and is_substantive_context
        and (anchors >= 2 or art_cos >= 0.055)
    ):
        fals_raw += 0.30

    # Quantitative anchors, causal/evidential operators, calibrated epistemic stance
    if memes == 0 and off_topic == 0:
        fals_raw += min(0.95, 0.34 * quants)
        fals_raw += min(0.85, 0.28 * popper)
        fals_raw += min(0.45, 0.22 * calibrated)
        # Quote-and-refute bonus when civil and substantive
        if quote_w >= 5 and own_w >= 24 and swipes == 0:
            fals_raw += 0.42

    # --- 3. Inverse `news.arc` Physics, Bayesian Author Precision & Tree Rescue ---
    grav_raw = 0.0
    if implied_votes > 0 and down_tier == 0:
        grav_raw += min(1.15, 0.38 * math.log1p(implied_votes))
    if temp_delta > 0.02 and down_tier == 0:
        grav_raw += min(0.35, temp_delta * 1.8)
    if constructive_kids >= 2:
        grav_raw += min(0.55, 0.18 * constructive_kids)

    # Bayesian Author Precision: ONLY amplifies genuine non-meme, non-swipe analytical signal
    clean_epistemic_core = max(0.0, info_raw) + fals_raw
    if clean_epistemic_core >= 1.35 and memes == 0 and swipes == 0 and conspiracy == 0 and karma >= 400:
        author_prec = min(0.68, max(0.0, math.log1p(max(0.0, kpp - 2.2)) * 0.32))
        grav_raw += author_prec * min(1.0, clean_epistemic_core / 2.5)

    # Tree-Lock Rescue: surface strong buried comments (depth >= 2 or proportional DOM cutoff)
    buried_dom_cutoff = min(450, max(40, int(0.15 * n_total)))
    dom_scale = min(2200.0, max(180.0, 2200.0 * (n_total / 3010.0)))
    if (depth >= 2 or dom_rank > buried_dom_cutoff) and clean_epistemic_core >= 1.65 and memes == 0 and off_topic == 0:
        depth_lift = min(0.55, 0.12 * depth) + min(0.45, dom_rank / dom_scale)
        anc_lift = 0.22 if (anc_down and down_tier == 0) else 0.0
        grav_raw += (depth_lift + anc_lift) * min(1.15, clean_epistemic_core / 2.4)

    # --- 4. Frankfurtian Bullshit, Meme, Off-Topic, Surf-Mirage & Duplicate Load ---
    bs_raw = 0.0
    if own_w < 8 and not short_documentary:
        bs_raw += 2.60
    elif own_w < 16 and url_tier < 2:
        bs_raw += 1.15

    # Bare link drops or low-credibility/joke URLs (YouTube, lmgtfy, wiktionary, Reddit rumors)
    if low_urls > 0:
        bs_raw += 1.35 * low_urls
    if any("reddit.com" in d for d in (c.get("url_domains") or [])):
        bs_raw += 1.45
    if mod_note:
        bs_raw += 1.80

    # Memes & one-liner snark (even when high-karma or carrying a CNBC/Nvidia URL!)
    if memes > 0:
        bs_raw += 1.65 * memes if own_w < 85 else 0.75 * memes

    # Off-topic drift (Epstein, cockroaches, Woźniak, Zelensky, polyamory, Overton window)
    if off_topic > 0:
        bs_raw += 1.95 * off_topic if anchors <= 2 else 0.95 * off_topic

    # Unfalsifiable conspiracy posturing & tribal ad-hominem swipes
    if conspiracy > 0:
        bs_raw += (1.35 if url_tier < 2 else 0.65) * conspiracy
    if swipes > 0:
        bs_raw += 1.15 * swipes

    # Surface-level tail cues count only when credible evidence and topic grounding are absent.
    own_text = str(c.get("own_text", c.get("text", "")) or "")
    evidence_thin = (
        url_tier < 2
        and primary_urls == 0
        and anchors < 2
        and quants == 0
        and popper == 0
        and art_cos < 0.055
    )
    if evidence_thin:
        tail_noise = 0.0
        if (
            low_urls == 0
            and c.get("urls")
            and own_w <= 36
            and quote_w < 8
        ):
            tail_noise += 0.75
        if 8 <= own_w <= 28 and paras <= 1 and not c.get("urls"):
            tail_noise += 0.45
        if swipes == 0 and _TAIL_PROFANITY_RE.search(own_text):
            tail_noise += 0.60
        if swipes == 0 and _TAIL_CONDESCENSION_RE.search(own_text):
            tail_noise += 0.60
        if conspiracy == 0 and _TAIL_CONSPIRACY_RE.search(own_text):
            tail_noise += 0.80
        if surf_idx > 3.0 and clean_epistemic_core < 2.2:
            tail_noise += min(1.60, 0.45 + 0.28 * (surf_idx - 3.0))
        bs_raw += min(2.10, tail_noise)

    # Throwaway sleeper skepticism on unsourced claims
    if is_throwaway and url_tier < 2:
        bs_raw += 0.95

    # Flamewar ping-pong & thread flooding (sparing comments with Tier 2/3 primary citations!)
    if ping_pong >= 4 and url_tier < 2:
        bs_raw += 0.32 * (ping_pong - 3)
    if author_posts >= 9 and url_tier < 2 and own_w < 90:
        bs_raw += min(0.95, 0.10 * (author_posts - 8))
    if faded_kids >= 2 and url_tier < 2:
        bs_raw += 0.25 * faded_kids

    # Copy-paste / near-duplicate suppression
    if dup_cos >= 0.85:
        bs_raw += 4.20
    elif dup_cos >= 0.62:
        bs_raw += 1.65 * dup_cos

    # --- 5. Community Downvote & Moderation Sink (with c5A Heterodox Evidence Rescue!) ---
    down_raw = 0.0
    if is_dead:
        down_raw += 5.0
    if mod_rebuked:
        down_raw += 4.5
    if newly_down and url_tier < 2:
        down_raw += 0.55

    if down_tier >= 2:
        # Deeply faded c73..cDD: decisive community rejection
        down_raw += 2.20 + 0.85 * ((down_tier - 1) ** 1.3)
    elif down_tier == 1:
        # c5A = single net downvote: rescue civil primary-sourced counter-narratives!
        if url_tier >= 2 and swipes == 0 and memes == 0 and off_topic == 0 and own_w >= 18:
            down_raw += 0.08
        else:
            down_raw += 1.15

    epistemic_pos = (
        w["info_gain"] * info_raw
        + w["falsifiability"] * fals_raw
        + w["gravity_progeny"] * grav_raw
    )
    bullshit_neg = w["bullshit_penalty"] * bs_raw
    down_neg = w["downvote_penalty"] * down_raw

    raw_total = epistemic_pos - bullshit_neg - down_neg
    tier = classify_epistemic_tier(c, epistemic_pos, bullshit_neg, down_neg)

    return {
        "signal_score": round(raw_total, 4),
        "epistemic_score": round(max(0.0, epistemic_pos), 4),
        "bullshit_score": round(max(0.0, bullshit_neg + down_neg), 4),
        "tier": tier,
        "components": {
            "info_gain": round(w["info_gain"] * info_raw, 3),
            "falsifiability": round(w["falsifiability"] * fals_raw, 3),
            "gravity_progeny": round(w["gravity_progeny"] * grav_raw, 3),
            "bullshit_load": round(-bullshit_neg, 3),
            "downvote_sink": round(-down_neg, 3),
        },
    }


def _tfidf_cos(v1: dict[str, float], v2: dict[str, float]) -> float:
    if not v1 or not v2:
        return 0.0
    if len(v1) > len(v2):
        v1, v2 = v2, v1
    return sum(val * v2.get(term, 0.0) for term, val in v1.items())


def rank_comments(
    comments: list[dict[str, Any]], weights: dict[str, float] | None = None
) -> list[dict[str, Any]]:
    """Score all comments and apply Greedy Submodular MMR portfolio selection on Top-K.

    :param comments: Canonical list of enriched comment dicts from `corpus_v2.json`.
    :param weights: Optional weight overrides.
    :return: Ranked comment list with `signal_rank` 1..N.
    """
    w = {**DEFAULT_WEIGHTS, **(weights or {})}
    scored: list[dict[str, Any]] = []
    vecs: dict[int, dict[str, float]] = {}
    quote_features = _quoted_lexical_features(comments)

    n_total = max(1, len(comments))
    for c, quote_metrics in zip(comments, quote_features):
        res = score_single_comment(c, weights=w, quote_features=quote_metrics, n_total=n_total)
        merged = {**c, **res}
        scored.append(merged)
        vecs[c["id"]] = {term: float(val) for term, val in (c.get("tfidf_top") or [])}

    scored.sort(
        key=lambda x: (x["signal_score"], -(x.get("live_dom_rank") or 99999)),
        reverse=True,
    )

    # Greedy Submodular MMR Reranking over top 110 candidates to select diverse Top 55
    pool_size = min(110, len(scored))
    select_k = min(55, pool_size)
    pool = scored[:pool_size]
    tail = scored[pool_size:]

    selected: list[dict[str, Any]] = []
    root_counts: dict[int, int] = {}
    facet_counts: dict[str, int] = {}
    remaining = list(pool)

    for _step in range(select_k):
        best_idx = 0
        best_mmr = -1e18
        for idx, cand in enumerate(remaining):
            cid = cand["id"]
            cvec = vecs[cid]
            max_sim = 0.0
            for prev in selected:
                sim = _tfidf_cos(cvec, vecs[prev["id"]])
                if sim > max_sim:
                    max_sim = sim
            rid = int(cand.get("root_id") or cid)
            facet = cand.get("facet", "general_commentary")
            r_cnt = root_counts.get(rid, 0)
            f_cnt = facet_counts.get(facet, 0)

            # Ignore shared-topic overlap; preserve full cost for near-identical vectors.
            sim_hinge = min(1.0, max(0.0, (max_sim - 0.30) / 0.70))
            root_hinge = min(r_cnt, 3)
            facet_hinge = min(max(0, f_cnt - 3), 5)
            root_similarity_factor = 0.35 + 0.65 * sim_hinge
            mmr_pen = (
                w["mmr_sim_lambda"] * sim_hinge
                + w["mmr_root_lambda"] * root_hinge * root_similarity_factor
                + w["mmr_facet_lambda"] * facet_hinge
            )
            mmr_val = cand["signal_score"] - mmr_pen
            if mmr_val > best_mmr:
                best_mmr = mmr_val
                best_idx = idx

        chosen = remaining.pop(best_idx)
        chosen["_mmr_score"] = round(best_mmr, 4)
        selected.append(chosen)
        rid = int(chosen.get("root_id") or chosen["id"])
        facet = chosen.get("facet", "general_commentary")
        root_counts[rid] = root_counts.get(rid, 0) + 1
        facet_counts[facet] = facet_counts.get(facet, 0) + 1

    # Maintain monotonic decreasing `signal_score` across selected + remaining + tail
    final_list = selected + remaining + tail
    running_ceil = float("inf")
    for idx, item in enumerate(final_list, start=1):
        eff = item.pop("_mmr_score", item["signal_score"])
        if eff >= running_ceil:
            eff = round(running_ceil - 0.0001, 4)
        running_ceil = eff
        item["signal_score"] = round(eff, 4)
        item["signal_rank"] = idx

    return final_list
