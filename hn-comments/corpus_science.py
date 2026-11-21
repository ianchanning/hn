"""Stage 1 Story-Agnostic Scientific Pipeline: Information-Theoretic, Graph & Epistemic Engine.

Transforms any Hacker News thread (`?p=1..N` paginated HTML, optional `t1` snapshot,
Algolia tree, SQLite-cached author profiles, and linked story article) into an enriched
epistemic dataset with zero story-specific hardcoded lexicons:
- Cross-domain URL tiering via `source_registry.py`
- Unsupervised TF-IDF + multi-root consensus story anchors
- Unsupervised vector-space subtree drift + localized single-root digression detection
- Unsupervised short-quip running-gag discovery + universal HN snowclone detection
- Deterministic 5-cluster spherical k-means++ auto-labeled topic facets
"""

from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any

from ingest import ingest_story
from parse_corpus import DATA_DIR, merge_algolia_dead_comments, parse_live_html_pages
from source_registry import classify_urls, classify_urls_detailed

STOPWORDS: frozenset[str] = frozenset(
    """
    a about above after again against all am an and any are aren aren't as at be because
    been before being below between both but by can can't cannot could couldn couldn't did
    didn didn't do does doesn doesn't doing don don't down during each few for from further
    had hadn hadn't has hasn hasn't have haven haven't having he he'd he'll he's her here
    here's hers herself him himself his how how's i i'd i'll i'm i've if in into is isn
    isn't it it's its itself let's ll me more most mustn mustn't my myself no nor not of
    off on once only or other ought our ours ourselves out over own re same shan shan't she
    she'd she'll she's should shouldn shouldn't so some such than that that's the their
    theirs them themselves then there there's these they they'd they'll they've this those
    through to too under until up ve very was wasn wasn't we we'd we'll we're we've were
    weren weren't what what's when when's where where's which while who who's whom why
    why's will with won won't would wouldn wouldn't you you'd you'll you're you've your
    yours yourself yourselves just like think really even still much many way thing things
    people someone anyone something anything nothing going get got make made know see say
    says said saying take back well also pretty sure right now one two may might actually
    probably maybe literally basically though although whether
    """.split()
)

UPPERCASE_ACRONYMS: frozenset[str] = frozenset(
    """
    ai ml llm llms nlp rl gpu gpus cpu cpus tpu npu ram vram dram sram ssd nvme hdd
    api apis sdk cli gui tui sql nosql orm dns bgp tcp udp quic tls ssl ssh http ipc rpc
    ast ir ssa jit aot gc wasm simd avx ffi abi os vm kvm ebpf io zfs ext4
    aws gcp oci cdn waf iam mfa sso oidc jwt rbac sla slo sli sre m365
    rfc doi cve nvd mit gpl lgpl bsd
    ceo cfo cto coo vp hr pr ir ipo sec doj fbi cia nsa bis ftc fcc fda epa irs eu uk us
    gdp cpi fed pe vc arr mrr capex opex saas b2b b2c
    cuda rocm tsmc asml arm x86 risc
    """.split()
)

GENERAL_DISCOURSE_STOP: frozenset[str] = frozenset(
    """
    another without must every some since around within across become became find found
    build built building forward new old first second third fourth fifth last next high
    low big small long short early late real full clear different similar possible
    impossible likely unlikely able unable come comes came making either neither others
    top bottom future past present personal public private general specific local global
    need needs needed want wants wanted use used using uses give given gave put puts set
    sets run runs running try trying tried let lets less least ever never always often
    sometimes already yet away enough quite rather almost especially certainly obviously
    clearly simply exactly perhaps tell told talking heard seen start started stop stopped
    keep kept call called comment comments thread threads article articles post posts
    hacker news hn point points link links read reading write written writing year years
    month months week weeks day days hour hours minute minutes time times good great bad
    better best worst true false wrong agree disagree question questions answer answers
    person guys folks everyone nobody somebody world life work working worked mean means
    meant look looks looking seem seems case cases part parts reason reasons fact facts
    example examples issue issues problem problems idea ideas level sense kind sort lot
    bit stuff http https www com org net html io dev gov edu pdf
    yeah yes yep nope nah okay fine wonder completely totally soon yesterday tomorrow ago blog
    """.split()
)

HN_MODERATORS: frozenset[str] = frozenset({"dang", "tomhow"})

POPPER_EVIDENCE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\baccording to\b", re.I),
    re.compile(r"\bevidence\b|\bempirical\b|\bmeasured\b|\bbenchmark(?:s|ed)?\b", re.I),
    re.compile(
        r"\b(?:s-1|10-k|8-k|def\s*14a|rfc\s*\d+|cve-\d{4}-\d+|arxiv|doi|preprint|filing|"
        r"press release|postmortem|changelog|release notes|specification|subpoena|statute)\b",
        re.I,
    ),
    re.compile(
        r"\b(?:fiduciary|conflict of interest|code of conduct|export control|entity list|"
        r"import approval|customs|memory safety|latency|throughput|regression|complexity|"
        r"reproduc(?:e|ible)|root cause|telemetry)\b",
        re.I,
    ),
    re.compile(r"\b(?:specifically|for example|for instance|in contrast|whereas|therefore|implies|precedent)\b", re.I),
    re.compile(r"(?:^|\n)\s*(?:[1-4][.)]|\*|-)\s+\w+", re.M),
)

CALIBRATED_MODALITY_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(?:unlikely|plausible|unclear|unproven|alleged|reportedly|appears to|depends on|estimate)\b", re.I),
    re.compile(r"\bno evidence\b|\bzero evidence presented\b|\bnot proven\b|\bcaveat\b", re.I),
)

FRANKFURT_CONSPIRACY_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"\b(?:psyop|manufactured consent|fabricated reality|deep state|3 letter agenc|"
        r"cia operation|friendly puppet|false flag|controlled opposition)\b",
        re.I,
    ),
    re.compile(r"\b(?:wake up|don't be naive|anyone with half a brain|blindly believe|sheeple|sheep)\b", re.I),
    re.compile(r"\b(?:zero possibility|100% guaranteed|you can guarantee|blatant and open collusion)\b", re.I),
    re.compile(r"\bwmd\b.*\biraq\b|\biraq\b.*\bwmd\b", re.I),
)

