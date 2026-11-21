module Observatory.View.Header exposing (viewHeader)

{-| HN topbar, fatitem story box, and view mode tabs.
-}

import Html exposing (Html, a, button, div, header, span, text)
import Html.Attributes exposing (attribute, class, href, id, type_)
import Html.Events exposing (onClick)
import Observatory.Model exposing (Model)
import Observatory.Msg exposing (Msg(..))
import Observatory.Types exposing (ObservatoryPayload, ViewMode(..))
import Observatory.View.Style exposing (extractHost, formatFloat1, formatFloat2, formatThousands)


viewHeader : Model -> ObservatoryPayload -> Html Msg
viewHeader model payload =
    let
        hnItemHref =
            "https://news.ycombinator.com/item?id=" ++ String.fromInt payload.storyId

        storyHref =
            if String.isEmpty payload.storyUrl then
                hnItemHref

            else
                payload.storyUrl

        siteHost =
            extractHost payload.storyUrl

        sitebitHtml =
            if String.isEmpty payload.storyUrl then
                text ""

            else
                span [ class "sitebit comhead" ]
                    [ text " ("
                    , a [ href ("https://news.ycombinator.com/from?site=" ++ siteHost) ]
                        [ span [ class "sitestr" ] [ text siteHost ] ]
                    , text ")"
                    ]

        totalComments =
            List.length payload.comments

        usefulCnt =
            payload.tiers.epistemicGold + payload.tiers.groundedAnalysis

        noisePct =
            if totalComments > 0 then
                max 0.0 (100.0 - (100.0 * toFloat usefulCnt / toFloat (max 1 totalComments)))

            else
                0.0

        ageStr =
            if payload.manifest.deltaMinutes > 0 then
                if payload.manifest.deltaMinutes < 60 then
                    String.fromInt (round payload.manifest.deltaMinutes) ++ "m ago"

                else
                    formatFloat1 (payload.manifest.deltaMinutes / 60.0) ++ "h ago"

            else
                "recently"

        modes =
            [ ( TopSignal, "Top 40" )
            , ( HnTop40, "HN Top 40" )
            ]

        renderTab ( mode, label ) isLast =
            let
                isActive =
                    model.activeMode == mode

                btn =
                    button
                        [ type_ "button"
                        , class
                            ("nav-btn mode-tab"
                                ++ (if isActive then
                                        " active"

                                    else
                                        ""
                                   )
                            )
                        , attribute "role" "tab"
                        , attribute "aria-selected"
                            (if isActive then
                                "true"

                             else
                                "false"
                            )
                        , onClick (SetMode mode)
                        ]
                        [ text label ]
            in
            if isLast then
                [ btn ]

            else
                [ btn, text " | " ]

        renderedTabs =
            List.concat
                (List.indexedMap
                    (\idx item ->
                        renderTab item (idx == List.length modes - 1)
                    )
                    modes
                )
    in
    header [ class "hn-header" ]
        [ div [ class "topbar" ]
            [ div [ class "topbar-left" ]
                [ a [ href "https://news.ycombinator.com", class "hn-logo" ] [ text "BS" ]
                , a [ href "https://ianchanning.com/hn", class "hnname" ] [ text "Better Signal News" ]
                , span [ class "pagetop", id "modeTabs" ] renderedTabs
                ]
            , div [ class "topbar-right" ]
                [ button
                    [ type_ "button"
                    , class
                        ("nav-btn topbar-toggle"
                            ++ (if model.labDrawerOpen then
                                    " active"

                                else
                                    ""
                               )
                        )
                    , id "exploreToggleBtn"
                    , attribute "aria-expanded"
                        (if model.labDrawerOpen then
                            "true"

                         else
                            "false"
                        )
                    , onClick ToggleLabDrawer
                    ]
                    [ text "explore" ]
                , text " | "
                , button
                    [ type_ "button"
                    , class
                        ("nav-btn topbar-toggle"
                            ++ (if model.proofDrawerOpen then
                                    " active"

                                else
                                    ""
                               )
                        )
                    , id "evidenceToggleBtn"
                    , attribute "aria-expanded"
                        (if model.proofDrawerOpen then
                            "true"

                         else
                            "false"
                        )
                    , onClick ToggleProofDrawer
                    ]
                    [ text "evidence" ]
                ]
            ]
        , div [ class "fatitem-box" ]
            [ div [ class "story-titleline" ]
                [ a [ class "story-title", href storyHref ] [ text payload.storyTitle ]
                , sitebitHtml
                ]
            , div [ class "subtext" ]
                [ span [ class "subline" ]
                    [ span [ class "score" ] [ text (String.fromInt payload.manifest.points ++ " points") ]
                    , text " by "
                    , a [ href ("https://news.ycombinator.com/user?id=" ++ payload.manifest.storyAuthor) ]
                        [ text payload.manifest.storyAuthor ]
                    , text " "
                    , span [ class "age" ] [ a [ href hnItemHref ] [ text ageStr ] ]
                    , text " | "
                    , a [ href hnItemHref ] [ text (formatThousands totalComments ++ " comments") ]
                    , text " | "
                    , text (formatFloat1 noisePct ++ "% bullshit")
                    ]
                ]
            ]
        ]
