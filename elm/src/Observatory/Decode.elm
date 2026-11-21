module Observatory.Decode exposing (payloadDecoder, tierDecoder)

{-| JSON decoders for the observatory payload embedded by Python.

Decodes the contents of `<script id="observatoryData" type="application/json">`.

-}

import Dict exposing (Dict)
import Json.Decode as D exposing (Decoder)
import Observatory.Types exposing (..)


payloadDecoder : Decoder ObservatoryPayload
payloadDecoder =
    D.succeed ObservatoryPayload
        |> andMap (D.field "story_id" D.int)
        |> andMap (D.field "story_title" D.string)
        |> andMap (D.field "story_url" D.string)
        |> andMap (D.field "is_benchmark" D.bool)
        |> andMap (D.field "manifest" manifestDecoder)
        |> andMap (D.field "judge" (D.nullable judgeDecoder))
        |> andMap (D.field "weights" weightsDecoder)
        |> andMap (D.field "tiers" tierCountsDecoder)
        |> andMap (D.field "facets" (D.dict D.int))
        |> andMap (D.field "facet_options" (D.list facetOptionDecoder))
        |> andMap (D.field "facet_diagnostics" (D.list facetDiagnosticDecoder))
        |> andMap (D.field "source_categories" (D.list sourceCategoryDecoder))
        |> andMap (D.field "story_anchors" (D.list D.string))
        |> andMap (D.field "largest_root" largestRootDecoder)
        |> andMap (D.field "buried_cutoff" D.int)
        |> andMap (D.field "rescue_top_k" D.int)
        |> andMap (D.field "ablations" (D.list ablationDecoder))
        |> andMap (D.field "tournament" (D.list tournamentDecoder))
        |> andMap (D.field "comments" (D.list commentDecoder))