TRIBAL_SWIPE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bgaslighting\b", re.I),
    re.compile(r"\bfucked\b|\bflying f\b|\bwtf\b|\bbullshit\b", re.I),
    re.compile(r"\bbruh\b|\blmao\b|\brofl\b|\blmfao\b", re.I),
    re.compile(
        r"\b(?:bootlicker|shill|cope|delusional|psychopath|sniveling|"
        r"adorable how naive|reading comprehension fail|midwit|clown)\b",
        re.I,
    ),
    re.compile(r"\byou(?:'re| are) (?:wrong|naive|making it sound|missing the point|clueless)\b", re.I),
    re.compile(r"\bhopefully you(?:'re| are) not\b|\byou should probably do some research\b", re.I),
    re.compile(r"<gets presented with", re.I),
)

UNIVERSAL_MEME_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\ba second .* has hit the\b", re.I),
    re.compile(r"\bsir,? this is a wendy'?s\b", re.I),
    re.compile(r"\bthe more you \w+,?\s+the more you \w+\b", re.I),
    re.compile(r"\bsell (?:them|his \w+|her \w+|their \w+) and live\b", re.I),
    re.compile(r"\b(?:we have .* at home|instructions unclear|aged like milk|bingo card|plot twist\s*:)\b", re.I),
    re.compile(r"\b(?:grabs? popcorn|spit out my coffee|rip (?:my |his |her )?inbox|found the .* account)\b", re.I),
    re.compile(r"\b(?:stonks|diamond hands|hodl|to the moon|remindme!|inb4)\b", re.I),
    re.compile(r"\b(?:rewrite it in rust|blazingly fast|it'?s always dns|turning it off and on)\b", re.I),
    re.compile(r"(?:^|\s)/s(?:\s|$|[.!?])", re.I),
)

QUANT_SPEC_RE = re.compile(
    r"(?:\$\d[\d,.]*\s*(?:billion|million|trillion|[BMK])?\b"
    r"|\b\d+(?:\.\d+)?%"
    r"|\b(?:19\d\d|20[0-3]\d)\b"
    r"|\b\d+(?:\.\d+)?\s*(?:ms|us|µs|ns|sec|seconds|mins|minutes|hours|days|years|"
    r"hz|khz|mhz|ghz|kb|mb|gb|tb|pb|kib|mib|gib|nm|mm|km|au|gw|mw|kw|fps|qps|rps|bps|gbps|mbps|x)\b"
    r"|\b\d[\d,]{2,}\s*[a-z]{3,14}\b)",
    flags=re.I,
)


def tokenize(text: str) -> list[str]:
    """Extract lowercase alphanumeric tokens preserving hyphenated domain terms."""
    raw = re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)?", text.lower())
    return [t for t in raw if len(t) >= 2 and not t.isdigit()]


def split_own_vs_quoted(text: str) -> tuple[str, str]:
    """Separate commenter's own prose from `>` quoted lines or `---` pasted blocks."""
    own_lines: list[str] = []
    quote_lines: list[str] = []
    in_excerpt = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "---":
            in_excerpt = not in_excerpt
            continue
        if stripped.startswith(">") or in_excerpt:
            quote_lines.append(stripped.lstrip("> "))
        elif not re.match(r"^\[?\d+\]?:\s*https?://", stripped):
            cleaned = re.sub(r"https?://\S+", "", stripped).strip()
            if cleaned:
                own_lines.append(cleaned)
    return "\n".join(own_lines), "\n".join(quote_lines)


def extract_story_anchors(
    *,
    story_title: str,
    story_url: str,
    article_text: str,
    content_docs: Mapping[int, list[str]],
    rows: Sequence[Mapping[str, Any]],
    doc_freq: Mapping[str, int],
) -> tuple[frozenset[str], list[str]]:
    """Unsupervised TF-IDF + multi-root dispersion story anchor extractor.

    Combines title entities, URL slug tokens, repeated article entities (`tf >= 2`),
    and high-IDF domain terms dispersed across multiple independent root subtrees.
    """
    n_docs = max(1, len(rows))
    all_stop = STOPWORDS | GENERAL_DISCOURSE_STOP

    root_sets: dict[str, set[int]] = {}
    root_term_counts: dict[str, Counter[int]] = {}
    all_roots: set[int] = set()
    for r in rows:
        if r.get("is_dead"):
            continue
        rid = int(r.get("root_id") or r["id"])
        all_roots.add(rid)
        for t in set(content_docs.get(r["id"], ())):
            if t not in all_stop:
                root_sets.setdefault(t, set()).add(rid)
                root_term_counts.setdefault(t, Counter())[rid] += 1

    n_roots = max(1, len(all_roots))
    title_toks = {t for t in tokenize(story_title) if t not in STOPWORDS and t not in GENERAL_DISCOURSE_STOP}
    slug_toks = {
        t
        for t in tokenize(re.sub(r"^https?://", "", story_url))
        if t not in all_stop and len(t) >= 3
    }
    art_toks = [t for t in tokenize(article_text) if t not in all_stop]
    art_tf = Counter(art_toks)

    scores: dict[str, float] = {}
    candidates = set(doc_freq) | title_toks
    min_consensus_roots = max(2, min(6, int(0.025 * n_roots)))

    for t in candidates:
        if t in all_stop or (len(t) < 3 and t not in title_toks):
            continue
        df_c = int(doc_freq.get(t, 0))
        idf = math.log2((n_docs + 1.0) / (df_c + 1.0))
        rdf = len(root_sets.get(t, ()))
        max_root_share = (
            root_term_counts[t].most_common(1)[0][1] / max(1, df_c)
            if t in root_term_counts and df_c > 0
            else 1.0
        )

        sc = 0.0
        if t in title_toks:
            sc += 12.0
        if t in slug_toks and (df_c >= 1 or art_tf[t] >= 1):
            sc += 5.0
        if art_tf[t] >= 2 and rdf >= 2 and idf >= 1.6:
            sc += 1.65 * (1.0 + math.log2(art_tf[t])) * math.log2(1.0 + rdf) * min(2.2, idf / 2.6)
        elif art_tf[t] == 1 and rdf >= max(3, min_consensus_roots) and idf >= 2.2 and max_root_share <= 0.50:
            sc += 1.05 * math.log2(1.0 + rdf) * min(2.2, idf / 2.6)

        if rdf >= min_consensus_roots and 1.8 <= idf <= 7.4 and (n_roots < 6 or max_root_share <= 0.48):
            sc += 1.20 * math.log2(1.0 + rdf) * idf * (1.0 - 0.60 * max_root_share)

        if sc > 0:
            scores[t] = sc

    cap = min(65, max(24, int(14 * math.log2(max(4, n_docs)))))
    ordered = [t for t, _ in sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))[:cap]]
    return frozenset(ordered), ordered


