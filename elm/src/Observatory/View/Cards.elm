module Observatory.View.Cards exposing (viewCards)

{-| Comment card list with multi-mode filtering, search, and facet filtering.
-}

import Html exposing (Html, a, article, button, div, input, option, section, select, span, strong, text)
import Html.Attributes exposing (attribute, class, href, id, placeholder, selected, style, type_, value)
import Html.Events exposing (onClick, onInput)
import Observatory.Model exposing (Model)
import Observatory.Msg exposing (Msg(..))
import Observatory.Types exposing (CompactComment, LiveComment, ObservatoryPayload, ViewMode(..))
import Observatory.View.Style exposing (colourToCss, extractHost, formatFloat1, formatFloat2, formatThousands, tierBorderColour, tierToClass)


viewCards : Model -> ObservatoryPayload -> Html Msg
viewCards model payload =
    let
        totalComments =
            List.length payload.comments

        rescueJump =
            max 25 (min 150 (round (toFloat totalComments * 0.15)))

        demoteDrop =
            -(max 40 (min 300 (round (toFloat totalComments * 0.25))))

        q =
            String.toLower (String.trim model.searchQuery)

        pool =
            if not (String.isEmpty q) then
                let
                    cleanQ =
                        if String.startsWith "@" q then
                            String.dropLeft 1 q

                        else
                            q
                in
                model.liveList
                    |> List.filter
                        (\lc ->
                            let
                                c =
                                    lc.comment
                            in
                            String.fromInt c.id
                                == q
                                || String.contains cleanQ (String.toLower c.au)
                                || String.contains q (String.toLower c.txt)
                        )

            else
                case model.activeMode of
                    TopSignal ->
                        List.take 40 model.liveList

                    HnTop40 ->
                        model.liveList
                            |> List.sortBy (\lc -> lc.comment.dom)
                            |> List.take 40

                    BuriedGems ->
                        model.liveList
                            |> List.filter
                                (\lc ->
                                    lc.comment.dom > payload.buriedCutoff && lc.liveRank <= payload.rescueTopK
                                )

                    C5aRescues ->
                        model.liveList
                            |> List.filter
                                (\lc ->
                                    lc.comment.dt == 1 && lc.comment.ut >= 2
                                )

                    BullshitTraps ->
                        let
                            demoteFloor =
                                max 40 (round (toFloat totalComments * 0.4))

                            topCeil =
                                max 20 (round (toFloat totalComments * 0.15))
                        in
                        model.liveList
                            |> List.filter
                                (\lc ->
                                    let
                                        c =
                                            lc.comment
                                    in
                                    (c.meme > 0 && (c.k >= 5000 || List.length c.urls > 0))
                                        || (c.lu > 0 && List.length c.urls > 0)
                                        || (c.dom <= topCeil && lc.liveRank > demoteFloor)
                                )
                            |> List.take 40

                    ModMorgue ->
                        model.liveList
                            |> List.filter
                                (\lc ->
                                    lc.comment.mod == 1 || lc.comment.dt >= 2 || lc.comment.pp >= 4
                                )
                            |> List.take 40

        filteredByFacet =
            if model.selectedFacet == "all" then
                pool

            else
                List.filter (\lc -> lc.comment.facet == model.selectedFacet) pool

        shown =
            List.take 40 filteredByFacet

        facetOptionsHtml =
            option [ value "all", selected (model.selectedFacet == "all") ]
                [ text ("All Facets (" ++ formatThousands totalComments ++ ")") ]
                :: List.map
                    (\opt ->
                        option [ value opt.slug, selected (model.selectedFacet == opt.slug) ]
                            [ text (opt.label ++ " (" ++ String.fromInt opt.count ++ ")") ]
                    )
                    payload.facetOptions

        hasFilter =
            not (String.isEmpty model.searchQuery) || model.selectedCommentId /= Nothing
    in
    section [ class "band grid-12", id "explorerSection", style "padding-top" "16px" ]
        [ div [ class "col-12" ]
            [ div [ class "filter-bar" ]
                [ select
                    [ id "facetSelect"
                    , class "sel-in"
                    , attribute "aria-label" "Topic facet"
                    , onInput FacetChanged
                    ]
                    facetOptionsHtml
                , input
                    [ type_ "search"
                    , id "searchInput"
                    , class "search-in"
                    , placeholder ("Search " ++ formatThousands totalComments ++ " comments by text, author, or id...")
                    , value model.searchQuery
                    , onInput SearchInput
                    ]
                    []
                ]
            , div [ id "resultMeta", style "color" "rgb(90, 90, 88)", style "margin-bottom" "10px", style "padding" "0 8px" ]
                [ text (String.fromInt (List.length shown) ++ " of " ++ String.fromInt (List.length filteredByFacet) ++ " comments")
                , if hasFilter then
                    button
                        [ type_ "button"
                        , id "clearFilterBtn"
                        , class "tab-btn"
                        , style "padding" "2px 8px"
                        , style "box-shadow" "none"
                        , style "margin-left" "8px"
                        , onClick ClearFilter
                        ]
                        [ text "Clear" ]

                  else
                    text ""
                ]
            , div [ id "cardContainer", class "card-list" ]
                (List.map (viewCommentCard model rescueJump demoteDrop) shown)
            ]
        ]


