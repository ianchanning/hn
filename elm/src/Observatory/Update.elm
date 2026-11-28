module Observatory.Update exposing (update)

{-| State transitions for all Msg variants.
-}

import Observatory.Model exposing (Model, recomputeLiveList)
import Observatory.Msg exposing (CanvasId(..), Msg(..), WeightField(..))
import Observatory.Ports as Ports
import Observatory.Types exposing (..)


update : Msg -> Model -> ( Model, Cmd Msg )
update msg model =
    case msg of
        SetMode mode ->
            let
                newModel =
                    { model
                        | activeMode = mode
                        , selectedCommentId = Nothing
                        , searchQuery = ""
                    }
            in
            ( newModel, Cmd.none )

        SearchInput q ->
            ( { model | searchQuery = q }, Cmd.none )

        FacetChanged slug ->
            ( { model | selectedFacet = slug }, Cmd.none )

        ClearFilter ->
            let
                newModel =
                    { model
                        | searchQuery = ""
                        , selectedCommentId = Nothing
                    }
            in
            ( newModel, Cmd.none )

        SliderChanged field val ->
            let
                cw =
                    model.currentWeights

                newCw =
                    case field of
                        WInfoGain ->
                            { cw | ig = val }

                        WFalsifiability ->
                            { cw | fa = val }

                        WGravityProgeny ->
                            { cw | gp = val }

                        WBullshitPenalty ->
                            { cw | bp = val }

                        WDownvotePenalty ->
                            { cw | dp = val }

                newLive =
                    case model.payload of
                        Just p ->
                            recomputeLiveList newCw p.comments

                        Nothing ->
                            model.liveList

                newModel =
                    { model | currentWeights = newCw, liveList = newLive }
            in
            ( newModel, Cmd.none )

        ResetWeights ->
            case model.payload of
                Just p ->
                    let
                        cw =
                            weightsToCurrentWeights p.weights

                        live =
                            recomputeLiveList cw p.comments

                        newModel =
                            { model | currentWeights = cw, liveList = live }
                    in
                    ( newModel, Cmd.none )

                Nothing ->
                    ( model, Cmd.none )

        CanvasProbeReceived probe ->
            let
                newModel =
                    { model
                        | selectedCommentId = Just probe.commentId
                        , searchQuery = String.fromInt probe.commentId
                    }
            in
            ( newModel, Cmd.none )

        CanvasProbeHovered probe ->
            ( { model | selectedCommentId = Just probe.commentId }, Cmd.none )

        ClearSelection ->
            let
                newModel =
                    { model
                        | selectedCommentId = Nothing
                        , searchQuery = ""
                    }
            in
            ( newModel, Cmd.none )

        ToggleProofDrawer ->
            ( { model | proofDrawerOpen = not model.proofDrawerOpen }, Cmd.none )

        ToggleLabDrawer ->
            ( { model | labDrawerOpen = not model.labDrawerOpen }, Cmd.none )

        ToggleTunerDrawer ->
            ( { model | tunerDrawerOpen = not model.tunerDrawerOpen }, Cmd.none )

        ToggleGravityDrawer ->
            ( { model | gravityDrawerOpen = not model.gravityDrawerOpen }, Cmd.none )

        ViewportChanged vp ->
            if vp == model.viewport then
                ( model, Cmd.none )

            else
                ( { model
                    | viewport = vp
                    , tunerDrawerOpen = vp == Desktop
                    , gravityDrawerOpen = vp == Desktop
                  }
                , Cmd.none
                )

        CanvasHover _ _ _ ->
            ( model, Cmd.none )

        CanvasClick _ _ _ ->
            ( model, Cmd.none )

        PayloadDecoded _ ->
            ( model, Cmd.none )

        NoOp ->
            ( model, Cmd.none )