def detect_unsupervised_gags(
    *,
    rows: Sequence[Mapping[str, Any]],
    content_docs: Mapping[int, list[str]],
    comment_bigrams: Mapping[int, list[str]],
    doc_freq: Mapping[str, int],
    bigram_df: Mapping[str, int],
    story_anchors: frozenset[str],
    article_vocab: frozenset[str],
) -> tuple[frozenset[str], frozenset[str]]:
    """Identify thread-specific running-gag unigrams and bigrams concentrated in short unsourced quips."""
    n_docs = len(rows)
    if n_docs < 40:
        return frozenset(), frozenset()

    all_stop = STOPWORDS | GENERAL_DISCOURSE_STOP
    quip_uni_df: Counter[str] = Counter()
    quip_bi_df: Counter[str] = Counter()

    for r in rows:
        if r.get("is_dead"):
            continue
        cid = int(r["id"])
        ctoks = content_docs.get(cid, [])
        own_txt = str(r.get("own_text") or "")
        has_ext_url = any(not u.startswith("item?id=") for u in (r.get("urls") or []))
        is_short_quip = (
            1 <= len(ctoks) <= 18
            and not has_ext_url
            and not QUANT_SPEC_RE.search(own_txt)
            and not r.get("quoted_text")
        )
        if is_short_quip:
            for ut in set(ctoks):
                quip_uni_df[ut] += 1
            for bg in set(comment_bigrams.get(cid, ())):
                quip_bi_df[bg] += 1

    min_uni_df = max(4, int(0.0025 * n_docs))
    gag_unigrams: set[str] = set()
    for term, q_cnt in quip_uni_df.items():
        total_df = int(doc_freq.get(term, 0))
        if (
            total_df < min_uni_df
            or term in story_anchors
            or term in article_vocab
            or term in all_stop
            or len(term) < 4
        ):
            continue
        idf = math.log2((n_docs + 1.0) / (total_df + 1.0))
        if idf >= 5.1 and (q_cnt / total_df) >= 0.70:
            gag_unigrams.add(term)

    min_bi_df = max(3, int(0.0015 * n_docs))
    gag_bigrams: set[str] = set()
    for bg, q_cnt in quip_bi_df.items():
        total_df = int(bigram_df.get(bg, 0))
        if total_df < min_bi_df:
            continue
        parts = bg.split("_", 1)
        if any(p in story_anchors or p in article_vocab or p in all_stop for p in parts):
            continue
        if (q_cnt / total_df) >= 0.65:
            gag_bigrams.add(bg)

    return frozenset(gag_unigrams), frozenset(gag_bigrams)


def compute_subtree_drift_map(
    *,
    rows: Sequence[Mapping[str, Any]],
    by_id: Mapping[int, Mapping[str, Any]],
    children_map: Mapping[int, Sequence[Mapping[str, Any]]],
    tfidf_vecs: Mapping[int, Mapping[str, float]],
    content_docs: Mapping[int, list[str]],
    doc_freq: Mapping[str, int],
    story_anchors: frozenset[str],
    article_vec: Mapping[str, float],
    article_vocab: frozenset[str],
) -> dict[int, int]:
    """Compute unsupervised subtree topic-drift counts per comment.

    Combines vector-space distance from the story's semantic cone across each
    comment's parent/child neighborhood with single-root localized tangent vocabulary.
    """
    n_docs = max(1, len(rows))
    all_stop = STOPWORDS | GENERAL_DISCOURSE_STOP

    # Build normalized story semantic cone vector (article + consensus story anchors)
    cone_raw: dict[str, float] = dict(article_vec)
    for term in story_anchors:
        idf = math.log2((n_docs + 1.0) / (doc_freq.get(term, 0) + 1.0))
        cone_raw[term] = cone_raw.get(term, 0.0) + 0.55 * idf
    cone_norm = math.sqrt(sum(v * v for v in cone_raw.values())) or 1.0
    cone_vec = {k: v / cone_norm for k, v in cone_raw.items()}

    # Identify rare high-IDF terms trapped inside a single root subtree (>= 82% share, df >= 5)
    root_term_counts: dict[str, Counter[int]] = {}
    all_roots: set[int] = set()
    for r in rows:
        if r.get("is_dead"):
            continue
        rid = int(r.get("root_id") or r["id"])
        all_roots.add(rid)
        for t in set(content_docs.get(r["id"], ())):
            if t not in all_stop and t not in story_anchors and t not in article_vocab:
                root_term_counts.setdefault(t, Counter())[rid] += 1

    localized_tangent_terms: set[str] = set()
    if len(all_roots) >= 8 and n_docs >= 80:
        min_df = max(5, int(0.002 * n_docs))
        for t, r_counts in root_term_counts.items():
            total_c = sum(r_counts.values())
            if total_c < min_df:
                continue
            idf = math.log2((n_docs + 1.0) / (total_c + 1.0))
            top_share = r_counts.most_common(1)[0][1] / total_c
            if idf >= 5.2 and top_share >= 0.84:
                localized_tangent_terms.add(t)

    self_cone_sim: dict[int, float] = {}
    for r in rows:
        cid = int(r["id"])
        vec = tfidf_vecs.get(cid, {})
        self_cone_sim[cid] = sum(w * cone_vec.get(t, 0.0) for t, w in vec.items())

    drift_hits: dict[int, int] = {}
    for r in rows:
        cid = int(r["id"])
        ctoks = content_docs.get(cid, [])
        unique_ctoks = set(ctoks)
        anchors = sum(1 for t in unique_ctoks if t in story_anchors)
        own_cone = self_cone_sim[cid]

        # Comments with clear direct story grounding never receive subtree-drift penalties
        if anchors >= 1 or own_cone >= 0.032 or len(ctoks) < 6:
            drift_hits[cid] = 0
            continue

        # Local subtree neighborhood cosine (self + parent + grandparent + direct children)
        neigh_sims = [own_cone]
        par_id = int(r.get("parent_id") or 0)
        if par_id in by_id:
            neigh_sims.append(self_cone_sim.get(par_id, 0.0))
            gp_id = int(by_id[par_id].get("parent_id") or 0)
            if gp_id in by_id:
                neigh_sims.append(self_cone_sim.get(gp_id, 0.0))
        for kid in children_map.get(cid, ())[:5]:
            neigh_sims.append(self_cone_sim.get(int(kid["id"]), 0.0))
        branch_sim = sum(neigh_sims) / len(neigh_sims)

        loc_hits = sum(1 for t in unique_ctoks if t in localized_tangent_terms)
        depth = int(r.get("depth") or 0)

        hits = 0
        if loc_hits >= 1 and branch_sim < 0.028:
            hits += min(2, loc_hits)
        elif depth >= 3 and own_cone < 0.008 and branch_sim < 0.015 and len(ctoks) >= 12:
            hits += 1
        drift_hits[cid] = hits

    return drift_hits


