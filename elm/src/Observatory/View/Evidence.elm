module Observatory.View.Evidence exposing (viewEvidence)

{-| Collapsible evidence drawer: benchmark ablation / tournament,
or unsupervised facet diagnostics and source registry.
-}

import Html exposing (Html, code, details, div, h2, p, strong, table, tbody, td, text, th, thead, tr)
import Html.Attributes exposing (attribute, class, id, style)
import Observatory.Model exposing (Model)
import Observatory.Msg exposing (Msg)
import Observatory.Types exposing (AblationRow, FacetDiagnostic, JudgeResult, ObservatoryPayload, SourceCategory, TournamentRow)
import Observatory.View.Style exposing (formatFloat1, formatFloat2, formatFloat3, formatThousands)


viewEvidence : Model -> ObservatoryPayload -> Html Msg
viewEvidence model payload =
    let
        openAttr =
            if model.proofDrawerOpen then
                [ attribute "open" "" ]

            else
                []

        content =
            case payload.judge of
                Just judge ->
                    viewBenchmarkEvidence judge payload

                Nothing ->
                    viewLiveEvidence payload
    in
    details (class "proof-drawer" :: id "proofDrawer" :: openAttr) [ content ]


viewBenchmarkEvidence : JudgeResult -> ObservatoryPayload -> Html Msg
viewBenchmarkEvidence _ payload =
    let
        maxAblationScore =
            payload.ablations
                |> List.map .score
                |> List.maximum
                |> Maybe.withDefault 0.0

        renderAblationRow idx r =
            let
                rowClass =
                    if idx == 0 then
                        "hn-row"

                    else if abs (r.score - maxAblationScore) < 0.02 then
                        "winner"

                    else
                        ""
            in
            tr [ class rowClass ]
                [ td [] [ text r.name ]
                , td [] [ strong [] [ text (formatFloat2 r.score) ] ]
                , td [] [ text (formatFloat3 r.ndcg20) ]
                , td [] [ text (formatFloat3 r.pairwiseConcordance) ]
                , td [] [ text (formatFloat1 (100.0 * r.adversarialAcc) ++ "%") ]
                , td [] [ text (formatFloat1 (100.0 * r.buriedGoldRecallTop45) ++ "%") ]
                , td [] [ text (formatFloat1 (100.0 * r.bullshitSinkPercentile) ++ "%") ]
                , td [] [ text (formatFloat3 r.top20Diversity) ]
                ]

        renderTourneyRow idx t =
            let
                rowClass =
                    if idx == 0 then
                        "hn-row"

                    else if t.disposition == "promoted_champion" || t.disposition == "promoted_best" then
                        "winner"

                    else
                        ""

                stageSuffix =
                    if t.disposition == "promoted_champion" then
                        " ★"

                    else
                        ""
            in
            tr [ class rowClass ]
                [ td [] [ text (t.stage ++ stageSuffix) ]
                , td [] [ text t.sha ]
                , td [] [ strong [] [ text (formatFloat2 t.score) ] ]
                , td [] [ text (formatFloat2 t.devScore) ]
                , td [] [ text (formatFloat2 t.holdoutScore) ]
                ]
    in
    div [ class "proof-body grid-12" ]
        [ div [ class "col-7" ]
            [ div [ class "sec-tag" ] [ text "CONTROLLED ABLATION MATRIX" ]
            , h2 [] [ text "Marginal Gain of Each Epistemic Pillar" ]
            , div [ style "overflow-x" "auto" ]
                [ table [ class "ablation", id "ablationTable" ]
                    [ thead []
                        [ tr []
                            [ th [] [ text "Model / Controlled Ablation Stage" ]
                            , th [] [ text "Score" ]
                            , th [] [ text "NDCG@20" ]
                            , th [] [ text "Concord" ]
                            , th [] [ text "Adv Traps" ]
                            , th [] [ text "Rescue" ]
                            , th [] [ text "Sink" ]
                            , th [] [ text "Div" ]
                            ]
                        ]
                    , tbody [ id "ablationBody" ]
                        (List.indexedMap renderAblationRow payload.ablations)
                    ]
                ]
            ]
        , div [ class "col-5" ]
            [ div [ class "sec-tag" ] [ text "FORGET-TEAM 4-AGENT HERDR TOURNAMENT" ]
            , h2 [] [ text "Amnesia Reset & Holdout Generalization" ]
            , div [ style "overflow-x" "auto", style "max-height" "365px", style "overflow-y" "auto" ]
                [ table [ class "ablation", id "tourneyTable" ]
                    [ thead []
                        [ tr []
                            [ th [] [ text "Stage / Worker" ]
                            , th [] [ text "SHA" ]
                            , th [] [ text "Full" ]
                            , th [] [ text "Dev" ]
                            , th [] [ text "Holdout" ]
                            ]
                        ]
                    , tbody [ id "tourneyBody" ]
                        (List.indexedMap renderTourneyRow payload.tournament)
                    ]
                ]
            ]
        ]


