module Observatory.View exposing (view)

{-| Top-level view — renders the full observatory layout.

Delegates to sub-views in Observatory.View.* modules.
Stub: will be filled during the Elm rewrite.

-}

import Html exposing (Html, div, text)
import Html.Attributes exposing (class, id)
import Observatory.Model exposing (Model)
import Observatory.Msg exposing (Msg)


view : Model -> Html Msg
view model =
    case model.error of
        Just err ->
            div [ class "wrap" ]
                [ div [ class "topbar" ]
                    [ text "HN Epistemic Observatory — Elm" ]
                , div [ id "error" ]
                    [ text ("Payload decode error: " ++ err) ]
                ]

        Nothing ->
            div [ class "wrap" ]
                [ text "Observatory loaded — view implementation pending"
                ]