def _clean_facet_terms(centroid: Mapping[str, float], all_stop: frozenset[str], top_n: int = 3) -> list[str]:
    """Pick clean, non-overlapping unigram labels from a cluster centroid."""
    ranked = sorted(centroid.items(), key=lambda kv: (-kv[1], kv[0]))
    chosen: list[str] = []
    for raw_term, _weight in ranked:
        parts = [p for p in raw_term.split("_") if p not in all_stop and len(p) >= 3]
        for cand in parts:
            # Skip plural/prefix near-duplicates of already chosen label words
            if any(
                cand == prev
                or cand.startswith(prev[:4])
                or prev.startswith(cand[:4])
                for prev in chosen
            ):
                continue
            chosen.append(cand)
            if len(chosen) >= top_n:
                return chosen
    return chosen or ["topic"]


def discover_auto_labeled_facets(
    *,
    rows: Sequence[Mapping[str, Any]],
    tfidf_vecs: Mapping[int, Mapping[str, float]],
    doc_freq: Mapping[str, int],
    n_clusters: int = 5,
) -> tuple[dict[int, str], dict[str, str], list[dict[str, Any]]]:
    """Deterministically partition comments into up to 5 auto-labeled TF-IDF topic clusters.

    Uses farthest-first cosine seeding (deterministic spherical k-means++) over substantive
    comments, balanced cosine updates, and `"general_commentary"` fallback for low-signal stubs.

    Returns:
        Tuple of (comment_id -> facet_slug, facet_slug -> human_label, cluster_summaries).
    """
    n_docs = len(rows)
    all_stop = STOPWORDS | GENERAL_DISCOURSE_STOP

    # Build filtered topical vectors (excluding ultra-rare noise & generic words)
    min_df = 2 if n_docs < 80 else max(3, int(0.004 * n_docs))
    max_df = max(min_df + 2, int(0.42 * n_docs))

    topic_vecs: dict[int, dict[str, float]] = {}
    substantive_ids: list[int] = []

    for r in rows:
        cid = int(r["id"])
        raw_v = tfidf_vecs.get(cid, {})
        filt: dict[str, float] = {}
        for term, w in raw_v.items():
            base_terms = term.split("_")
            if any(bt in all_stop for bt in base_terms):
                continue
            if "_" not in term and not (min_df <= doc_freq.get(term, 0) <= max_df):
                continue
            filt[term] = w
        norm = math.sqrt(sum(v * v for v in filt.values()))
        if norm > 0:
            topic_vecs[cid] = {t: v / norm for t, v in filt.items()}
            if not r.get("is_dead") and len(filt) >= 4:
                substantive_ids.append(cid)

    target_k = min(n_clusters, max(1, len(substantive_ids) // 6)) if substantive_ids else 0
    if target_k == 0:
        default_map = {int(r["id"]): "general_commentary" for r in rows}
        return default_map, {"general_commentary": "General Commentary"}, []

    # Deterministic prototype candidates: top 180 substantive comments sorted by lexical richness
    proto_ids = sorted(
        substantive_ids,
        key=lambda cid: (-len(topic_vecs[cid]), cid),
    )[:180]

    # Seed 1: highest mean cosine centrality among prototypes
    best_seed = proto_ids[0]
    best_cent = -1.0
    for cid in proto_ids[:60]:
        v1 = topic_vecs[cid]
        c_sum = sum(
            sum(w * topic_vecs[oid].get(t, 0.0) for t, w in v1.items())
            for oid in proto_ids[:60]
            if oid != cid
        )
        if c_sum > best_cent:
            best_cent = c_sum
            best_seed = cid

    centroids: list[dict[str, float]] = [dict(topic_vecs[best_seed])]

    # Seeds 2..K: deterministic farthest-first cosine diversity
    while len(centroids) < target_k:
        next_cid = proto_ids[0]
        best_dist = -1.0
        for cid in proto_ids:
            vec = topic_vecs[cid]
            max_sim = max(
                sum(w * cent.get(t, 0.0) for t, w in vec.items())
                for cent in centroids
            )
            richness = min(1.25, 0.75 + len(vec) / 36.0)
            score = (1.0 - max_sim) * richness
            if score > best_dist:
                best_dist = score
                next_cid = cid
        centroids.append(dict(topic_vecs[next_cid]))

    # 10 iterations of balanced spherical k-means over substantive comments
    for _it in range(10):
        accum: list[Counter[str]] = [Counter() for _ in range(target_k)]
        counts = [0] * target_k
        for cid in substantive_ids:
            vec = topic_vecs[cid]
            best_j = 0
            best_sc = -1e9
            for j, cent in enumerate(centroids):
                sim = sum(w * cent.get(t, 0.0) for t, w in vec.items())
                # Gentle load-balancing penalty prevents one broad cluster from monopolizing
                bal_pen = 0.035 * (counts[j] / max(1.0, len(substantive_ids) / target_k))
                if sim - bal_pen > best_sc:
                    best_sc = sim - bal_pen
                    best_j = j
            counts[best_j] += 1
            for t, w in vec.items():
                accum[best_j][t] += w

        new_centroids: list[dict[str, float]] = []
        for j in range(target_k):
            if not accum[j]:
                new_centroids.append(centroids[j])
                continue
            top_c = dict(accum[j].most_common(60))
            norm = math.sqrt(sum(v * v for v in top_c.values())) or 1.0
            new_centroids.append({t: v / norm for t, v in top_c.items()})
        centroids = new_centroids

    # Generate unique slugs and clean human-readable labels for the K clusters
    cluster_slugs: list[str] = []
    facet_labels: dict[str, str] = {}
    used_slugs: set[str] = set()
    cluster_top_terms: list[list[str]] = []

    for idx, cent in enumerate(centroids, start=1):
        terms = _clean_facet_terms(cent, all_stop, top_n=4)
        cluster_top_terms.append(terms)
        slug_base = "_".join(re.sub(r"[^a-z0-9]+", "", t) for t in terms[:2] if t) or f"cluster_{idx}"
        slug = slug_base
        suffix = 2
        while slug in used_slugs:
            slug = f"{slug_base}_{suffix}"
            suffix += 1
        used_slugs.add(slug)
        cluster_slugs.append(slug)

        def _fmt_term(word: str) -> str:
            return word.upper() if word in UPPERCASE_ACRONYMS else word.capitalize()

        pretty_parts = [_fmt_term(t) for t in terms[:2]]
        label = " & ".join(pretty_parts)
        if len(terms) >= 3:
            label = f"{label} ({_fmt_term(terms[2])})"
        facet_labels[slug] = label

    facet_labels["general_commentary"] = "General Commentary"

    # Assign all comments (low-similarity or empty vectors fall back to `general_commentary`)
    assignments: dict[int, str] = {}
    cluster_counts: Counter[str] = Counter()
    for r in rows:
        cid = int(r["id"])
        vec = topic_vecs.get(cid)
        if not vec:
            assignments[cid] = "general_commentary"
            cluster_counts["general_commentary"] += 1
            continue
        best_j = 0
        best_sim = 0.0
        for j, cent in enumerate(centroids):
            sim = sum(w * cent.get(t, 0.0) for t, w in vec.items())
            if sim > best_sim:
                best_sim = sim
                best_j = j
        if best_sim >= 0.055:
            slug = cluster_slugs[best_j]
        else:
            slug = "general_commentary"
        assignments[cid] = slug
        cluster_counts[slug] += 1

    summaries: list[dict[str, Any]] = []
    for j, slug in enumerate(cluster_slugs):
        summaries.append(
            {
                "slug": slug,
                "label": facet_labels[slug],
                "count": cluster_counts[slug],
                "top_terms": cluster_top_terms[j],
            }
        )
    return assignments, facet_labels, summaries


def build_corpus_from_inputs(
    *,
    story_id: int,
    html_pages_t2: Sequence[Path | str],
    algolia_data: Mapping[str, Any] | None = None,
    authors_map: Mapping[str, Mapping[str, Any]] | None = None,
    article_text: str = "",
    story_meta: Mapping[str, Any] | None = None,
    html_pages_t1: Sequence[Path | str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Run story-agnostic Stage 1 feature extraction from parsed/ingested story inputs."""
    t2_rows, ref_t2, parsed_meta = parse_live_html_pages(html_pages_t2, story_id=story_id)
    merged_meta = {**parsed_meta, **(dict(story_meta) if story_meta else {})}
    resolved_id = int(story_id or merged_meta.get("story_id") or 0)
    story_title = str(merged_meta.get("story_title") or f"HN Item {resolved_id}")
    story_url = str(merged_meta.get("story_url") or "")

    t1_by_id: dict[int, dict[str, Any]] = {}
    t1_sib_pos: dict[int, tuple[int, int]] = {}
    ref_t1 = ref_t2
    if html_pages_t1:
        t1_rows, ref_t1_parsed, _ = parse_live_html_pages(html_pages_t1, story_id=resolved_id)
        if ref_t1_parsed > 0:
            ref_t1 = ref_t1_parsed
        t1_by_id = {r["id"]: r for r in t1_rows}
        t1_sibs: dict[int, list[int]] = {}
        for r in t1_rows:
            t1_sibs.setdefault(r["parent_id"], []).append(r["id"])
        for cids in t1_sibs.values():
            for idx, cid in enumerate(cids):
                t1_sib_pos[cid] = (idx + 1, len(cids))

    rows = merge_algolia_dead_comments(
        list(t2_rows),
        dict(algolia_data) if algolia_data else {},
        ref_t2,
        story_id=resolved_id,
    )
    if not rows:
        empty_manifest = {
            "version": "2.1.0",
            "story_id": resolved_id,
            "story_title": story_title,
            "story_url": story_url,
            "t1_ref_utc": datetime.fromtimestamp(ref_t1 or 0, tz=UTC).isoformat(),
            "t2_ref_utc": datetime.fromtimestamp(ref_t2 or 0, tz=UTC).isoformat(),
            "delta_minutes": 0.0,
            "story_anchors": [],
            "facet_labels": {"general_commentary": "General Commentary"},
            "facet_clusters": [],
            "counts": {
                "total_comments": 0,
                "live_t2_comments": 0,
                "algolia_dead_comments": 0,
                "downvoted_faded_t2": 0,
                "unique_authors_profiled": 0,
                "mod_rebuked_comments": 0,
                "near_duplicates_gt_065": 0,
                "pages_fetched": int(merged_meta.get("pages_fetched") or len(html_pages_t2)),
            },
        }
        return [], empty_manifest

    by_id = {r["id"]: r for r in rows}
    authors = authors_map or {}

    # Detect HN moderator guideline rebukes (`dang` / `tomhow`)
    mod_rebuked_ids: set[int] = set()
    mod_note_ids: set[int] = set()
    for r in rows:
        if r["author"] in HN_MODERATORS and any("newsguidelines" in u for u in r["urls"]):
            mod_note_ids.add(r["id"])
            if r["parent_id"] in by_id:
                mod_rebuked_ids.add(r["parent_id"])

    # Crowd language model (smoothed unigram + bigram) & document frequencies
    unigram_counts: Counter[str] = Counter()
    bigram_counts: Counter[tuple[str, str]] = Counter()
    doc_freq: Counter[str] = Counter()
    tokenized_docs: dict[int, list[str]] = {}
    content_docs: dict[int, list[str]] = {}

    for r in rows:
        own_txt, quoted_txt = split_own_vs_quoted(r["text"])
        r["own_text"] = own_txt
        r["quoted_text"] = quoted_txt
        toks = tokenize(own_txt)
        ctoks = [t for t in toks if t not in STOPWORDS]
        tokenized_docs[r["id"]] = toks
        content_docs[r["id"]] = ctoks

        unigram_counts.update(toks)
        for i in range(len(toks) - 1):
            bigram_counts[(toks[i], toks[i + 1])] += 1
        for ut in set(ctoks):
            doc_freq[ut] += 1

    n_docs = len(rows)
    total_unigrams = max(1, sum(unigram_counts.values()))
    vocab_size = max(1, len(unigram_counts))

    # Story article TF-IDF reference vector (falls back cleanly to title + toptext)
    effective_article = f"{story_title}\n\n{article_text}".strip()
    art_tokens = [t for t in tokenize(effective_article) if t not in STOPWORDS]
    art_vocab = frozenset(art_tokens)
    art_tf = Counter(art_tokens)
    art_vec: dict[str, float] = {}
    for term, cnt in art_tf.items():
        idf = math.log2((n_docs + 1.0) / (doc_freq.get(term, 0) + 1.0)) + 1.0
        art_vec[term] = (1.0 + math.log2(cnt)) * idf
    art_norm = math.sqrt(sum(v * v for v in art_vec.values())) or 1.0
    art_vec = {k: v / art_norm for k, v in art_vec.items()}

    # L2-normalized comment TF-IDF vectors (unigrams + informative bigrams)
    bigram_df: Counter[str] = Counter()
    comment_bigrams: dict[int, list[str]] = {}
    for cid, ctoks in content_docs.items():
        bgs = [f"{ctoks[i]}_{ctoks[i + 1]}" for i in range(len(ctoks) - 1)]
        comment_bigrams[cid] = bgs
        for bg in set(bgs):
            bigram_df[bg] += 1

    tfidf_vecs: dict[int, dict[str, float]] = {}
    for r in rows:
        cid = r["id"]
        ctoks = content_docs[cid]
        bgs = [bg for bg in comment_bigrams[cid] if bigram_df[bg] >= 2]
        tf = Counter(ctoks)
        vec: dict[str, float] = {}
        for term, cnt in tf.items():
            idf = math.log2((n_docs + 1.0) / (doc_freq[term] + 1.0))
            if idf > 0.4:
                vec[term] = (1.0 + math.log2(cnt)) * idf
        for bg, cnt in Counter(bgs).items():
            idf = math.log2((n_docs + 1.0) / (bigram_df[bg] + 1.0))
            vec[bg] = 0.65 * (1.0 + math.log2(cnt)) * idf
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        tfidf_vecs[cid] = {k: v / norm for k, v in vec.items()}

    # Unsupervised story anchors, running gags, subtree drift, and 5-cluster facets
    story_anchors, ordered_anchors = extract_story_anchors(
        story_title=story_title,
        story_url=story_url,
        article_text=article_text,
        content_docs=content_docs,
        rows=rows,
        doc_freq=doc_freq,
    )
    gag_unigrams, gag_bigrams = detect_unsupervised_gags(
        rows=rows,
        content_docs=content_docs,
        comment_bigrams=comment_bigrams,
        doc_freq=doc_freq,
        bigram_df=bigram_df,
        story_anchors=story_anchors,
        article_vocab=art_vocab,
    )

    sibs_t2: dict[int, list[dict[str, Any]]] = {}
    children_map: dict[int, list[dict[str, Any]]] = {}
    for r in rows:
        if not r["is_dead"]:
            sibs_t2.setdefault(r["parent_id"], []).append(r)
            children_map.setdefault(r["parent_id"], []).append(r)

    drift_map = compute_subtree_drift_map(
        rows=rows,
        by_id=by_id,
        children_map=children_map,
        tfidf_vecs=tfidf_vecs,
        content_docs=content_docs,
        doc_freq=doc_freq,
        story_anchors=story_anchors,
        article_vec=art_vec,
        article_vocab=art_vocab,
    )
    facet_map, facet_labels, facet_summaries = discover_auto_labeled_facets(
        rows=rows,
        tfidf_vecs=tfidf_vecs,
        doc_freq=doc_freq,
        n_clusters=5,
    )

    # Inverted index for fast pairwise cosine similarity (crowd redundancy + copy-paste duplicates)
    max_df_cap = max(25, int(0.18 * n_docs))
    inv_idx: dict[str, list[tuple[int, float]]] = {}
    for cid, vec in tfidf_vecs.items():
        top_terms = sorted(vec.items(), key=lambda kv: kv[1], reverse=True)[:20]
        for term, weight in top_terms:
            if doc_freq.get(term, 2) <= max_df_cap:
                inv_idx.setdefault(term, []).append((cid, weight))

    max_older_sim: dict[int, tuple[float, int | None]] = {}
    crowd_density: dict[int, float] = {}
    for r in rows:
        cid = r["id"]
        vec = tfidf_vecs[cid]
        scores: Counter[int] = Counter()
        for term, w in vec.items():
            for other_id, ow in inv_idx.get(term, ()):
                if other_id != cid:
                    scores[other_id] += w * ow
        older_best = 0.0
        older_id: int | None = None
        neighbors_above_028 = 0
        for oid, sim in scores.items():
            if sim >= 0.28:
                neighbors_above_028 += 1
            if oid < cid and sim > older_best:
                older_best = sim
                older_id = oid
        max_older_sim[cid] = (round(min(1.0, older_best), 4), older_id)
        crowd_density[cid] = round(neighbors_above_028 / max(1.0, n_docs / 100.0), 4)

    author_post_counts = Counter(r["author"] for r in rows if not r["author"].startswith("["))

    for r in rows:
        age_h = max(0.05, (ref_t2 - r["unix_ts"]) / 3600.0) if r["unix_ts"] and ref_t2 else 6.0
        r["age_hours"] = round(age_h, 3)
        r["gravity_denom"] = round((age_h + 2.0) ** 1.8, 4)

        au = authors.get(r["author"]) or {}
        karma = int(au.get("karma", 0))
        sub_cnt = max(1, int(au.get("submitted_count", 1)))
        created_ts = float(au.get("created", 0))
        acct_age_days = max(0.1, (ref_t2 - created_ts) / 86400.0) if created_ts and ref_t2 else 365.0
        kpp = karma / sub_cnt

        r["author_karma"] = karma
        r["author_submitted"] = sub_cnt
        r["author_age_days"] = round(acct_age_days, 1)
        r["author_kpp"] = round(kpp, 3)
        r["is_throwaway"] = bool(au) and (acct_age_days < 14.0 or (karma <= 5 and sub_cnt <= 8))

    # Inverse news.arc sibling ordering physics
    for sibs in sibs_t2.values():
        n_sibs = len(sibs)
        min_rank_below = 0.0
        youngest_clean_denom: float | None = None
        for idx in range(n_sibs - 1, -1, -1):
            s = sibs[idx]
            s["sibling_rank"] = idx + 1
            s["sibling_count"] = n_sibs
            if s["downvote_tier"] > 0:
                s["implied_extra_votes"] = -float(s["downvote_tier"])
                s["surf_mirage_index"] = 0.0
                continue

            implied_rank = min_rank_below
            if youngest_clean_denom is not None and s["gravity_denom"] > youngest_clean_denom * 1.15:
                floor_r = 0.42 / youngest_clean_denom
                if floor_r > implied_rank:
                    implied_rank = floor_r

            est_hn_author_mult = 1.0 + min(0.45, max(0.0, math.log1p(max(0.0, s["author_kpp"] - 2.0)) * 0.14))
            raw_base = ((implied_rank * s["gravity_denom"]) / est_hn_author_mult) ** 1.25 if implied_rank > 0 else 0.0
            s["implied_extra_votes"] = round(raw_base, 2)

            own_min = max(raw_base, 0.35 if idx < n_sibs - 1 else 0.0)
            cand_r = (own_min**0.8) * est_hn_author_mult / s["gravity_denom"] if own_min > 0 else 0.0
            if cand_r > min_rank_below:
                min_rank_below = cand_r
            if youngest_clean_denom is None or s["gravity_denom"] < youngest_clean_denom:
                youngest_clean_denom = s["gravity_denom"]

        for idx, s in enumerate(sibs):
            if s["downvote_tier"] > 0:
                continue
            older_below = [
                b for b in sibs[idx + 1 : idx + 8] if b["downvote_tier"] == 0 and b["age_hours"] > s["age_hours"] + 4.0
            ]
            if older_below and s["age_hours"] < 3.2:
                s["surf_mirage_index"] = round(
                    max(b["gravity_denom"] / s["gravity_denom"] for b in older_below), 2
                )
            else:
                s["surf_mirage_index"] = 0.0

    # Assemble per-comment epistemic, information-theoretic, temporal & progeny features
    for r in rows:
        cid = r["id"]
        if r["is_dead"]:
            r["sibling_rank"] = None
            r["sibling_count"] = None
            r["implied_extra_votes"] = -9.0
            r["surf_mirage_index"] = 0.0

        r1 = t1_by_id.get(cid)
        if r1 is not None:
            r["in_t1"] = True
            r["dom_rank_t1"] = r1["live_dom_rank"]
            r["newly_downvoted"] = r["downvote_tier"] > r1["downvote_tier"]
            pos1, cnt1 = t1_sib_pos.get(cid, (1, 1))
            pos2 = r["sibling_rank"] or cnt1
            cnt2 = r["sibling_count"] or cnt1
            pct1 = 1.0 - (pos1 - 1) / max(1, cnt1)
            pct2 = 1.0 - (pos2 - 1) / max(1, cnt2)
            r["temporal_pct_delta"] = round(pct2 - pct1, 4)
        else:
            r["in_t1"] = False
            r["dom_rank_t1"] = None
            r["newly_downvoted"] = False
            r["temporal_pct_delta"] = 0.0

        toks = tokenized_docs[cid]
        ctoks = content_docs[cid]
        own_txt = r["own_text"]
        quoted_txt = r["quoted_text"]
        own_words = len(toks)
        quoted_words = len(tokenize(quoted_txt))

        if toks:
            surprisals: list[float] = []
            for i, w in enumerate(toks):
                p_uni = (unigram_counts[w] + 0.5) / (total_unigrams + 0.5 * vocab_size)
                if i > 0:
                    prev = toks[i - 1]
                    p_bi = bigram_counts[(prev, w)] / max(1, unigram_counts[prev])
                    p = 0.65 * p_bi + 0.35 * p_uni
                else:
                    p = p_uni
                surprisals.append(-math.log2(max(1e-9, p)))
            crowd_surprisal = sum(surprisals) / len(surprisals)
        else:
            crowd_surprisal = 0.0

        unique_ctoks = set(ctoks)
        idfs = [math.log2((n_docs + 1.0) / (doc_freq[t] + 1.0)) for t in unique_ctoks]
        high_idf_thresh = min(4.2, max(2.2, math.log2(max(8.0, n_docs / 16.0))))
        high_idf_cnt = sum(1 for v in idfs if v >= high_idf_thresh)
        mean_idf = (sum(idfs) / len(idfs)) if idfs else 0.0
        specific_info_bits = mean_idf * math.log2(1.0 + high_idf_cnt)
        content_ratio = len(ctoks) / max(1, own_words)

        vec = tfidf_vecs[cid]
        art_cos = sum(w * art_vec.get(t, 0.0) for t, w in vec.items())
        anchor_hits = sum(1 for t in unique_ctoks if t in story_anchors)
        off_topic_hits = drift_map.get(cid, 0)

        url_info = classify_urls_detailed(r["urls"])
        url_tier = int(url_info["url_tier"])
        primary_urls = int(url_info["primary_url_count"])
        low_urls = int(url_info["low_cred_url_count"])
        url_domains = list(url_info["url_domains"])
        url_categories = list(url_info["url_categories"])

        quants = QUANT_SPEC_RE.findall(own_txt)
        popper_hits = sum(1 for p in POPPER_EVIDENCE_PATTERNS if p.search(own_txt))
        calibrated_hits = sum(1 for p in CALIBRATED_MODALITY_PATTERNS if p.search(own_txt))
        conspiracy_hits = sum(1 for p in FRANKFURT_CONSPIRACY_PATTERNS if p.search(own_txt))
        swipe_hits = sum(1 for p in TRIBAL_SWIPE_PATTERNS if p.search(r["text"]))

        template_memes = sum(1 for p in UNIVERSAL_MEME_PATTERNS if p.search(r["text"]))
        gag_hits = 0
        if own_words < 55 and url_tier < 2:
            gag_hits = sum(1 for bg in set(comment_bigrams[cid]) if bg in gag_bigrams)
            if gag_hits == 0 and own_words < 38:
                gag_hits = sum(1 for t in unique_ctoks if t in gag_unigrams)
        meme_hits = template_memes + min(2, gag_hits)

        chain_authors = [r["author"]]
        cur = r
        anc_downvoted = False
        while cur["parent_id"] in by_id and len(chain_authors) < 10:
            par = by_id[cur["parent_id"]]
            if par["downvote_tier"] > 0 or par["is_dead"]:
                anc_downvoted = True
            chain_authors.append(par["author"])
            cur = par

        ping_pong = 0
        if len(chain_authors) >= 3 and chain_authors[0] == chain_authors[2] and chain_authors[0] != chain_authors[1]:
            a0, a1 = chain_authors[0], chain_authors[1]
            for k, auth in enumerate(chain_authors):
                if auth == (a0 if k % 2 == 0 else a1):
                    ping_pong += 1
                else:
                    break

        direct_kids = children_map.get(cid, [])
        clean_kid_authors = {
            k["author"]
            for k in direct_kids
            if k["downvote_tier"] == 0 and len(tokenize(k.get("own_text") or k["text"])) >= 25
        }
        faded_kids = sum(1 for k in direct_kids if k["downvote_tier"] >= 2)

        dup_sim, dup_id = max_older_sim[cid]
        top_tfidf = sorted(vec.items(), key=lambda kv: kv[1], reverse=True)[:18]
        facet = facet_map.get(cid, "general_commentary")

        r.update(
            {
                "own_word_count": own_words,
                "quoted_word_count": quoted_words,
                "paragraph_count": len([p for p in own_txt.split("\n\n") if p.strip()]),
                "content_token_ratio": round(content_ratio, 4),
                "crowd_surprisal_bits": round(crowd_surprisal, 4),
                "mean_idf_bits": round(mean_idf, 4),
                "high_idf_term_count": high_idf_cnt,
                "specific_info_bits": round(specific_info_bits, 4),
                "article_tfidf_cos": round(art_cos, 4),
                "core_anchor_hits": anchor_hits,
                "off_topic_hits": off_topic_hits,
                "max_older_dup_cos": dup_sim,
                "dup_of_id": dup_id,
                "crowd_cluster_density": crowd_density[cid],
                "url_tier": url_tier,
                "primary_url_count": primary_urls,
                "low_cred_url_count": low_urls,
                "url_domains": url_domains,
                "url_categories": url_categories,
                "quant_count": len(quants),
                "popper_hits": popper_hits,
                "calibrated_hits": calibrated_hits,
                "conspiracy_hits": conspiracy_hits,
                "swipe_hits": swipe_hits,
                "meme_hits": meme_hits,
                "ping_pong_depth": ping_pong,
                "author_thread_posts": author_post_counts.get(r["author"], 1),
                "ancestor_downvoted": anc_downvoted,
                "constructive_reply_authors": len(clean_kid_authors),
                "faded_reply_count": faded_kids,
                "is_mod_rebuked": cid in mod_rebuked_ids,
                "is_mod_note": cid in mod_note_ids,
                "facet": facet,
                "tfidf_top": [[t, round(w, 4)] for t, w in top_tfidf],
            }
        )

    manifest = {
        "version": "2.1.0",
        "story_id": resolved_id,
        "story_title": story_title,
        "story_url": story_url,
        "points": int(merged_meta.get("points") or 0),
        "story_author": str(merged_meta.get("story_author") or ""),
        "article_source": str(merged_meta.get("article_source") or "unknown"),
        "t1_ref_utc": datetime.fromtimestamp(ref_t1 or 0, tz=UTC).isoformat(),
        "t2_ref_utc": datetime.fromtimestamp(ref_t2 or 0, tz=UTC).isoformat(),
        "delta_minutes": round(max(0.0, (ref_t2 - ref_t1) / 60.0), 2) if html_pages_t1 else 0.0,
        "story_anchors": ordered_anchors[:25],
        "facet_labels": facet_labels,
        "facet_clusters": facet_summaries,
        "counts": {
            "total_comments": len(rows),
            "live_t2_comments": len(t2_rows),
            "algolia_dead_comments": sum(1 for r in rows if r["is_dead"]),
            "downvoted_faded_t2": sum(1 for r in rows if 0 < r["downvote_tier"] < 9),
            "unique_authors_profiled": len(authors),
            "mod_rebuked_comments": len(mod_rebuked_ids),
            "near_duplicates_gt_065": sum(1 for r in rows if r["max_older_dup_cos"] >= 0.65),
            "pages_fetched": int(merged_meta.get("pages_fetched") or len(html_pages_t2)),
        },
    }
    return rows, manifest


def build_story_corpus(
    target: str | int,
    *,
    data_dir: Path = DATA_DIR,
    offline: bool = False,
    refresh: bool = False,
    max_pages: int = 25,
    write_output: bool = True,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Ingest `target` (ID or URL) and compute its generalized scientific corpus.

    Writes artifacts to `data_dir/items/<story_id>/corpus.json` and `manifest.json`,
    preserving the read-only benchmark `data_dir/corpus_v2.json` untouched.
    """
    ingested = ingest_story(
        target,
        data_dir=data_dir,
        offline=offline,
        refresh=refresh,
        max_pages=max_pages,
    )
    story_id = int(ingested["story_id"])
    rows, manifest = build_corpus_from_inputs(
        story_id=story_id,
        html_pages_t2=ingested["html_pages_t2"],
        algolia_data=ingested["algolia"],
        authors_map=ingested["authors"],
        article_text=ingested["article_text"],
        story_meta={
            **ingested["story_meta"],
            "article_source": ingested["article_source"],
        },
        html_pages_t1=ingested["html_pages_t1"] or None,
    )

    if write_output:
        out_dir = data_dir / "items" / str(story_id)
        out_dir.mkdir(parents=True, exist_ok=True)
        corpus_path = out_dir / "corpus.json"
        manifest_path = out_dir / "manifest.json"
        corpus_bytes = json.dumps(rows, ensure_ascii=False).encode("utf-8")
        corpus_path.write_bytes(corpus_bytes)
        manifest["sha256"] = {
            "corpus.json": hashlib.sha256(corpus_bytes).hexdigest(),
        }
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    return rows, manifest


def build_scientific_corpus() -> dict[str, Any]:
    """Run generalized feature extraction on local 50467087 snapshots without mutating `corpus_v2.json`."""
    _rows, manifest = build_story_corpus(50467087, data_dir=DATA_DIR, offline=True, write_output=True)
    return manifest


__all__ = [
    "DATA_DIR",
    "STOPWORDS",
    "build_corpus_from_inputs",
    "build_scientific_corpus",
    "build_story_corpus",
    "classify_urls",
    "discover_auto_labeled_facets",
    "extract_story_anchors",
    "split_own_vs_quoted",
    "tokenize",
]


if __name__ == "__main__":
    m = build_scientific_corpus()
    print(json.dumps(m, indent=2))
