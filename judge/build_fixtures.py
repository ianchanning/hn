"""Generate verified Popper/Frankfurt epistemic benchmark fixtures (v1.0) outside worker scope."""

import json
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent
CORPUS_PATH = OUT_DIR.parent / "data" / "corpus_v2.json"
DEV_PUBLIC_PATH = OUT_DIR.parent / "benchmark" / "dev_sample.json"

# Every single ID below was inspected directly from corpus_v2.json (story 50467087).
# Grades:
#   3 = Epistemic Gold: Falsifiable primary source, quantitative/institutional mechanism, or deep insider synthesis
#   2 = Grounded Constructive Analysis: Coherent multi-step reasoning grounded in real incentives/precedents
#   1 = Predictable Crowd Chatter: Surface opinion, low marginal information, or repetitive take
#   0 = Bullshit / Meme / Tribal Swipe / Unfalsifiable Conspiracy / Off-topic / Bare Link-drop / Mod-rebuked
GRADED_ITEMS: list[tuple[int, int, str, str]] = [
    # --- GRADE 3: EPISTEMIC GOLD (28 items, split 14 dev / 14 holdout) ---
    (50472726, 3, "dev", "Reuters primary quote: 600,000 Nvidia chips held in HK awaiting Chinese import approval, refuting export-demand premise"),
    (50476624, 3, "holdout", "Cites page 7 of Nvidia External Code of Conduct PDF on actual/potential conflict of interest"),
    (50477795, 3, "dev", "Links May 2026 40-page Culper Research PDF documenting Megaspeed, shell companies & Alice Huang 6 months prior"),
    (50478347, 3, "holdout", "INSEAD case study precedent on HP CEO Mark Hurd fiduciary resignation over $20k relationship expense"),
    (50476287, 3, "dev", "CNN/ODNI reporting: officials close to Jay Clayton saw no evidence Alice Huang is a spy"),
    (50468029, 3, "holdout", "Direct SEC EDGAR DEF-14A / 8-K shareholder board election filing (nvda-20260512.htm)"),
    (50470235, 3, "dev", "US Supreme Court caselaw (13-354) refuting myth that corporate law mandates short-term profit maximization"),
    (50471890, 3, "holdout", "Politico House Intel Ranking Member Jim Himes briefing rebuttal (faded c5A by tribal downvotes)"),
    (50468194, 3, "dev", "Sourced timeline contrasting Huang's Nov 9 Fortune quote ('completely normal') with board probe & subordinate affairs"),
    (50469819, 3, "holdout", "Quantitative M&A breakdown: 18% of Nvidia revenue stems from 2020 Mellanox interconnect acquisition"),
    (50471550, 3, "dev", "346-word legal/regulatory analysis of parallel DOJ & Commerce BIS oversight over Nvidia-Megaspeed"),
    (50475531, 3, "holdout", "Archived NYT primary text excerpt detailing Huang Le / Alice Huang & Singapore datacenter entity"),
    (50467655, 3, "dev", "Direct link & excerpt of Huang's internal farewell apology memo on nvidianews.nvidia.com refuting false claim"),
    (50477419, 3, "holdout", "June 2026 TOP500 supercomputer data analyzing AMD GPU competitiveness outside CUDA IP moat"),
    (50467629, 3, "dev", "Axios + Business Insider synthesis linking loss of Trump/Lutnick political cover to export-control exposure"),
    (50470940, 3, "holdout", "Reuters + FT custom-crackdown citations showing Beijing actively blocking Nvidia GPU imports (faded c5A)"),
    (50472433, 3, "dev", "Popperian source audit showing referenced article covers software platform only, never hardware or 'Watchdog'"),
    (50471360, 3, "holdout", "321-word chronological dissection of board backing Sunday vs Wednesday subordinate-affair disclosures"),
    (50476126, 3, "dev", "Historical CUDA 2004 strategic bet & 20-year timeline refuting 'right place right time' luck narrative"),
    (50467951, 3, "holdout", "Bloomberg Sept 2025 citation documenting Chinese regulator order halting Nvidia AI chip purchases"),
    (50472115, 3, "dev", "NYT + Reuters citations distinguishing US-approved revenue-shared chip sales from illegal smuggling"),
    (50476734, 3, "holdout", "NYT corporate-law analysis clarifying fiduciary duty vs shareholder-value maximization myth"),
    (50473169, 3, "dev", "Axios + archive citation on Bessent vs Lutnick enforcement split regarding Megaspeed"),
    (50468469, 3, "holdout", "Historical NYT precedent on 'unwitting asset' intelligence framing paired with Himes briefing"),
    (50470097, 3, "dev", "Specific compliance timeline: Megaspeed absent from BIS Entity List yet Nvidia halted shipments June 2025"),
    (50468826, 3, "holdout", "CNBC May 2026 primary report on US clearing H200 sales to 10 Chinese firms inside deep debate thread"),
    (50467440, 3, "dev", "CNBC Nov 8 Nvidia board & Huang statement refuting open-marriage speculation with primary quote"),
    (50476314, 3, "holdout", "Export-compliance practitioner explanation of physical end-user verification teams in restricted hardware"),

    # --- GRADE 2: GROUNDED CONSTRUCTIVE ANALYSIS (26 items, split 13 dev / 13 holdout) ---
    (50474166, 2, "dev", "Coherent executive-governance analysis of CEO perception risk and board liability"),
    (50468428, 2, "holdout", "183-word strategic analysis of Nvidia core business resilience vs founder strategic execution"),
    (50473155, 2, "dev", "Structured 3-premise decomposition of Megaspeed/sanctions/affair inference chain"),
    (50476201, 2, "holdout", "Clear taxonomy of the two disjoint coalitions lobbying to restrict open-weight models"),
    (50475192, 2, "dev", "Counterfactual fab wafer allocation & accelerator ecosystem analysis if Nvidia stumbled"),
    (50469961, 2, "holdout", "Concise corporate-governance explanation of why subordinate affair triggers mandatory board ouster"),
    (50468644, 2, "dev", "Historical Apple 1985-1996 post-Jobs succession comparison with explicit caveats"),
    (50472133, 2, "holdout", "Industrial-policy analysis contrasting market crowd-out vs Chinese state semiconductor subsidies"),
    (50467764, 2, "dev", "Dual-class voting control comparison (Meta/Zuckerberg vs Nvidia single-class shareholder structure)"),
    (50473538, 2, "holdout", "Incentive analysis distinguishing Chinese private firm GPU demand vs Beijing indigenous-chip mandate"),
    (50467833, 2, "dev", "Balanced evaluation of Jensen's multi-decade CUDA investment discipline vs personal misconduct"),
    (50474654, 2, "holdout", "Org-design analysis of Jensen's 50+ direct-report flat management structure and succession vacuum"),
    (50469053, 2, "dev", "Financial distinction between secondary market cap valuation and 50%+ gross margin cash generation"),
    (50473388, 2, "holdout", "Quantitative sanity check questioning $7.5B Megaspeed chip volume vs Singapore entity scale"),
    (50467672, 2, "dev", "Employee equity wealth distribution analysis comparing Nvidia broad RSU grants vs peer tech giants"),
    (50476038, 2, "holdout", "Technical feasibility critique of hardware-level unsigned open-weight inference blocking"),
    (50468685, 2, "dev", "Game-theoretic refutation of 'affair isn't blackmail material' claim"),
    (50474036, 2, "holdout", "Counterintelligence timeline analysis of why serious espionage probes don't leak piecemeal"),
    (50473303, 2, "dev", "Policy taxonomy contrasting State Dept Model Hawks vs Hardware Hawks"),
    (50468873, 2, "holdout", "Nuanced counter-history on Tegra mobile pivots vs datacenter pivot"),
    (50476717, 2, "dev", "Concrete 2026 shareholder governance example (Warner Bros Zaslav pay vote)"),
    (50468180, 2, "holdout", "Cloud-rental loophole mechanics via Malaysian datacenters outside physical China"),
    (50474171, 2, "dev", "Founder vs professional caretaker CEO risk-appetite comparison in long-horizon R&D"),
    (50469420, 2, "holdout", "Institutional execution argument comparing Nvidia engineering output vs AMD/Intel/TI alumni"),
    (50467344, 2, "dev", "Focused technical concern over GPU firmware attestation / unsigned open-model inference"),
    (50477457, 2, "holdout", "Due-process critique examining anonymous intelligence leaks prior to formal charges"),

    # --- GRADE 1: LOW-DENSITY CHATTER / PREDICTABLE CROWD TAKES / SURF-RIDERS (22 items, 11 dev / 11 holdout) ---
    (50477887, 1, "dev", "2h surf-rider root comment claiming resignation is mainly a loss for the gaming community"),
    (50469848, 1, "holdout", "18-word unsubstantiated assertion: 'The board is making a major mistake...'"),
    (50469658, 1, "dev", "Single-sentence restatement that Jensen is also off the board"),
    (50467245, 1, "holdout", "Short speculative leap that resignation 'confirms' illegal GPU knowledge"),
    (50478097, 1, "dev", "Low-densitysurf reply about internet attention spans"),
    (50477383, 1, "holdout", "19-word casual quip about buying Chinese GPUs"),
    (50478678, 1, "dev", "Short generic HR question about morality clauses"),
    (50473851, 1, "holdout", "192-word zero-specificity hedging soup ('things certainly have not been improving in those respects...')"),
    (50472710, 1, "dev", "Generic populist rant that random HN commenters could run Nvidia just as well"),
    (50468255, 1, "holdout", "One-line succession rumor question ('So Johnny Siruji new CEO when?')"),
    (50472076, 1, "dev", "Self-promo stub linking own short blog post ('should have fought for AGI')"),
    (50475165, 1, "holdout", "Short 'Food for thought... Why now?' vague speculation"),
    (50476536, 1, "dev", "Redundant late link-repeat of the 3rd affair story already posted 5 times"),
    (50475317, 1, "holdout", "One-word 'Yes:' link repeat"),
    (50477498, 1, "dev", "Bare link-wrapper to X post without analysis"),
    (50478145, 1, "holdout", "Casual 'My fps or flops don't care about the CEO' take"),
    (50468055, 1, "dev", "Tangential remark about estate taxes"),
    (50472894, 1, "holdout", "Walk-back comment admitting 'treasonous' label was purely subjective"),
    (50477022, 1, "dev", "Emotional 'Furious investor here. Lol' retail vent"),
    (50470425, 1, "holdout", "Exact self-plagiarized copy-paste duplicate of author's earlier comment 50469592"),
    (50472107, 1, "dev", "Near-duplicate repetition of parent's 'two ants in kitchen' analogy"),
    (50478775, 1, "holdout", "Fresh 8-minute surf-rider casual speculation"),

    # --- GRADE 0: BULLSHIT / MEMES / SWIPES / CONSPIRACY / OFF-TOPIC / BARE LINKS / MOD-REBUKED (36 items, 18 dev / 18 holdout) ---
    (50477314, 0, "dev", "HN DOM #1 surf-rider: unsourced 'members of government knew for years / why now' conspiracy"),
    (50471074, 0, "holdout", "Profane tribal rant ('Stop with the gaslighting. He fucked a communist spy')"),
    (50477258, 0, "dev", "189-word unhinged rant ('fabricated reality... fucked up societies and psychopath politicians')"),
    (50478785, 0, "holdout", "6-minute surf-rider ('reading social media, hard to believe there isn't a plot')"),
    (50467793, 0, "dev", "Pure joke + YouTube link ('And a gift card for Spatula City!')"),
    (50467506, 0, "holdout", "98k-karma leather-jacket Sotheby's shoe-selling joke with CNBC link"),
    (50477883, 0, "dev", "GTC visitor badge one-liner joke with nvidia.com URL"),
    (50474795, 0, "holdout", "'A second employee affair has hit the CEO' meme with Reuters URL"),
    (50478591, 0, "dev", "'You don't table Tom Brady in the last quarter' sports bro one-liner"),
    (50475021, 0, "holdout", "'The leather jacket was a giant red flag... sexy man' snark"),
    (50468400, 0, "dev", "Movie cliché one-liner ('smoking a cigar... plan comes together')"),
    (50467926, 0, "holdout", "r/ShittySysadmin joke link"),
    (50478216, 0, "dev", "Unverified Reddit layoff rumor + 'Nvidia is a stagnating company'"),
    (50478659, 0, "holdout", "Includes literal lmgtfy google.com/search?q=ccp+in+the+united+states URL"),
    (50473977, 0, "dev", "Off-topic home-gardening cockroach article link"),
    (50469126, 0, "holdout", "Off-topic Wiktionary etymology of 'Woźniak'"),
    (50473655, 0, "dev", "Off-topic Zelensky / Boris Johnson / Chomsky YouTube tangent"),
    (50473752, 0, "holdout", "Off-topic Jeffrey Epstein / Bill Gates tangent"),
    (50472966, 0, "dev", "Off-topic Epstein files press release tangent"),
    (50469992, 0, "holdout", "Off-topic Grok deepfake Wikipedia tangent"),
    (50475277, 0, "dev", "Zero-word bare archive.is URL drop"),
    (50473185, 0, "holdout", "Zero-word bare x.com URL drop"),
    (50467438, 0, "dev", "Zero-word bare jobs.nvidia.com joke URL drop"),
    (50468049, 0, "holdout", "Zero-word bare Wikipedia Scope_neglect URL drop"),
    (50474875, 0, "dev", "claude.ai sentiment-cloud spam artifact (faded c5A)"),
    (50472264, 0, "holdout", "Deeply downvoted (cBE) polyamory tangent ignoring fiduciary conflict"),
    (50472068, 0, "dev", "Downvoted (c73) 85k-karma 'Chinese or CIA friendly puppet' conspiracy"),
    (50468569, 0, "holdout", "Downvoted (c88) 'epic reading comprehension fail' tribal swipe"),
    (50474955, 0, "dev", "Downvoted (c88) bare headline drop on Taiwan"),
    (50471418, 0, "holdout", "Moderator-rebuked by @dang (50471709) for 'Bruh / swipes' (faded c73)"),
    (50469868, 0, "dev", "Moderator-rebuked by @tomhow (50477158) for Musk flamebait"),
    (50470168, 0, "holdout", "Moderator-rebuked by @tomhow (50477194) for dogmatic ideological tangent (faded c73)"),
    (50477099, 0, "dev", "2-word exact duplicate 'Three now!'"),
    (50473609, 0, "holdout", "1-word 'lol' noise"),
    (50478061, 0, "dev", "Condescending swipe ('You should probably do some research') + YouTube link"),
    (50475170, 0, "holdout", "7-hour-old 1-karma throwaway dramatic rant + YouTube link"),
]

