module Observatory.View.Explore exposing (viewExplore)

{-| Epistemic tuner sliders and dual OLED canvases (Phase Plane & Gravity).
-}

import Html exposing (Html, br, button, code, details, div, h2, i, input, p, span, strong, summary, text)
import Html.Attributes as Attr exposing (attribute, class, id, step, style, type_, value)
import Html.Events exposing (onClick, onInput)
import Observatory.Model exposing (Model)
import Observatory.Msg exposing (Msg(..), WeightField(..))
import Observatory.Ports exposing (computeGravityPlot, computePhasePlot)
import Observatory.Types exposing (CompactComment, LiveComment, ObservatoryPayload, PlotCommand)
import Observatory.View.Style exposing (formatFloat1, formatFloat2, formatThousands)
import Svg
import Svg.Attributes as SvgAttr
import Svg.Events as SvgEvents


viewExplore : Model -> ObservatoryPayload -> Html Msg
viewExplore model payload =
    let
        openAttr =
            if model.labDrawerOpen then
                [ attribute "open" "" ]

            else
                []

        totalComments =
            List.length payload.comments

        cw =
            model.currentWeights

        selectedComment =
            model.selectedCommentId
                |> Maybe.andThen
                    (\id ->
                        model.liveList
                            |> List.filter (\lc -> lc.comment.id == id)
                            |> List.head
                    )
    in
    details (class "proof-drawer" :: id "labDrawer" :: openAttr)
        [ summary [] []
        , div [ class "proof-body grid-12" ]
            [ div [ class "col-3" ]
                [ viewTunerDrawer model payload totalComments cw ]
            , div [ class "col-9" ]
                [ div [ class "dual-oled" ]
                    [ viewPhaseDrawer (computePhasePlot model payload) payload totalComments selectedComment
                    , viewGravityDrawer (computeGravityPlot model payload) payload totalComments selectedComment
                    ]
                ]
            ]
        ]


viewTunerDrawer : Model -> ObservatoryPayload -> Int -> { ig : Float, fa : Float, gp : Float, bp : Float, dp : Float } -> Html Msg
viewTunerDrawer model payload totalComments cw =
    let
        openAttr =
            if model.tunerDrawerOpen then
                [ attribute "open" "" ]

            else
                []

        parseSlider field str =
            case String.toFloat str of
                Just val ->
                    SliderChanged field val

                Nothing ->
                    NoOp
    in
    details (class "graph-drawer" :: id "tunerDrawer" :: openAttr)
        [ summary [ class "graph-summary", onClick ToggleTunerDrawer ]
            [ div [ class "graph-title-group" ]
                [ div [ class "sec-tag" ] [ text "CALIBRATE" ]
                , h2 [] [ text "Signal Tuner" ]
                ]
            , span [ class "mob-graph-pill" ] []
            ]
        , div [ class "control-panel" ]
            [ div [ class "slider-row" ]
                [ div [ class "slider-lbl" ]
                    [ span [] [ text "1. Info Gain (IDF)" ]
                    , span [ id "val_ig" ] [ text (formatFloat2 cw.ig) ]
                    ]
                , input
                    [ type_ "range"
                    , id "sl_ig"
                    , Attr.min "0"
                    , Attr.max "5"
                    , step "0.05"
                    , value (String.fromFloat cw.ig)
                    , onInput (parseSlider WInfoGain)
                    ]
                    []
                ]
            , div [ class "slider-row" ]
                [ div [ class "slider-lbl" ]
                    [ span [] [ text "2. Falsifiability" ]
                    , span [ id "val_fa" ] [ text (formatFloat2 cw.fa) ]
                    ]
                , input
                    [ type_ "range"
                    , id "sl_fa"
                    , Attr.min "0"
                    , Attr.max "5"
                    , step "0.05"
                    , value (String.fromFloat cw.fa)
                    , onInput (parseSlider WFalsifiability)
                    ]
                    []
                ]
            , div [ class "slider-row" ]
                [ div [ class "slider-lbl" ]
                    [ span [] [ text "3. Gravity & Precision" ]
                    , span [ id "val_gp" ] [ text (formatFloat2 cw.gp) ]
                    ]
                , input
                    [ type_ "range"
                    , id "sl_gp"
                    , Attr.min "0"
                    , Attr.max "4"
                    , step "0.05"
                    , value (String.fromFloat cw.gp)
                    , onInput (parseSlider WGravityProgeny)
                    ]
                    []
                ]
            , div [ class "slider-row" ]
                [ div [ class "slider-lbl" ]
                    [ span [] [ text "4. Bullshit Penalty" ]
                    , span [ id "val_bp" ] [ text (formatFloat2 cw.bp) ]
                    ]
                , input
                    [ type_ "range"
                    , id "sl_bp"
                    , Attr.min "0"
                    , Attr.max "5"
                    , step "0.05"
                    , value (String.fromFloat cw.bp)
                    , onInput (parseSlider WBullshitPenalty)
                    ]
                    []
                ]
            , div [ class "slider-row" ]
                [ div [ class "slider-lbl" ]
                    [ span [] [ text "5. Downvote Sink" ]
                    , span [ id "val_dp" ] [ text (formatFloat2 cw.dp) ]
                    ]
                , input
                    [ type_ "range"
                    , id "sl_dp"
                    , Attr.min "0"
                    , Attr.max "5"
                    , step "0.05"
                    , value (String.fromFloat cw.dp)
                    , onInput (parseSlider WDownvotePenalty)
                    ]
                    []
                ]
            , button
                [ class "tab-btn"
                , id "resetWeightsBtn"
                , style "width" "100%"
                , style "margin-top" "6px"
                , onClick ResetWeights
                ]
                [ text "Reset Calibrated Weights" ]
            , p []
                [ text
                    ("Drag any weight to watch the "
                        ++ formatThousands totalComments
                        ++ "-point phase plane and comment ranking re-solve instantaneously."
                    )
                , br [] []
                , text "• "
                , strong [] [ text "c5A Rescue: " ]
                , text "Sourced "
                , code [] [ text "c5A" ]
                , text " rebuttals survive partisan downvotes."
                , br [] []
                , text "• "
                , strong [] [ text "Context Gate: " ]
                , text "Meme links & bare drops get zero citation boost."
                ]
            ]
        ]


