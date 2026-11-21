module Pages.Index exposing (..)

{-| Front-page HN-style item list (replaces render_index_html in build_pages_site.py). Stub. -}

import Html exposing (Html)


type alias IndexModel =
    { items : List ()  -- TODO: use IndexItem from Types
    , frontpageIds : List Int
    , updatedUtc : String
    }


view : IndexModel -> Html msg
view _ =
    Html.text "Index page — pending implementation"
