module DecodeTest exposing (..)

{-| Tests for JSON payload decoding — the most critical boundary.
-}

import Expect
import Json.Decode as Decode
import Observatory.Decode exposing (payloadDecoder, tierDecoder)
import Observatory.Types exposing (Tier(..))
import Test exposing (..)


suite : Test
suite =
    describe "Observatory.Decode"
        [ describe "tierDecoder"
            [ test "decodes epistemic_gold" <|
                \_ ->
                    Decode.decodeString tierDecoder "\"epistemic_gold\""
                        |> Expect.equal (Ok EpistemicGold)
            , test "decodes bullshit_or_flamewar" <|
                \_ ->
                    Decode.decodeString tierDecoder "\"bullshit_or_flamewar\""
                        |> Expect.equal (Ok BullshitOrFlamewar)
            , test "decodes downvoted_sink" <|
                \_ ->
                    Decode.decodeString tierDecoder "\"downvoted_sink\""
                        |> Expect.equal (Ok DownvotedSink)
            , test "fails on unknown tier" <|
                \_ ->
                    Decode.decodeString tierDecoder "\"bogus_tier\""
                        |> Expect.err
            ]
        , describe "payloadDecoder"
            [ test "fails gracefully on empty object" <|
                \_ ->
                    Decode.decodeString payloadDecoder "{}"
                        |> Expect.err
            , test "fails on null" <|
                \_ ->
                    Decode.decodeString payloadDecoder "null"
                        |> Expect.err
            ]
        ]
