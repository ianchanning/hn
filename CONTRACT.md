# Epistemic Signal vs Bullshit Contract (`v1.0.0`)

## Objective
Rank all `3,010` comments on Hacker News item `50467087` (*Jensen Huang resigns*) by **epistemic usefulness** — maximizing falsifiable documentary grounding, non-redundant information gain, and domain synthesis while suppressing Frankfurtian bullshit, memes, surf-riding conspiracy takes, off-topic tangents, and flamewars.

## Editable Surface
- `hn-comments/ranker.py` (must expose `rank_comments(comments: list[dict]) -> list[dict]`)

## Read-Only Inputs
- `hn-comments/data/corpus_v2.json` (`sha256: 27b31e3ace4bb92b31f7a0a525e74ae41e8a5341cef453118115723b4a4bc425`)
- `hn-comments/benchmark/dev_sample.json` (24-item illustrative `dev` sample)

## Required Output Fields per Comment
- All original comment fields preserved (`id`, `live_dom_rank`, `facet`, `tfidf_top`, etc.)
- `signal_score`: finite `float`
- `signal_rank`: contiguous `int` permutation `1..3010` matching list order
- `epistemic_score`: finite `float` (`>= 0` pre-MMR epistemic quality)
- `bullshit_score`: finite `float` (`>= 0` Frankfurtian bullshit / noise load)
- `tier`: one of:
  - `epistemic_gold`
  - `grounded_analysis`
  - `crowd_chatter`
  - `meme_or_snark`
  - `bullshit_or_flamewar`
  - `downvoted_sink`
- `components`: dict of interpretable sub-scores (`info_gain`, `falsifiability`, `gravity_progeny`, `bullshit_load`, `downvote_sink`)

## Hard Anti-Goodhart Invariant Gates (`valid == true`)
1. Exact permutation of all `3,010` canonical comment IDs with contiguous `signal_rank = 1..3010` and finite `signal_score`.
2. Zero deeply downvoted (`downvote_tier >= 2`, i.e., `c73..cDD`) comments in Global Top 35.
3. Zero moderator-rebuked (`is_mod_rebuked == true`) comments in Global Top 60.
4. Zero bare stub (`own_word_count < 2` or `own_word_count + quoted_word_count < 8`) comments in Global Top 50.
5. Zero near-exact copy-paste duplicates (`max_older_dup_cos >= 0.85`) in Global Top 40.
6. Deterministic execution under `4.0s` without network calls or corpus mutation.