# Explicit Adversarial Anti-Goodhart Trap Pairs: (winner_id, loser_id, trap_category, split)
ADVERSARIAL_PAIRS: list[tuple[int, int, str, str]] = [
    # Trap 1: Prestige URL / High-Karma Joke vs True Sourced Analysis
    (50472726, 50467506, "karma_url_joke_vs_evidence", "holdout"),
    (50468029, 50474795, "meme_reuters_vs_sec_filing", "holdout"),
    (50476624, 50477883, "nvidia_joke_url_vs_nvidia_conduct_pdf", "dev"),
    (50477795, 50467793, "low_karma_pdf_vs_high_karma_youtube_joke", "dev"),
    # Trap 2: Confident Conspiracy / Tribal Bullshit vs Calibrated Rebuttal
    (50471890, 50471074, "c5a_himes_rebuttal_vs_c00_profane_rant", "holdout"),
    (50476287, 50477314, "odni_citation_at_2481_vs_hn_top1_conspiracy", "dev"),
    (50470940, 50472068, "c5a_reuters_ft_vs_85k_karma_cia_conspiracy", "holdout"),
    (50471360, 50478785, "timeline_dissection_vs_6min_social_media_plot", "holdout"),
    # Trap 3: Concise Dense Evidence vs Long Unsourced Bloviation / Rant
    (50472726, 50477258, "42w_reuters_fact_vs_189w_psychopath_rant", "dev"),
    (50470235, 50473851, "scotus_precedent_vs_192w_hedging_vapor", "holdout"),
    (50469819, 50472710, "54w_mellanox_18pct_vs_268w_populist_ramble", "dev"),
    (50476624, 50477022, "concise_pdf_clause_vs_218w_investor_vent", "holdout"),
    # Trap 4: Off-Topic Links vs Core Event Grounding
    (50478347, 50473977, "hurd_governance_vs_cockroach_idiom_url", "dev"),
    (50467951, 50469126, "bloomberg_chip_ban_vs_wozniak_wiktionary", "holdout"),
    (50472433, 50473655, "source_audit_vs_zelensky_chomsky_youtube", "dev"),
    (50476314, 50473752, "export_compliance_domain_vs_epstein_tangent", "holdout"),
    # Trap 5: Bare Link Drops & Unverified Reddit Rumors vs Contextualized Synthesis
    (50468194, 50475277, "contextualized_timeline_vs_bare_archive_url", "dev"),
    (50477419, 50473185, "top500_analysis_vs_bare_x_url", "holdout"),
    (50468428, 50478216, "strategic_moat_analysis_vs_reddit_layoff_rumor", "holdout"),
    (50471550, 50467438, "doj_bis_analysis_vs_bare_careers_joke_url", "dev"),
    # Trap 6: Original Analysis vs Self-Plagiarism / Duplicate
    (50473538, 50470425, "original_incentive_analysis_vs_self_copy_paste", "holdout"),
    # Trap 7: Civil Insider Analysis vs Moderator-Rebuked Swipes
    (50476126, 50471418, "civil_cuda_history_vs_dang_rebuked_bruh_swipe", "holdout"),
    (50476201, 50470168, "open_weight_taxonomy_vs_tomhow_rebuked_dogma", "dev"),
]


