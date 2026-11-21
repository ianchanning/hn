port module Observatory.Ports exposing
    ( computeGravityPlot
    , computePhasePlot
    , drawPlot
    , encodePlotCommand
    , onCanvasProbe
    , sendPlot
    , sendPlots
    )

{-| Port declarations for canvas interop.

Outgoing: Elm sends PlotCommand to JS canvas renderer.
Incoming: JS sends CanvasProbeEvent when user clicks/hovers a point.

-}

import Json.Decode as Decode
import Json.Encode as Encode
import Observatory.Types exposing (..)
import Observatory.View.Style exposing (tierDotColour)


port drawPlot : Encode.Value -> Cmd msg


port onCanvasProbe : (Decode.Value -> msg) -> Sub msg


encodePlotCommand : PlotCommand -> Encode.Value
encodePlotCommand cmd =
    Encode.object
        [ ( "canvasId", Encode.string cmd.canvasId )
        , ( "points", Encode.list encodePlotPoint cmd.points )
        , ( "selectedId"
          , case cmd.selectedId of
                Just id ->
                    Encode.int id

                Nothing ->
                    Encode.null
          )
        , ( "axisConfig", encodeAxisConfig cmd.axisConfig )
        , ( "largestRoot"
          , case cmd.largestRoot of
                Just lr ->
                    encodeLargestRoot lr

                Nothing ->
                    Encode.null
          )
        ]


encodePlotPoint : PlotPoint -> Encode.Value
encodePlotPoint pt =
    Encode.object
        [ ( "x", Encode.float pt.x )
        , ( "y", Encode.float pt.y )
        , ( "radius", Encode.float pt.radius )
        , ( "colour", encodeColour pt.colour )
        , ( "commentId", Encode.int pt.commentId )
        ]


encodeColour : Colour -> Encode.Value
encodeColour c =
    Encode.object
        [ ( "r", Encode.int c.r )
        , ( "g", Encode.int c.g )
        , ( "b", Encode.int c.b )
        , ( "a", Encode.float c.a )
        ]


encodeAxisConfig : AxisConfig -> Encode.Value
encodeAxisConfig cfg =
    Encode.object
        [ ( "maxX", Encode.float cfg.maxX )
        , ( "maxY", Encode.float cfg.maxY )
        , ( "xLabel", Encode.string cfg.xLabel )
        , ( "yLabel", Encode.string cfg.yLabel )
        ]


encodeLargestRoot : LargestRoot -> Encode.Value
encodeLargestRoot lr =
    Encode.object
        [ ( "rootId", Encode.int lr.rootId )
        , ( "author", Encode.string lr.author )
        , ( "slots", Encode.int lr.slots )
        , ( "startDom", Encode.int lr.startDom )
        , ( "endDom", Encode.int lr.endDom )
        , ( "sharePct", Encode.float lr.sharePct )
        , ( "topDom1Age", Encode.float lr.topDom1Age )
        , ( "topDom1Author", Encode.string lr.topDom1Author )
        ]


sendPlot : PlotCommand -> Cmd msg
sendPlot cmd =
    drawPlot (encodePlotCommand cmd)


computePhasePlot : { a | liveList : List LiveComment, selectedCommentId : Maybe Int } -> ObservatoryPayload -> PlotCommand
computePhasePlot model _ =
    let
        width =
            540.0

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
        , xLabel = "EPISTEMIC POTENTIAL (INFO + FALSIFIABILITY) ->"
        , yLabel = "BULLSHIT / SINK LOAD ^"
        }
    , largestRoot = Nothing
    }


computeGravityPlot : { a | liveList : List LiveComment, selectedCommentId : Maybe Int } -> ObservatoryPayload -> PlotCommand
computeGravityPlot model payload =
    let
        width =
            540.0

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
        , xLabel = "COMMENT AGE IN HOURS (0h -> " ++ String.fromFloat maxAgePlot ++ "h) ->"
        , yLabel = "HN POS 1 (TOP)"
        }
    , largestRoot =
        if payload.largestRoot.slots > 1 then
            Just payload.largestRoot

        else
            Nothing
    }


sendPlots : { a | liveList : List LiveComment, selectedCommentId : Maybe Int, payload : Maybe ObservatoryPayload } -> Cmd msg
sendPlots model =
    case model.payload of
        Just p ->
            Cmd.batch
                [ sendPlot (computePhasePlot model p)
                , sendPlot (computeGravityPlot model p)
                ]

        Nothing ->
            Cmd.none