{-| Applicative-style pipeline helper (elm/json doesn't ship one).
-}
andMap : Decoder a -> Decoder (a -> b) -> Decoder b
andMap =
    D.map2 (|>)



-- TIER


tierDecoder : Decoder Tier
tierDecoder =
    D.string
        |> D.andThen
            (\s ->
                case s of
                    "epistemic_gold" ->
                        D.succeed EpistemicGold

                    "grounded_analysis" ->
                        D.succeed GroundedAnalysis

                    "crowd_chatter" ->
                        D.succeed CrowdChatter

                    "meme_or_snark" ->
                        D.succeed MemeOrSnark

                    "bullshit_or_flamewar" ->
                        D.succeed BullshitOrFlamewar

                    "downvoted_sink" ->
                        D.succeed DownvotedSink

                    other ->
                        D.fail ("Unknown tier: " ++ other)
            )



-- WEIGHTS


weightsDecoder : Decoder Weights
weightsDecoder =
    D.map8 Weights
        (D.field "info_gain" D.float)
        (D.field "falsifiability" D.float)
        (D.field "gravity_progeny" D.float)
        (D.field "bullshit_penalty" D.float)
        (D.field "downvote_penalty" D.float)
        (D.field "mmr_sim_lambda" D.float)
        (D.field "mmr_root_lambda" D.float)
        (D.field "mmr_facet_lambda" D.float)



-- COMMENT


commentDecoder : Decoder CompactComment
commentDecoder =
    D.succeed CompactComment
        |> andMap (D.field "id" D.int)
        |> andMap (D.field "au" D.string)
        |> andMap (D.field "dom" D.int)
        |> andMap (D.field "sr" D.int)
        |> andMap (D.field "sc" D.float)
        |> andMap (D.field "ep" D.float)
        |> andMap (D.field "bs" D.float)
        |> andMap (D.field "d" D.int)
        |> andMap (D.field "age" D.float)
        |> andMap (D.field "grav" D.float)
        |> andMap (D.field "surf" D.float)
        |> andMap (D.field "fade" D.string)
        |> andMap (D.field "dt" D.int)
        |> andMap (D.field "ut" D.int)
        |> andMap (D.field "lu" D.int)
        |> andMap (D.field "w" D.int)
        |> andMap (D.field "qw" D.int)
        |> andMap (D.field "k" D.int)
        |> andMap (D.field "kpp" D.float)
        |> andMap (D.field "td" D.float)
        |> andMap (D.field "mod" D.int)
        |> andMap (D.field "pp" D.int)
        |> andMap (D.field "meme" D.int)
        |> andMap (D.field "tier" tierDecoder)
        |> andMap (D.field "facet" D.string)
        |> andMap (D.field "flbl" D.string)
        |> andMap (D.field "urls" (D.list D.string))
        |> andMap (D.field "ig" D.float)
        |> andMap (D.field "fa" D.float)
        |> andMap (D.field "gp" D.float)
        |> andMap (D.field "bl" D.float)
        |> andMap (D.field "ds" D.float)
        |> andMap (D.field "txt" D.string)



-- MANIFEST


manifestDecoder : Decoder Manifest
manifestDecoder =
    D.succeed Manifest
        |> andMap (D.field "story_title" D.string |> withDefault "")
        |> andMap (D.field "story_url" D.string |> withDefault "")
        |> andMap (D.field "points" D.int |> withDefault 0)
        |> andMap (D.field "story_author" D.string |> withDefault "")
        |> andMap (D.field "t2_ref_utc" D.string |> withDefault "")
        |> andMap (D.field "delta_minutes" D.float |> withDefault 0.0)
        |> andMap (D.field "counts" manifestCountsDecoder |> withDefault { totalComments = 0, uniqueAuthorsProfiled = 0, pagesFetched = 1 })
        |> andMap (D.field "facet_labels" (D.dict D.string) |> withDefault Dict.empty)
        |> andMap (D.field "facet_clusters" (D.list facetClusterDecoder) |> withDefault [])
        |> andMap (D.field "story_anchors" (D.list D.string) |> withDefault [])


manifestCountsDecoder : Decoder ManifestCounts
manifestCountsDecoder =
    D.map3 ManifestCounts
        (D.field "total_comments" D.int |> withDefault 0)
        (D.field "unique_authors_profiled" D.int |> withDefault 0)
        (D.field "pages_fetched" D.int |> withDefault 1)


facetClusterDecoder : Decoder FacetCluster
facetClusterDecoder =
    D.map2 FacetCluster
        (D.field "slug" D.string)
        (D.field "top_terms" (D.list D.string) |> withDefault [])



-- TIER COUNTS


tierCountsDecoder : Decoder TierCounts
tierCountsDecoder =
    D.map6 TierCounts
        (D.field "epistemic_gold" D.int |> withDefault 0)
        (D.field "grounded_analysis" D.int |> withDefault 0)
        (D.field "crowd_chatter" D.int |> withDefault 0)
        (D.field "meme_or_snark" D.int |> withDefault 0)
        (D.field "bullshit_or_flamewar" D.int |> withDefault 0)
        (D.field "downvoted_sink" D.int |> withDefault 0)



-- FACETS & SOURCES


facetOptionDecoder : Decoder FacetOption
facetOptionDecoder =
    D.map3 FacetOption
        (D.field "slug" D.string)
        (D.field "label" D.string)
        (D.field "count" D.int)


facetDiagnosticDecoder : Decoder FacetDiagnostic
facetDiagnosticDecoder =
    D.succeed FacetDiagnostic
        |> andMap (D.field "slug" D.string)
        |> andMap (D.field "label" D.string)
        |> andMap (D.field "count" D.int)
        |> andMap (D.field "useful" D.int)
        |> andMap (D.field "useful_pct" D.float)
        |> andMap (D.field "terms" D.string)


sourceCategoryDecoder : Decoder SourceCategory
sourceCategoryDecoder =
    D.map2 SourceCategory
        (D.field "category" D.string)
        (D.field "count" D.int)



-- LARGEST ROOT


largestRootDecoder : Decoder LargestRoot
largestRootDecoder =
    D.map8 LargestRoot
        (D.field "root_id" D.int)
        (D.field "author" D.string)
        (D.field "slots" D.int)
        (D.field "start_dom" D.int)
        (D.field "end_dom" D.int)
        (D.field "share_pct" D.float)
        (D.field "top_dom1_age" D.float)
        (D.field "top_dom1_author" D.string)



-- BENCHMARK


judgeDecoder : Decoder JudgeResult
judgeDecoder =
    D.succeed JudgeResult
        |> andMap (D.field "judge_version" D.string)
        |> andMap (D.field "score" D.float)
        |> andMap (D.field "dev_score" D.float)
        |> andMap (D.field "holdout_score" D.float)
        |> andMap (D.field "delta_vs_hn" D.float)
        |> andMap (D.field "hn_live_baseline_score" D.float)
        |> andMap (D.field "full_metrics" judgeMetricsDecoder)


judgeMetricsDecoder : Decoder JudgeMetrics
judgeMetricsDecoder =
    D.map6 JudgeMetrics
        (D.field "ndcg20" D.float |> withDefault 0.0)
        (D.field "pairwise_concordance" D.float |> withDefault 0.0)
        (D.field "adversarial_acc" D.float |> withDefault 0.0)
        (D.field "buried_gold_recall_top45" D.float |> withDefault 0.0)
        (D.field "bullshit_sink_percentile" D.float |> withDefault 0.0)
        (D.field "top20_diversity" D.float |> withDefault 0.0)


ablationDecoder : Decoder AblationRow
ablationDecoder =
    D.map8 AblationRow
        (D.field "name" D.string)
        (D.field "score" D.float)
        (D.field "ndcg20" D.float)
        (D.field "pairwise_concordance" D.float)
        (D.field "adversarial_acc" D.float)
        (D.field "buried_gold_recall_top45" D.float)
        (D.field "bullshit_sink_percentile" D.float)
        (D.field "top20_diversity" D.float)


tournamentDecoder : Decoder TournamentRow
tournamentDecoder =
    D.succeed TournamentRow
        |> andMap (D.field "stage" D.string)
        |> andMap (D.field "sha" D.string)
        |> andMap (D.field "score" D.float)
        |> andMap (D.field "dev_score" D.float)
        |> andMap (D.field "holdout_score" D.float)
        |> andMap (D.field "disposition" D.string |> withDefault "")



-- HELPERS


{-| Decode with a fallback default if the field is missing or wrong type.
-}
withDefault : a -> Decoder a -> Decoder a
withDefault default decoder =
    D.oneOf [ decoder, D.succeed default ]
