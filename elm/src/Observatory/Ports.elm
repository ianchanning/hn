port module Observatory.Ports exposing (drawPlot, onCanvasProbe)

{-| Port declarations for canvas interop.

Outgoing: Elm sends PlotCommand to JS canvas renderer.
Incoming: JS sends CanvasProbeEvent when user clicks/hovers a point.

-}

import Json.Decode as Decode
import Json.Encode as Encode


port drawPlot : Encode.Value -> Cmd msg


port onCanvasProbe : (Decode.Value -> msg) -> Sub msg
