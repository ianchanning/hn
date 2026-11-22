module Observatory.View.Style exposing (..)

{-| Zero-hash RGB-only colour constants and style helpers.

All colours use rgb()/rgba() — no hex `#` literals — to satisfy
the `assert "#" not in html_doc` invariant from the Python pipeline.

-}

import Html
import Html.Attributes exposing (class, style, attribute)
import Observatory.Types exposing (Colour, Tier(..))


{-| ARIA role
-}
role : String -> Html.Attribute msg
role value =
    attribute "role" value


{-| Single `class` attribute, omitted entirely when the name is empty
    (avoids emitting a useless `class=""` in the rendered DOM).
-}
classIf : String -> List (Html.Attribute msg)
classIf name =
    if String.isEmpty name then
        []

    else
        [ class name ]

{-| Convert Colour to CSS rgba() string.
-}
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


{-| Tier → border-left colour for comment cards.
-}
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


{-| Tier → scatter plot dot colour.
-}
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


{-| Graduated fade ramp mapping bullshit load to news.css fade classes.
Clean comments remain crisp black (comm-c00), while comments with increasing
bullshit load fade to progressively lighter greys (comm-c5a .. comm-cdd).
Epistemic gold and grounded analysis comments remain crisp black.
-}
bullshitFadeClass : Tier -> Float -> String
bullshitFadeClass tier bl =
    case tier of
        EpistemicGold ->
            "comm-c00"

        GroundedAnalysis ->
            "comm-c00"

        _ ->
            if bl >= 3.5 then
                "comm-cdd"

            else if bl >= 3.0 then
                "comm-cce"

            else if bl >= 2.5 then
                "comm-cbe"

            else if bl >= 2.1 then
                "comm-cae"

            else if bl >= 1.7 then
                "comm-c9c"

            else if bl >= 1.3 then
                "comm-c88"

            else if bl >= 0.9 then
                "comm-c73"

            else if bl >= 0.5 || tier == BullshitOrFlamewar then
                "comm-c5a"

            else
                "comm-c00"


{-| HN news.css downvote fade → text colour.
-}
fadeToColour : String -> Colour
fadeToColour cls =
    case String.toLower cls of
        "c00" ->
            Colour 0 0 0 1.0

        "c5a" ->
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



-- FORMATTERS & STRING HELPERS


{-| Map Tier to class name matching Python HTML / CSS.
-}
tierToClass : Tier -> String
tierToClass tier =
    case tier of
        EpistemicGold ->
            "epistemic_gold"

        GroundedAnalysis ->
            "grounded_analysis"

        CrowdChatter ->
            "crowd_chatter"

        MemeOrSnark ->
            "meme_or_snark"

        BullshitOrFlamewar ->
            "bullshit_or_flamewar"

        DownvotedSink ->
            "downvoted_sink"


{-| Map Tier to readable label.
-}
tierToLabel : Tier -> String
tierToLabel tier =
    case tier of
        EpistemicGold ->
            "Epistemic Gold"

        GroundedAnalysis ->
            "Grounded Analysis"

        CrowdChatter ->
            "Crowd Chatter"

        MemeOrSnark ->
            "Meme or Snark"

        BullshitOrFlamewar ->
            "Bullshit or Flamewar"

        DownvotedSink ->
            "Downvoted Sink"


{-| Format a float to 1 decimal place.
-}
formatFloat1 : Float -> String
formatFloat1 val =
    let
        rounded =
            toFloat (round (val * 10)) / 10

        parts =
            String.split "." (String.fromFloat rounded)
    in
    case parts of
        [ whole ] ->
            whole ++ ".0"

        [ whole, frac ] ->
            whole ++ "." ++ String.left 1 frac

        _ ->
            String.fromFloat val


{-| Format a float to 2 decimal places.
-}
formatFloat2 : Float -> String
formatFloat2 val =
    let
        rounded =
            toFloat (round (val * 100)) / 100

        parts =
            String.split "." (String.fromFloat rounded)
    in
    case parts of
        [ whole ] ->
            whole ++ ".00"

        [ whole, frac ] ->
            if String.length frac == 1 then
                whole ++ "." ++ frac ++ "0"

            else
                whole ++ "." ++ String.left 2 frac

        _ ->
            String.fromFloat val


{-| Format a float to 3 decimal places.
-}
formatFloat3 : Float -> String
formatFloat3 val =
    let
        rounded =
            toFloat (round (val * 1000)) / 1000

        parts =
            String.split "." (String.fromFloat rounded)
    in
    case parts of
        [ whole ] ->
            whole ++ ".000"

        [ whole, frac ] ->
            whole ++ "." ++ String.padRight 3 '0' (String.left 3 frac)

        _ ->
            String.fromFloat val


{-| Format integer with comma thousands separators.
-}
formatThousands : Int -> String
formatThousands n =
    if n < 0 then
        "-" ++ formatThousands (abs n)

    else if n < 1000 then
        String.fromInt n

    else
        let
            remainder =
                modBy 1000 n

            quotient =
                n // 1000

            remStr =
                String.padLeft 3 '0' (String.fromInt remainder)
        in
        formatThousands quotient ++ "," ++ remStr


{-| Extract clean domain name from URL string.
-}
extractHost : String -> String
extractHost raw =
    let
        withoutScheme =
            if String.startsWith "https://" raw then
                String.dropLeft 8 raw

            else if String.startsWith "http://" raw then
                String.dropLeft 7 raw

            else
                raw

        hostOnly =
            case String.split "/" withoutScheme of
                h :: _ ->
                    h

                [] ->
                    withoutScheme

        withoutPort =
            case String.split ":" hostOnly of
                h :: _ ->
                    h

                [] ->
                    hostOnly
    in
    if String.startsWith "www." withoutPort then
        String.dropLeft 4 withoutPort

    else
        withoutPort
