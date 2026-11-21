module DecodeTest exposing (..)

{-| Tests for JSON payload decoding — the most critical boundary.
-}

import Expect
import Json.Decode as Decode
import Observatory.Decode exposing (catalogDecoder, indexItemDecoder, payloadDecoder, routerConfigDecoder, tierDecoder)
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
        , describe "indexItemDecoder & catalogDecoder"
            [ test "decodes index item properly" <|
                \_ ->
                    let
                        raw =
                            """{"story_id": 50467087, "story_title": "Test Title", "points": 100, "story_author": "alice"}"""
                    in
                    case Decode.decodeString indexItemDecoder raw of
                        Ok it ->
                            it.storyId |> Expect.equal 50467087

                        Err _ ->
                            Expect.fail "failed to decode index item"
            , test "decodes catalog with items list" <|
                \_ ->
                    let
                        raw =
                            """{"updated_utc": "2026-11-21 09:00 UTC", "total_published": 1, "items": [{"story_id": 1, "story_title": "A"}]}"""
                    in
                    case Decode.decodeString catalogDecoder raw of
                        Ok cat ->
                            List.length cat.items |> Expect.equal 1

                        Err _ ->
                            Expect.fail "failed to decode catalog"
            ]
        , describe "routerConfigDecoder"
            [ test "decodes router config" <|
                \_ ->
                    let
                        raw =
                            """{"repo": "ian/hn", "actions_url": "https://example.com", "workflow_file": "run.yml"}"""
                    in
                    case Decode.decodeString routerConfigDecoder raw of
                        Ok cfg ->
                            cfg.repo |> Expect.equal "ian/hn"

                        Err _ ->
                            Expect.fail "failed to decode router config"
            ]
        ]
