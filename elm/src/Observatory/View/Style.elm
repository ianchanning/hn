module Observatory.View.Style exposing (..)

{-| Zero-hash RGB-only colour constants and style helpers.

All colours use rgb()/rgba() — no hex `#` literals — to satisfy
the `assert "#" not in html_doc` invariant from the Python pipeline.

-}

import Html
import Html.Attributes exposing (style)
import Observatory.Types exposing (Colour, Tier(..))


{-| Convert Colour to CSS rgba() string. -}
colourToCss : Colour -> String
colourToCss c =
    if c.a >= 1.0 then
        "rgb("
            ++ String.fromInt c.r
            ++ ", "
            ++ String.fromInt c.g
            ++ ", "
            ++ String.fromInt c.b
            ++ ")"

    else
        "rgba("
            ++ String.fromInt c.r
            ++ ", "
            ++ String.fromInt c.g
            ++ ", "
            ++ String.fromInt c.b
            ++ ", "
            ++ String.fromFloat c.a
            ++ ")"


{-| Tier → border-left colour for comment cards. -}
tierBorderColour : Tier -> Colour
tierBorderColour tier =
    case tier of
        EpistemicGold ->
            Colour 0 158 96 1.0

        GroundedAnalysis ->
            Colour 16 98 188 1.0

        MemeOrSnark ->
            Colour 230 145 0 1.0

        BullshitOrFlamewar ->
            Colour 255 51 0 1.0

        DownvotedSink ->
            Colour 156 156 156 1.0

        CrowdChatter ->
            Colour 255 102 0 1.0


{-| Tier → scatter plot dot colour. -}
tierDotColour : Tier -> Colour
tierDotColour tier =
    case tier of
        EpistemicGold ->
            Colour 0 230 118 1.0

        GroundedAnalysis ->
            Colour 56 189 248 1.0

        CrowdChatter ->
            Colour 148 163 184 0.45

        MemeOrSnark ->
            Colour 255 179 0 1.0

        BullshitOrFlamewar ->
            Colour 255 68 0 0.72

        DownvotedSink ->
            Colour 110 118 128 0.45


{-| HN news.css downvote fade → text colour. -}
fadeToColour : String -> Colour
fadeToColour cls =
    case cls of
        "c00" ->
            Colour 0 0 0 1.0

        "c5A" ->
            Colour 90 90 90 1.0

        "c73" ->
            Colour 115 115 115 1.0

        "c88" ->
            Colour 136 136 136 1.0

        "c9c" ->
            Colour 156 156 156 1.0

        "cae" ->
            Colour 174 174 174 1.0

        "cbe" ->
            Colour 190 190 190 1.0

        "cce" ->
            Colour 206 206 206 1.0

        "cdd" ->
            Colour 221 221 221 1.0

        _ ->
            Colour 0 0 0 1.0



-- COMMON BRAND COLOURS


hnOrange : Colour
hnOrange =
    Colour 255 102 0 1.0


bgCream : Colour
bgCream =
    Colour 246 246 239 1.0


textGrey : Colour
textGrey =
    Colour 130 130 130 1.0
