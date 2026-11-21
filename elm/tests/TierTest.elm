module TierTest exposing (..)

{-| Tests for Tier enum helpers and colour mappings. -}

import Expect
import Observatory.Types exposing (Tier(..))
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
        ]
