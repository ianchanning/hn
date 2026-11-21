module TierTest exposing (..)

{-| Tests for Tier enum helpers and colour mappings.
-}

import Expect
import Observatory.Types exposing (Tier(..))
import Observatory.View.Style exposing (bullshitFadeClass)
import Test exposing (..)


suite : Test
suite =
    describe "Tier"
        [ test "all six constructors exist" <|
            \_ ->
                let
                    allTiers =
                        [ EpistemicGold
                        , GroundedAnalysis
                        , CrowdChatter
                        , MemeOrSnark
                        , BullshitOrFlamewar
                        , DownvotedSink
                        ]
                in
                List.length allTiers
                    |> Expect.equal 6
        , describe "bullshitFadeClass graduated ramp"
            [ test "epistemic gold is always comm-c00" <|
                \_ ->
                    bullshitFadeClass EpistemicGold 3.8
                        |> Expect.equal "comm-c00"
            , test "grounded analysis is always comm-c00" <|
                \_ ->
                    bullshitFadeClass GroundedAnalysis 2.5
                        |> Expect.equal "comm-c00"
            , test "clean crowd chatter with zero bullshit is comm-c00" <|
                \_ ->
                    bullshitFadeClass CrowdChatter 0.0
                        |> Expect.equal "comm-c00"
            , test "low bullshit crowd chatter (0.2) is comm-c00" <|
                \_ ->
                    bullshitFadeClass CrowdChatter 0.2
                        |> Expect.equal "comm-c00"
            , test "crowd chatter with moderate bullshit scales up ramp" <|
                \_ ->
                    [ bullshitFadeClass CrowdChatter 0.6
                    , bullshitFadeClass CrowdChatter 1.0
                    , bullshitFadeClass CrowdChatter 1.4
                    , bullshitFadeClass CrowdChatter 1.8
                    , bullshitFadeClass CrowdChatter 2.2
                    , bullshitFadeClass CrowdChatter 2.7
                    , bullshitFadeClass CrowdChatter 3.2
                    , bullshitFadeClass CrowdChatter 4.0
                    ]
                        |> Expect.equal
                            [ "comm-c5a"
                            , "comm-c73"
                            , "comm-c88"
                            , "comm-c9c"
                            , "comm-cae"
                            , "comm-cbe"
                            , "comm-cce"
                            , "comm-cdd"
                            ]
            , test "bullshit_or_flamewar tier is at least comm-c5a even with low bl" <|
                \_ ->
                    bullshitFadeClass BullshitOrFlamewar 0.1
                        |> Expect.equal "comm-c5a"
            , test "bullshit_or_flamewar tier scales to comm-cdd with high bl" <|
                \_ ->
                    bullshitFadeClass BullshitOrFlamewar 3.6
                        |> Expect.equal "comm-cdd"
            ]
        ]
