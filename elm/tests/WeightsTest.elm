module WeightsTest exposing (..)

{-| Tests for weight recomputation logic.
-}

import Expect
import Observatory.Model exposing (recomputeLiveList)
import Observatory.Types exposing (..)
import Test exposing (..)


mockComment : Int -> Float -> Float -> Float -> CompactComment
mockComment id igVal faVal blVal =
    { id = id
    , au = "testuser"
    , dom = id
    , sr = id
    , sc = 0.0
    , ep = 0.0
    , bs = 0.0
    , d = 0
    , age = 1.0
    , grav = 3.0
    , surf = 0.0
    , fade = "c00"
    , dt = 0
    , ut = 0
    , lu = 0
    , w = 50
    , qw = 0
    , k = 100
    , kpp = 10.0
    , td = 0.0
    , mod = 0
    , pp = 0
    , meme = 0
    , tier = CrowdChatter
    , facet = "general_commentary"
    , flbl = "General Commentary"
    , urls = []
    , ig = igVal
    , fa = faVal
    , gp = 0.0
    , bl = blVal
    , ds = 0.0
    , txt = "Test comment body"
    }


suite : Test
suite =
    describe "Observatory.Model.recomputeLiveList"
        [ test "ranks higher info-gain comment first" <|
            \_ ->
                let
                    cw =
                        { ig = 1.0, fa = 1.0, gp = 0.0, bp = 0.0, dp = 0.0 }

                    comments =
                        [ mockComment 1 0.5 0.0 0.0
                        , mockComment 2 2.0 0.0 0.0
                        ]

                    result =
                        recomputeLiveList cw comments
                in
                result
                    |> List.head
                    |> Maybe.map (\lc -> lc.comment.id)
                    |> Expect.equal (Just 2)
        , test "bullshit penalty demotes high-load comments" <|
            \_ ->
                let
                    cw =
                        { ig = 1.0, fa = 0.0, gp = 0.0, bp = 2.0, dp = 0.0 }

                    comments =
                        [ mockComment 1 1.0 0.0 5.0 -- high BS load
                        , mockComment 2 1.0 0.0 0.0 -- clean
                        ]

                    result =
                        recomputeLiveList cw comments
                in
                result
                    |> List.head
                    |> Maybe.map (\lc -> lc.comment.id)
                    |> Expect.equal (Just 2)
        , test "assigns 1-based liveRank" <|
            \_ ->
                let
                    cw =
                        { ig = 1.0, fa = 0.0, gp = 0.0, bp = 0.0, dp = 0.0 }

                    comments =
                        [ mockComment 1 3.0 0.0 0.0
                        , mockComment 2 1.0 0.0 0.0
                        ]

                    result =
                        recomputeLiveList cw comments
                in
                result
                    |> List.map .liveRank
                    |> Expect.equal [ 1, 2 ]
        ]
