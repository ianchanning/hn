module Observatory.Msg exposing (CanvasId(..), Msg(..), WeightField(..))

{-| All messages the Observatory app can process.
-}

import Json.Decode as Decode
import Observatory.Types exposing (CanvasProbeEvent, ObservatoryPayload, ViewMode, Viewport)


type Msg
    = PayloadDecoded (Result Decode.Error ObservatoryPayload)
    | SetMode ViewMode
    | SearchInput String
    | FacetChanged String
    | ClearFilter
    | SliderChanged WeightField Float
    | ResetWeights
    | CanvasHover CanvasId Float Float
    | CanvasClick CanvasId Float Float
    | CanvasProbeReceived CanvasProbeEvent
    | ClearSelection
    | ToggleProofDrawer
    | ToggleLabDrawer
    | ToggleTunerDrawer
    | ViewportChanged Viewport
    | NoOp


type WeightField
    = WInfoGain
    | WFalsifiability
    | WGravityProgeny
    | WBullshitPenalty
    | WDownvotePenalty


type CanvasId
    = PhaseCanvas
    | GravityCanvas
