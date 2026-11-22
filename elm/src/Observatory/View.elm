module Observatory.View exposing (view)

{-| Top-level view — renders the full observatory layout.

Delegates to sub-views in Observatory.View.\* modules.

-}

import Html exposing (Html, div, footer, span, text)
import Html.Attributes exposing (class, id)
import Observatory.Model exposing (Model)
import Observatory.Msg exposing (Msg)
import Observatory.Types exposing (ObservatoryPayload)
import Observatory.View.Cards exposing (viewCards)
import Observatory.View.Evidence exposing (viewEvidence)
import Observatory.View.Explore exposing (viewExplore)
import Observatory.View.Header exposing (viewHeader)
import Observatory.View.Style exposing (extractHost, role)


view : Model -> Html Msg
view model =
    case model.error of
        Just err ->
            div [ class "wrap" ]
                [ div [ class "topbar", role "banner" ]
                    [ text "Better Signal News" ]
                , div [ id "error" ]
                    [ text ("Payload decode error: " ++ err) ]
                ]

        Nothing ->
            case model.payload of
                Just payload ->
                    div [ class "wrap" ]
                        [ viewHeader model payload
                        , viewEvidence model payload
                        , viewExplore model payload
                        , viewCards model payload
                        , viewFooter payload
                        ]

                Nothing ->
                    div [ class "wrap" ]
                        [ text "Waiting for observatory payload..." ]


viewFooter : ObservatoryPayload -> Html Msg
viewFooter payload =
    let
        hostStr =
            if String.isEmpty payload.storyUrl then
                "NEWS.YCOMBINATOR.COM"

            else
                String.toUpper (extractHost payload.storyUrl)
    in
    footer [ class "sheet-foot", role "contentinfo" ]
        [ span [] [ text "SILICON PIRATE × CARBON PIRATE // ZERO-HASH DEFENSIVE ARTIFACT" ]
        , span [] [ text ("SOURCE: HN " ++ String.fromInt payload.storyId ++ " + " ++ hostStr ++ " + ALGOLIA + AUTHOR CACHE") ]
        ]
