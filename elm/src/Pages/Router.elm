module Pages.Router exposing (view)

{-| /item?id=<id> SPA router (replaces render\_item\_router\_html in build\_pages\_site.py).
-}

import Html exposing (Html, a, code, div, header, p, pre, text)
import Html.Attributes exposing (class, href, id)
import Observatory.Types exposing (RouterConfig, RouterState(..))


view : RouterState -> Html msg
view state =
    div [ class "wrap" ]
        [ header [ class "hn-header" ]
            [ div [ class "topbar" ]
                [ div [ class "topbar-left" ]
                    [ a [ class "hn-logo", href "./" ] [ text "BS" ]
                    , a [ class "hnname", href "./" ] [ text "Better Signal News" ]
                    ]
                , div [ class "topbar-right" ] [ text "NYX OBSERVATORY // HN URI MIRROR" ]
                ]
            , viewStateContent state
            ]
        ]


viewStateContent : RouterState -> Html msg
viewStateContent state =
    case state of
        ResolvingItem itemId ->
            div [ class "fatitem-box", id "routerStatus" ]
                [ div [ class "story-titleline", id "statusTitle" ] [ text "Loading Better Signal News..." ]
                , div [ class "subtext", id "statusBody" ]
                    [ text "Resolving "
                    , code [] [ text ("/item?id=" ++ String.fromInt itemId) ]
                    , text " from static observatory archive."
                    ]
                ]

        ItemLoaded _ ->
            div [ class "fatitem-box", id "routerStatus" ]
                [ div [ class "story-titleline", id "statusTitle" ] [ text "Observatory Loaded" ]
                ]

        ItemNotBuilt itemId cfg ->
            let
                hnUrl =
                    "https://news.ycombinator.com/item?id=" ++ String.fromInt itemId

                cliCommand =
                    "gh workflow run "
                        ++ cfg.workflowFile
                        ++ " -f target="
                        ++ String.fromInt itemId
                        ++ "\nuv run --no-project python hn-comments/cli.py "
                        ++ String.fromInt itemId
                        ++ " --open"

                actionBtns =
                    (if String.isEmpty cfg.actionsUrl then
                        []

                     else
                        [ a [ href cfg.actionsUrl ] [ text "github workflows" ] ]
                    )
            in
            div [ class "fatitem-box", id "routerStatus" ]
                [ div [ class "story-titleline", id "statusTitle" ]
                    [ a [ class "story-title", href hnUrl ] [ text ("HN Item " ++ String.fromInt itemId ++ " Not Yet Built") ] ]
                , div [ class "subtext", id "statusBody" ]
                    [ text "No pre-built observatory was found at "
                    , code [] [ text ("/items/" ++ String.fromInt itemId ++ ".html") ]
                    , text ". Trigger the GitHub Actions workflow with item ID "
                    , code [] [ text (String.fromInt itemId) ]
                    , text " to publish "
                    , code [] [ text ("/item?id=" ++ String.fromInt itemId) ]
                    , text ":"
                    ]
                , pre [] [ text cliCommand ]
                , div [ class "subtext" ] actionBtns
                ]

        InvalidItemId ->
            div [ class "fatitem-box", id "routerStatus" ]
                [ div [ class "story-titleline", id "statusTitle" ]
                    [ text "Missing or Invalid Hacker News Item ID" ]

                , div [ class "subtext", id "statusBody" ]
                    [ text "Append "
                    , code [] [ text "?id=50472038" ]
                    , text " just like Hacker News ("
                    , code [] [ text "/item?id=50472038" ]
                    , text "), or browse the published index."
                    ]
                , div [ class "actions" ]
                    [ a [ class "btn", href "./" ] [ text "Open Published Index" ] ]
                ]