viewCommentCard : Model -> Int -> Int -> LiveComment -> Html Msg
viewCommentCard model rescueJump demoteDrop lc =
    let
        c =
            lc.comment

        delta =
            c.dom - lc.liveRank

        deltaBadge =
            if delta >= rescueJump then
                span [ class "badge rescue" ] [ text ("RESCUED +" ++ String.fromInt delta ++ " SPOTS") ]

            else if delta <= demoteDrop then
                span [ class "badge drop" ] [ text ("DEMOTED " ++ String.fromInt delta ++ " SPOTS") ]

            else
                text ""

        fadeBadge =
            if c.dt == 1 then
                span [ class "badge c5a" ] [ text ("HN FADE: " ++ c.fade ++ " (RESCUED)") ]

            else if c.dt >= 2 then
                span [ class "badge drop" ] [ text ("HN FADE: " ++ c.fade ++ " (TIER " ++ String.fromInt c.dt ++ ")") ]

            else
                text ""

        modBadge =
            if c.mod == 1 then
                span [ class "badge drop" ] [ text "MOD REBUKED (dang/tomhow)" ]

            else
                text ""

        surfBadge =
            if c.surf >= 4.0 then
                span [ class "badge c5a" ] [ text ("SURF MIRAGE " ++ formatFloat1 c.surf ++ "x") ]

            else
                text ""

        facetLabel =
            if String.isEmpty c.flbl then
                String.replace "_" " " c.facet

            else
                c.flbl

        fadeClass =
            "comm-"
                ++ (if String.isEmpty c.fade then
                        "c00"

                    else
                        String.toLower c.fade
                   )

        cw =
            model.currentWeights

        borderColourStyle =
            style "border-left" ("4px solid " ++ colourToCss (tierBorderColour c.tier))
    in
    article [ class ("c-card tier-" ++ tierToClass c.tier), borderColourStyle ]
        [ div [ class "hn-comhead" ]
            [ a [ href ("https://news.ycombinator.com/user?id=" ++ c.au) ] [ text c.au ]
            , span [] [ text (" " ++ formatFloat1 c.age ++ " hours ago") ]
            , span [] [ text " | " ]
            , span [] [ text ("depth " ++ String.fromInt c.d) ]
            , span [] [ text " | " ]
            , span [] [ text ("karma " ++ formatThousands c.k ++ " (" ++ formatFloat1 c.kpp ++ "/post)") ]
            , span [] [ text " | " ]
            , a [ href ("https://news.ycombinator.com/item?id=" ++ String.fromInt c.id) ] [ text "link" ]
            ]
        , div [ class "c-meta" ]
            [ span [ class "badge rank-sig" ] [ text ("SIGNAL " ++ String.fromInt lc.liveRank) ]
            , span [ class "badge" ] [ text ("HN POS " ++ String.fromInt c.dom) ]
            , deltaBadge
            , fadeBadge
            , modBadge
            , surfBadge
            , span [ class "badge" ] [ text facetLabel ]
            ]
        , div [ class ("c-body " ++ fadeClass) ]
            (renderCommentBody c.txt)
        , div [ class "vec-bars" ]
            [ span [] [ text "SCORE: ", strong [] [ text (formatFloat2 lc.liveScore) ] ]
            , span [] [ text ("INFO: +" ++ formatFloat2 (cw.ig * c.ig)) ]
            , span [] [ text ("FALSIFIABILITY: +" ++ formatFloat2 (cw.fa * c.fa)) ]
            , span [] [ text ("GRAVITY/PRECISION: +" ++ formatFloat2 (cw.gp * c.gp)) ]
            , span [] [ text ("BULLSHIT LOAD: -" ++ formatFloat2 (cw.bp * c.bl)) ]
            , span [] [ text ("DOWNVOTE SINK: -" ++ formatFloat2 (cw.dp * c.ds)) ]
            , if List.isEmpty c.urls then
                text ""

              else
                span [] (text "LINKS: " :: List.map renderUrlLink c.urls)
            ]
        ]


renderUrlLink : String -> Html Msg
renderUrlLink url =
    let
        host =
            extractHost url
    in
    a
        [ class "ext-link"
        , href url
        , attribute "target" "_blank"
        , attribute "rel" "noopener noreferrer"
        , style "margin-right" "6px"
        ]
        [ text ("[" ++ host ++ "]") ]


renderCommentBody : String -> List (Html Msg)
renderCommentBody txt =
    let
        lines =
            String.split "\n" txt

        renderLine line isLast =
            let
                lineContent =
                    if String.startsWith ">" (String.trimLeft line) then
                        span [ class "hn-quote" ] [ text line ]

                    else
                        text line
            in
            if isLast then
                [ lineContent ]

            else
                [ lineContent, text "\n" ]
    in
    List.concat
        (List.indexedMap
            (\idx line ->
                renderLine line (idx == List.length lines - 1)
            )
            lines
        )