def main() -> None:
    corpus = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    by_id = {c["id"]: c for c in corpus}

    for cid, _grade, _split, _note in GRADED_ITEMS:
        assert cid in by_id, f"Missing graded ID {cid} in corpus_v2.json"
    for w_id, l_id, _cat, _split in ADVERSARIAL_PAIRS:
        assert w_id in by_id and l_id in by_id, f"Missing pair ({w_id}, {l_id})"

    fixtures = {
        "version": "1.0.0",
        "corpus_sha256": "27b31e3ace4bb92b31f7a0a525e74ae41e8a5341cef453118115723b4a4bc425",
        "graded_items": [
            {"id": cid, "grade": g, "split": sp, "rationale": note}
            for cid, g, sp, note in GRADED_ITEMS
        ],
        "adversarial_pairs": [
            {"winner_id": w, "loser_id": l, "category": cat, "split": sp}
            for w, l, cat, sp in ADVERSARIAL_PAIRS
        ],
    }
    out_file = OUT_DIR / "epistemic_fixtures_v1.json"
    out_file.write_text(json.dumps(fixtures, indent=2), encoding="utf-8")

    # Export ONLY a 24-item dev subset to the public benchmark dir so workers never see holdout!
    dev_subset = [x for x in fixtures["graded_items"] if x["split"] == "dev"][:24]
    DEV_PUBLIC_PATH.parent.mkdir(parents=True, exist_ok=True)
    DEV_PUBLIC_PATH.write_text(
        json.dumps(
            {
                "note": "Illustrative dev sample (24 of 56 dev items; 56 holdout items are locked in External Judge).",
                "items": dev_subset,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(
        f"Wrote {len(GRADED_ITEMS)} graded items "
        f"(dev={sum(1 for x in GRADED_ITEMS if x[2]=='dev')}, "
        f"holdout={sum(1 for x in GRADED_ITEMS if x[2]=='holdout')}) "
        f"and {len(ADVERSARIAL_PAIRS)} adversarial pairs."
    )


if __name__ == "__main__":
    main()
