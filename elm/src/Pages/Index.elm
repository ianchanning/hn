module Pages.Index exposing (IndexModel, view)

{-| Front-page HN-style item list (replaces render\_index\_html in build\_pages\_site.py).
-}

import Html exposing (Html, a, div, footer, span, table, tbody, td, text, tr)
import Html.Attributes exposing (attribute, class, colspan, href, style)
import Observatory.Types exposing (IndexItem)
import Observatory.View.Style exposing (extractHost, formatFloat1, formatThousands)


type alias IndexModel =
    { items : List IndexItem
    , frontpageIds : List Int
    , updatedUtc : String
    , repo : String
    , actionsUrl : String
    , workflowFile : String
    }


view : IndexModel -> Html msg
view model =
    let
        byStoryId id =
            model.items
                |> List.filter (\it -> it.storyId == id)
                |> List.head

        orderedItems =
            if List.isEmpty model.frontpageIds then
                model.items

            else
                let
                    fpItems =
                        List.filterMap byStoryId model.frontpageIds
                in
                if List.isEmpty fpItems then
                    model.items

                else
                    fpItems

        itemRows =
            if List.isEmpty orderedItems then
                [ tr []
                    [ td [ colspan 2, class "empty-msg" ]
                        [ text "No stories built yet. Run the GitHub Actions frontpage workflow or paste an item ID." ]
                    ]
                ]

            else
                List.concat
                    (List.indexedMap
                        (\idx item ->
                            renderItemRow (idx + 1) item
                        )
                        orderedItems
                    )

        publishedCount =
            List.length model.items
    in
    div [ class "hnmain" ]
        [ div [ class "topbar" ]
            [ div [ class "topbar-left" ]
                [ a [ class "hn-logo", href "./" ] [ text "BS" ]
                , a [ class "hnname", href "./" ] [ text "Better Signal News" ]
                ]
            , div [ class "topbar-right" ]
                [ text
                    (if String.isEmpty model.updatedUtc then
                        "hourly updates"

                     else
                        model.updatedUtc
                    )
                ]
            ]
        , table [ class "itemlist", style "border" "0", style "padding" "10px 8px 8px 8px" ]
            [ tbody [] itemRows ]
        , footer [ class "sheet-foot" ]
            [ span []
                [ text "Hourly updates | "
                , text (String.fromInt publishedCount ++ " published | ")
                , a [ href "https://news.ycombinator.com/" ] [ text "news.ycombinator.com" ]
                ]
            , span []
                [ text "ZERO-HASH DEFENSIVE ARTIFACT" ]
            ]
        ]


renderItemRow : Int -> IndexItem -> List (Html msg)
renderItemRow rank it =
    let
        itemHref =
            "./item?id=" ++ String.fromInt it.storyId

        hasExtUrl =
            not (String.isEmpty it.storyUrl)

        extHref =
            it.storyUrl

        siteHost =
            extractHost it.storyUrl

        ( titleLink, sitebitHtml ) =
            if hasExtUrl then
                ( a [ class "storylink", href extHref ] [ text it.storyTitle ]
                , span [ class "sitebit comhead" ]
                    [ text " ("
                    , a [ href extHref ] [ text siteHost ]
                    , text ")"
                    ]
                )

            else
                ( a [ class "storylink", href itemHref ] [ text it.storyTitle ]
                , text ""
                )

        useful =
            it.epistemicGold + it.groundedAnalysis

        bsPct =
            if it.totalComments > 0 then
                max 0.0 (100.0 - (100.0 * toFloat useful / toFloat (max 1 it.totalComments)))

            else
                0.0

        subtextBits =
            [ span []
                [ text
                    (String.fromInt it.points
                        ++ (if it.points == 1 then
                                " point by "

                            else
                                " points by "
                           )
                        ++ it.storyAuthor
                    )
                ]
            , text " | "
            , a [ href itemHref ]
                [ text (formatThousands it.totalComments ++ " comments") ]
            , text " | "
            , a [ href itemHref ]
                [ text (String.fromInt it.epistemicGold ++ " gold · " ++ formatFloat1 bsPct ++ "% bullshit") ]
            , text " | "
            , a [ href ("https://news.ycombinator.com/item?id=" ++ String.fromInt it.storyId) ]
                [ text "hn" ]
            ]
    in
    [ tr [ class "athing" ]
        [ td [ class "title rank" ] [ text (String.fromInt rank ++ ".") ]
        , td [ class "title" ]
            [ span [ class "titleline" ] [ titleLink, sitebitHtml ] ]
        ]
    , tr []
        [ td [] []
        , td [ class "subtext" ] subtextBits
        ]
    , tr [ class "spacer" ]
        [ td [ colspan 2 ] [] ]
    ]
