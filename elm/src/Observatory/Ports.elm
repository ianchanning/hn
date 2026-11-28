module Observatory.Ports exposing
    ( computeGravityPlot
    , computePhasePlot
    )

{-| Plot coordinate computation for inline SVG scatter plots.
-}

import Observatory.Types exposing (..)
import Observatory.View.Style exposing (tierDotColour)


computePhasePlot : { a | liveList : List LiveComment, selectedCommentId : Maybe Int } -> ObservatoryPayload -> PlotCommand
computePhasePlot model _ =
    let
        width =
            420.0

        height =
            300.0

        maxX =
            16.5

        maxY =
            16.5

        pts =
            model.liveList
                |> List.map
                    (\lc ->
                        let
                            c =
                                lc.comment

                            x =
                                32.0 + min 1.0 (lc.liveEp / maxX) * (width - 52.0)

                            y =
                                (height - 26.0) - min 1.0 (lc.liveBs / maxY) * (height - 46.0)

                            r =
                                case c.tier of
                                    EpistemicGold ->
                                        4.2

                                    GroundedAnalysis ->
                                        2.8

                                    _ ->
                                        2.0

                            col =
                                tierDotColour c.tier
                        in
                        { x = x
                        , y = y
                        , radius = r
                        , colour = col
                        , commentId = c.id
                        }
                    )
    in
    { canvasId = "phaseCanvas"
    , points = pts
    , selectedId = model.selectedCommentId
    , axisConfig =
        { maxX = maxX
        , maxY = maxY
        , xLabel = "SIGNAL →"
        , yLabel = "↑ BULLSHIT"
        }
    , largestRoot = Nothing
    }


computeGravityPlot : { a | liveList : List LiveComment, selectedCommentId : Maybe Int } -> ObservatoryPayload -> PlotCommand
computeGravityPlot model payload =
    let
        width =
            420.0

        height =
            300.0

        totalN =
            max 1.0 (toFloat (List.length payload.comments))

        ages =
            payload.comments
                |> List.map .age
                |> List.sort

        p98Index =
            floor (0.98 * toFloat (max 0 (List.length ages - 1)))

        p98Age =
            ages
                |> List.drop p98Index
                |> List.head
                |> Maybe.withDefault 12.0

        maxAgePlot =
            max 4.0 (toFloat (ceiling p98Age))

        pts =
            model.liveList
                |> List.map
                    (\lc ->
                        let
                            c =
                                lc.comment

                            x =
                                32.0 + min 1.0 (c.age / maxAgePlot) * (width - 52.0)

                            y =
                                20.0 + min 1.0 (toFloat c.dom / totalN) * (height - 44.0)

                            ( col, r ) =
                                if c.tier == EpistemicGold then
                                    ( Colour 0 230 118 1.0, 4.2 )

                                else if c.surf >= 4.0 then
                                    ( Colour 255 179 0 1.0, 3.2 )

                                else if c.dt >= 2 || c.mod == 1 then
                                    ( Colour 255 68 0 0.7, 2.4 )

                                else
                                    ( Colour 148 163 184 0.3, 2.0 )
                        in
                        { x = x
                        , y = y
                        , radius = r
                        , colour = col
                        , commentId = c.id
                        }
                    )
    in
    { canvasId = "gravityCanvas"
    , points = pts
    , selectedId = model.selectedCommentId
    , axisConfig =
        { maxX = maxAgePlot
        , maxY = totalN
        , xLabel = "AGE (0..." ++ String.fromFloat maxAgePlot ++ "h) →"
        , yLabel = "↑ HN POS 1"
        }
    , largestRoot =
        if payload.largestRoot.slots > 1 then
            Just payload.largestRoot

        else
            Nothing
    }
