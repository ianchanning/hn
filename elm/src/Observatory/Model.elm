module Observatory.Model exposing (Flags, Model, init, initFromPayload, recomputeLiveList)

{-| Application model and initialisation.
-}

import Json.Decode as Decode
import Observatory.Decode as ObsDecode
import Observatory.Msg exposing (Msg(..))
import Observatory.Ports as Ports
import Observatory.Types exposing (..)


type alias Flags =
    Decode.Value


type alias Model =
    { payload : Maybe ObservatoryPayload
    , currentWeights : CurrentWeights
    , activeMode : ViewMode
    , searchQuery : String
    , selectedFacet : String
    , selectedCommentId : Maybe Int
    , liveList : List LiveComment
    , proofDrawerOpen : Bool
    , labDrawerOpen : Bool
    , tunerDrawerOpen : Bool
    , viewport : Viewport
    , error : Maybe String
    }


init : Flags -> ( Model, Cmd Msg )
init flags =
    case Decode.decodeValue ObsDecode.payloadDecoder flags of
        Ok payload ->
            initFromPayload payload

        Err err ->
            ( { payload = Nothing
              , currentWeights = { ig = 2.35, fa = 2.85, gp = 1.45, bp = 2.65, dp = 3.1 }
              , activeMode = TopSignal
              , searchQuery = ""
              , selectedFacet = "all"
              , selectedCommentId = Nothing
              , liveList = []
              , proofDrawerOpen = False
              , labDrawerOpen = False
              , tunerDrawerOpen = True
              , viewport = Desktop
              , error = Just (Decode.errorToString err)
              }
            , Cmd.none
            )


{-| Initialize directly from an already decoded ObservatoryPayload.
-}
initFromPayload : ObservatoryPayload -> ( Model, Cmd Msg )
initFromPayload payload =
    let
        cw =
            weightsToCurrentWeights payload.weights

        live =
            recomputeLiveList cw payload.comments

        m =
            { payload = Just payload
            , currentWeights = cw
            , activeMode = TopSignal
            , searchQuery = ""
            , selectedFacet = "all"
            , selectedCommentId = Nothing
            , liveList = live
            , proofDrawerOpen = False
            , labDrawerOpen = False
            , tunerDrawerOpen = True
            , viewport = Desktop
            , error = Nothing
            }
    in
    ( m, Ports.sendPlots m )


{-| Recompute live scores and ranks from current slider weights.
-}
recomputeLiveList : CurrentWeights -> List CompactComment -> List LiveComment
recomputeLiveList cw comments =
    comments
        |> List.map
            (\c ->
                let
                    pos =
                        cw.ig * c.ig + cw.fa * c.fa + cw.gp * c.gp

                    neg =
                        cw.bp * c.bl + cw.dp * c.ds

                    score =
                        pos - neg
                in
                { comment = c
                , liveScore = score
                , liveEp = max 0 pos
                , liveBs = max 0 neg
                , liveRank = 0
                }
            )
        |> List.sortBy (\lc -> negate lc.liveScore)
        |> List.indexedMap (\i lc -> { lc | liveRank = i + 1 })