viewPhaseDrawer : PlotCommand -> ObservatoryPayload -> Int -> Maybe LiveComment -> Html Msg
viewPhaseDrawer plotCmd payload totalComments selectedComment =
    details [ class "graph-drawer", id "phaseDrawer", attribute "open" "" ]
        [ summary [ class "graph-summary" ]
            [ div [ class "graph-title-group" ]
                [ div [ class "sec-tag" ] [ text "EPISTEMIC PHASE PLANE" ]
                , h2 [] [ text "Crowd Chatter vs. Grounded Signal" ]
                ]
            , span [ class "mob-graph-pill" ] []
            ]
        , div [ class "oled-bay" ]
            [ div [ class "oled-head" ]
                [ span [] [ text "Bullshit (Y) // Signal (X) " ]
                , span [ class "sig" ] [ text ("TAP POINT (N = " ++ formatThousands totalComments ++ ")") ]
                ]
            , viewSvgPlot plotCmd
            , div [ class "legend-row" ]
                [ span [] [ i [ class "dot", style "background" "rgb(0, 230, 118)" ] [], text ("Gold (" ++ String.fromInt payload.tiers.epistemicGold ++ ")") ]
                , span [] [ i [ class "dot", style "background" "rgb(56, 189, 248)" ] [], text ("Grounded (" ++ String.fromInt payload.tiers.groundedAnalysis ++ ")") ]
                , span [] [ i [ class "dot", style "background" "rgb(148, 163, 184)" ] [], text ("Chatter (" ++ String.fromInt payload.tiers.crowdChatter ++ ")") ]
                , span [] [ i [ class "dot", style "background" "rgb(255, 179, 0)" ] [], text ("Meme (" ++ String.fromInt payload.tiers.memeOrSnark ++ ")") ]
                , span [] [ i [ class "dot", style "background" "rgb(255, 68, 0)" ] [], text ("BS (" ++ String.fromInt payload.tiers.bullshitOrFlamewar ++ ")") ]
                ]
            , div [ class "probe-box" ]
                [ div [ id "phaseProbe", class "probe-clamp" ]
                    [ case selectedComment of
                        Just lc ->
                            viewProbeSnippet lc

                        Nothing ->
                            text "Tap or hover any point to inspect its coordinates and filter the comment below."
                    ]
                ]
            ]
        ]


