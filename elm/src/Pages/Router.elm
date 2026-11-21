module Pages.Router exposing (..)

{-| /item?id=<id> SPA router (replaces render_item_router_html in build_pages_site.py). Stub. -}

import Html exposing (Html)


type RouterState
    = ResolvingItem Int
    | ItemLoaded String
    | ItemNotBuilt Int
    | InvalidItemId


view : RouterState -> Html msg
view state =
    case state of
        ResolvingItem itemId ->
            Html.text ("Resolving HN item " ++ String.fromInt itemId ++ "...")

        ItemLoaded _ ->
            Html.text "Item loaded"

        ItemNotBuilt itemId ->
            Html.text ("HN item " ++ String.fromInt itemId ++ " not yet built")

        InvalidItemId ->
            Html.text "Invalid HN item ID"
