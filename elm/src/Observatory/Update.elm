module Observatory.Update exposing (update)

{-| State transitions for all Msg variants. -}

import Observatory.Model exposing (Model, recomputeLiveList)
import Observatory.Msg exposing (Msg(..), WeightField(..))
import Observatory.Types exposing (..)


update : Msg -> Model -> ( Model, Cmd Msg )
update msg model =
    case msg of
        SetMode mode ->
            ( { model
                | activeMode = mode
                , selectedCommentId = Nothing
                , searchQuery = ""
              }
            , Cmd.none
            )

        SearchInput q ->
            ( { model | searchQuery = q }, Cmd.none )

        FacetChanged slug ->
            ( { model | selectedFacet = slug }, Cmd.none )

        ClearFilter ->
            ( { model
                | searchQuery = ""
                , selectedCommentId = Nothing
              }
            , Cmd.none
            )

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
            in
            ( { model | currentWeights = newCw, liveList = newLive }, Cmd.none )

        ResetWeights ->
            case model.payload of
                Just p ->
                    let
                        cw =
                            weightsToCurrentWeights p.weights

                        live =
                            recomputeLiveList cw p.comments
                    in
                    ( { model | currentWeights = cw, liveList = live }, Cmd.none )

                Nothing ->
                    ( model, Cmd.none )

        CanvasProbeReceived probe ->
            ( { model | selectedCommentId = Just probe.commentId }, Cmd.none )

        ClearSelection ->
            ( { model | selectedCommentId = Nothing, searchQuery = "" }, Cmd.none )

        ToggleProofDrawer ->
            ( { model | proofDrawerOpen = not model.proofDrawerOpen }, Cmd.none )

        ToggleLabDrawer ->
            ( { model | labDrawerOpen = not model.labDrawerOpen }, Cmd.none )

        ToggleTunerDrawer ->
            ( { model | tunerDrawerOpen = not model.tunerDrawerOpen }, Cmd.none )

        ViewportChanged vp ->
            ( { model | viewport = vp }, Cmd.none )

        _ ->
            ( model, Cmd.none )
