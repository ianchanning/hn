module Observatory.Subscriptions exposing (subscriptions)

{-| App subscriptions: canvas port events, viewport media queries. -}

import Json.Decode as Decode
import Observatory.Model exposing (Model)
import Observatory.Msg exposing (Msg(..))
import Observatory.Ports as Ports
import Observatory.Types exposing (CanvasProbeEvent)


subscriptions : Model -> Sub Msg
subscriptions _ =
    Ports.onCanvasProbe decodeProbe


decodeProbe : Decode.Value -> Msg
decodeProbe val =
    case Decode.decodeValue probeDecoder val of
        Ok probe ->
            CanvasProbeReceived probe

        Err _ ->
            NoOp


probeDecoder : Decode.Decoder CanvasProbeEvent
probeDecoder =
    Decode.map2 CanvasProbeEvent
        (Decode.field "canvasId" Decode.string)
        (Decode.field "commentId" Decode.int)