viewLiveEvidence : ObservatoryPayload -> Html Msg
viewLiveEvidence payload =
    let
        totalCnt =
            List.length payload.comments

        usefulCnt =
            payload.tiers.epistemicGold + payload.tiers.groundedAnalysis

        usefulPct =
            if totalCnt > 0 then
                100.0 * toFloat usefulCnt / toFloat totalCnt

            else
                0.0

        goldPct =
            if totalCnt > 0 then
                100.0 * toFloat payload.tiers.epistemicGold / toFloat totalCnt

            else
                0.0

        noisePct =
            max 0.0 (100.0 - usefulPct)

        lr =
            payload.largestRoot

        primarySourced =
            payload.comments
                |> List.filter (\c -> c.ut >= 2)
                |> List.length

        renderFacetDiag idx f =
            let
                rowClass =
                    if idx == 0 then
                        "winner"

                    else
                        ""
            in
            tr [ class rowClass ]
                [ td [] [ text f.label ]
                , td [] [ text (String.fromInt f.count) ]
                , td [] [ strong [] [ text (String.fromInt f.useful) ] ]
                , td [] [ text (formatFloat1 f.usefulPct ++ "%") ]
                , td [ style "text-align" "left" ] [ text f.terms ]
                ]

        renderSourceCat sc =
            tr []
                [ td [] [ text sc.category ]
                , td [] [ strong [] [ text (String.fromInt sc.count) ] ]
                ]

        sourceRows =
            if List.isEmpty payload.sourceCategories then
                [ tr [] [ td [] [ text "No external links" ], td [] [ text "0" ] ] ]

            else
                List.map renderSourceCat payload.sourceCategories

        anchorBox =
            if List.isEmpty payload.storyAnchors then
                text ""

            else
                div
                    [ id "anchorListBox"
                    , style "color" "rgb(90, 90, 88)"
                    , style "margin-top" "16px"
                    ]
                    [ text ("UNSUPERVISED STORY ANCHORS: " ++ String.join ", " payload.storyAnchors) ]
    in
    div []
        [ div [ class "proof-body" ]
            [ p [ style "margin" "0 0 12px", style "color" "rgb(70, 70, 68)" ]
                [ text "Replacing surface crowd prediction and "
                , code [] [ text "(T + 2)^1.8" ]
                , text " recency decay with Shannon/IDF surprisal, Popperian falsifiability, Frankfurtian bullshit suppression, inverse "
                , code [] [ text "news.arc" ]
                , text " physics, and submodular portfolio selection."
                ]
            , div [ class "kpi-strip" ]
                [ div [ class "kpi-cell" ]
                    [ div [ class "kpi-label" ] [ text "Corpus Audited" ]
                    , div [ class "kpi-val" ] [ text (formatThousands totalCnt) ]
                    , div [ class "kpi-sub" ]
                        [ text
                            (String.fromInt payload.manifest.counts.pagesFetched
                                ++ " HTML page(s) • "
                                ++ formatThousands payload.manifest.counts.uniqueAuthorsProfiled
                                ++ " authors"
                            )
                        ]
                    ]
                , div [ class "kpi-cell" ]
                    [ div [ class "kpi-label" ] [ text "Actual Useful Signal" ]
                    , div [ class "kpi-val ok" ] [ text (formatFloat1 usefulPct ++ "%") ]
                    , div [ class "kpi-sub" ]
                        [ text
                            (String.fromInt usefulCnt
                                ++ " comments ("
                                ++ String.fromInt payload.tiers.epistemicGold
                                ++ " Gold / "
                                ++ formatFloat1 goldPct
                                ++ "%)"
                            )
                        ]
                    ]
                , div [ class "kpi-cell" ]
                    [ div [ class "kpi-label" ] [ text "Chatter & Bullshit" ]
                    , div [ class "kpi-val hi" ] [ text (formatFloat1 noisePct ++ "%") ]
                    , div [ class "kpi-sub" ]
                        [ text
                            (String.fromInt payload.tiers.crowdChatter
                                ++ " chatter • "
                                ++ String.fromInt payload.tiers.bullshitOrFlamewar
                                ++ " BS • "
                                ++ String.fromInt payload.tiers.downvotedSink
                                ++ " faded"
                            )
                        ]
                    ]
                , div [ class "kpi-cell" ]
                    [ div [ class "kpi-label" ] [ text "Primary Citations" ]
                    , div [ class "kpi-val ok" ] [ text (String.fromInt primarySourced) ]
                    , div [ class "kpi-sub" ] [ text "Tier 2/3 verified citations" ]
                    ]
                , div [ class "kpi-cell" ]
                    [ div [ class "kpi-label" ] [ text "Facet Sub-Themes" ]
                    , div [ class "kpi-val" ] [ text (String.fromInt (List.length payload.facetOptions)) ]
                    , div [ class "kpi-sub" ] [ text "Auto-discovered TF-IDF clusters" ]
                    ]
                , div [ class "kpi-cell" ]
                    [ div [ class "kpi-label" ] [ text "Largest Root Monopoly" ]
                    , div [ class "kpi-val hi" ] [ text (String.fromInt lr.slots) ]
                    , div [ class "kpi-sub" ]
                        [ text
                            ("HN POS "
                                ++ String.fromInt lr.startDom
                                ++ ".."
                                ++ String.fromInt lr.endDom
                                ++ " ("
                                ++ formatFloat1 lr.sharePct
                                ++ "% of thread)"
                            )
                        ]
                    ]
                ]
            ]
        , div [ class "proof-body grid-12" ]
            [ div [ class "col-7" ]
                [ div [ class "sec-tag" ] [ text "UNSUPERVISED 5-CLUSTER FACETS (SPHERICAL K-MEANS++)" ]
                , h2 [] [ text "Auto-Discovered Sub-Themes & Signal Yield" ]
                , div [ style "overflow-x" "auto" ]
                    [ table [ class "ablation", id "facetDiagTable" ]
                        [ thead []
                            [ tr []
                                [ th [] [ text "Discovered Facet Cluster" ]
                                , th [] [ text "Comments" ]
                                , th [] [ text "Useful Signal" ]
                                , th [] [ text "Signal %" ]
                                , th [] [ text "Centroid Salient Terms" ]
                                ]
                            ]
                        , tbody [ id "facetDiagBody" ]
                            (List.indexedMap renderFacetDiag payload.facetDiagnostics)
                        ]
                    ]
                ]
            , div [ class "col-5" ]
                [ div [ class "sec-tag" ] [ text "SOURCE REGISTRY & STORY ANCHORS" ]
                , h2 [] [ text "Cross-Domain Citations & TF-IDF Anchors" ]
                , div [ style "overflow-x" "auto", style "max-height" "365px", style "overflow-y" "auto" ]
                    [ table [ class "ablation", id "sourceCatTable" ]
                        [ thead []
                            [ tr []
                                [ th [] [ text "Source Registry Category" ]
                                , th [] [ text "Cited Comments" ]
                                ]
                            ]
                        , tbody [ id "sourceCatBody" ] sourceRows
                        ]
                    , anchorBox
                    ]
                ]
            ]
        ]