viewGravityDrawer : PlotCommand -> ObservatoryPayload -> Int -> Maybe LiveComment -> Html Msg
viewGravityDrawer plotCmd payload totalComments selectedComment =
    let
        lr =
            payload.largestRoot

        defaultMsg =
            "Top slot ("
                ++ lr.topDom1Author
                ++ ", "
                ++ formatFloat1 lr.topDom1Age
                ++ "h); largest subtree (@"
                ++ lr.author
                ++ ") occupies "
                ++ String.fromInt lr.slots
                ++ " slots (HN POS "
                ++ String.fromInt lr.startDom
                ++ ".."
                ++ String.fromInt lr.endDom
                ++ ")."
    in
    details [ class "graph-drawer", id "gravityDrawer", attribute "open" "" ]
        [ summary [ class "graph-summary" ]
            [ div [ class "graph-title-group" ]
                [ div [ class "sec-tag" ] [ text "NEWS.ARC GRAVITY & TREE-LOCK" ]
                , h2 [] [ text "Why Live HN Buried Primary Evidence" ]
                ]
            , span [ class "mob-graph-pill" ] []
            ]
        , div [ class "oled-bay" ]
            [ div [ class "oled-head" ]
                [ span [] [ text ("HN POS (1.." ++ formatThousands totalComments ++ ") (Y) // Age (Hours) (X)") ]
                , span [ class "sig" ] [ text "(T + 2)^1.8" ]
                ]
            , viewSvgPlot plotCmd
            , div [ class "legend-row" ]
                [ span [] [ i [ class "dot", style "background" "rgb(0, 230, 118)" ] [], text ("Buried Gold (HN POS > " ++ String.fromInt payload.buriedCutoff ++ ")") ]
                , span [] [ i [ class "dot", style "background" "rgb(255, 179, 0)" ] [], text "Surf Mirage (<3.2h)" ]
                , span [] [ i [ class "dot", style "background" "rgb(255, 68, 0)" ] [], text "Downvoted / Mod-Rebuked" ]
                ]
            , div [ class "probe-box" ]
                [ div [ id "gravProbe", class "probe-clamp" ]
                    [ case selectedComment of
                        Just lc ->
                            viewProbeSnippet lc

                        Nothing ->
                            text defaultMsg
                    ]
                ]
            ]
        ]


viewProbeSnippet : LiveComment -> Html Msg
viewProbeSnippet lc =
    let
        c =
            lc.comment

        delta =
            c.dom - lc.liveRank

        deltaStr =
            if delta >= 0 then
                "+" ++ String.fromInt delta

            else
                String.fromInt delta

        snippet =
            String.left 88 c.txt
                |> String.replace "\n" " "
    in
    div []
        [ div [ class "hn-comhead" ]
            [ text (c.au ++ " | Signal " ++ String.fromInt lc.liveRank ++ " vs HN " ++ String.fromInt c.dom ++ " (" ++ deltaStr ++ ") ")
            , button
                [ class "tab-btn"
                , style "padding" "0 6px"
                , style "margin-left" "6px"
                , onClick ClearSelection
                ]
                [ text "Clear" ]
            ]
        , text (snippet ++ "...")
        ]


