port module Main exposing (main)

{-| HN Epistemic Observatory — Elm entry point.

Consumes the observatory JSON payload embedded in the HTML by Python
and renders the full interactive display layer.

-}

import Browser
import Json.Decode as Decode
import Observatory.Decode as Decode
import Observatory.Model exposing (Model, Flags, init)
import Observatory.Msg exposing (Msg(..))
import Observatory.Subscriptions exposing (subscriptions)
import Observatory.Update exposing (update)
import Observatory.View exposing (view)


main : Program Decode.Value Model Msg
main =
    Browser.element
        { init = init
        , update = update
        , subscriptions = subscriptions
        , view = view
        }
