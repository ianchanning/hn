module Observatory.Subscriptions exposing (subscriptions)

{-| App subscriptions.
-}

import Observatory.Model exposing (Model)
import Observatory.Msg exposing (Msg)


subscriptions : Model -> Sub Msg
subscriptions _ =
    Sub.none