viewSvgPlot : PlotCommand -> Html Msg
viewSvgPlot cmd =
    let
        gridLines =
            List.range 1 5
                |> List.concatMap
                    (\i ->
                        let
                            gx =
                                String.fromFloat (540.0 * toFloat i / 6.0)

                            gy =
                                String.fromFloat (300.0 * toFloat i / 6.0)
                        in
                        [ Svg.line [ SvgAttr.x1 gx, SvgAttr.y1 "0", SvgAttr.x2 gx, SvgAttr.y2 "300", SvgAttr.stroke "rgb(30, 36, 44)", SvgAttr.strokeWidth "1" ] []
                        , Svg.line [ SvgAttr.x1 "0", SvgAttr.y1 gy, SvgAttr.x2 "540", SvgAttr.y2 gy, SvgAttr.stroke "rgb(30, 36, 44)", SvgAttr.strokeWidth "1" ] []
                        ]
                    )

        largestRootHighlight =
            case cmd.largestRoot of
                Just lr ->
                    if lr.slots > 1 then
                        let
                            totalN =
                                toFloat (max 1 (List.length cmd.points))

                            yStart =
                                20.0 + (toFloat lr.startDom / totalN) * 256.0

                            yEnd =
                                20.0 + (toFloat lr.endDom / totalN) * 256.0
                        in
                        [ Svg.rect
                            [ SvgAttr.x "32"
                            , SvgAttr.y (String.fromFloat yStart)
                            , SvgAttr.width "492"
                            , SvgAttr.height (String.fromFloat (max 4.0 (yEnd - yStart)))
                            , SvgAttr.fill "rgba(255, 68, 0, 0.09)"
                            ]
                            []
                        , Svg.text_
                            [ SvgAttr.x "40"
                            , SvgAttr.y (String.fromFloat (min 278.0 (yStart + 13.0)))
                            , SvgAttr.fill "rgba(255, 110, 64, 0.75)"
                            , SvgAttr.fontSize "10px"
                            , SvgAttr.fontFamily "ui-monospace, Menlo, monospace"
                            ]
                            [ Svg.text ("LARGEST SUBTREE (@" ++ lr.author ++ ": " ++ String.fromInt lr.slots ++ " SLOTS, HN POS " ++ String.fromInt lr.startDom ++ ".." ++ String.fromInt lr.endDom ++ ")") ]
                        ]

                    else
                        []

                Nothing ->
                    []

        pointNodes =
            cmd.points
                |> List.reverse
                |> List.concatMap
                    (\p ->
                        let
                            cx =
                                String.fromFloat p.x

                            cy =
                                String.fromFloat p.y

                            col =
                                "rgba(" ++ String.fromInt p.colour.r ++ ", " ++ String.fromInt p.colour.g ++ ", " ++ String.fromInt p.colour.b ++ ", " ++ String.fromFloat p.colour.a ++ ")"

                            probeMsg =
                                CanvasProbeReceived { canvasId = cmd.canvasId, commentId = p.commentId }

                            dot =
                                Svg.circle
                                    [ SvgAttr.cx cx
                                    , SvgAttr.cy cy
                                    , SvgAttr.r (String.fromFloat p.radius)
                                    , SvgAttr.fill col
                                    , SvgEvents.onClick probeMsg
                                    , SvgEvents.onMouseOver probeMsg
                                    ]
                                    []
                        in
                        if cmd.selectedId == Just p.commentId then
                            [ dot
                            , Svg.circle
                                [ SvgAttr.cx cx
                                , SvgAttr.cy cy
                                , SvgAttr.r (String.fromFloat (p.radius + 4.0))
                                , SvgAttr.fill "none"
                                , SvgAttr.stroke "rgb(255, 255, 255)"
                                , SvgAttr.strokeWidth "2"
                                ]
                                []
                            ]

                        else
                            [ dot ]
                    )

        axisLabels =
            [ Svg.text_
                [ SvgAttr.x "245"
                , SvgAttr.y "293"
                , SvgAttr.fill "rgb(140, 150, 162)"
                , SvgAttr.fontSize "10px"
                , SvgAttr.fontFamily "ui-monospace, Menlo, monospace"
                ]
                [ Svg.text cmd.axisConfig.xLabel ]
            , Svg.text_
                [ SvgAttr.x "8"
                , SvgAttr.y "14"
                , SvgAttr.fill "rgb(140, 150, 162)"
                , SvgAttr.fontSize "10px"
                , SvgAttr.fontFamily "ui-monospace, Menlo, monospace"
                ]
                [ Svg.text cmd.axisConfig.yLabel ]
            ]
    in
    Svg.svg
        [ SvgAttr.id cmd.canvasId
        , Attr.class "plot"
        , SvgAttr.viewBox "0 0 540 300"
        , SvgAttr.width "540"
        , SvgAttr.height "300"
        ]
        (gridLines ++ largestRootHighlight ++ pointNodes ++ axisLabels)
