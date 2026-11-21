module Observatory.Msg exposing (Msg(..), WeightField(..), CanvasId(..))

{-| All messages the Observatory app can process. -}

import Observatory.Types exposing (CanvasProbeEvent, ObservatoryPayload, ViewMode, Viewport)
import Json.Decode as Decode


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
