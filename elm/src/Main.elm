module Main exposing (main)

{-| HN Epistemic Observatory — Elm entry point.

Consumes either:
1. Observatory JSON payload (embedded in HTML by Python or static comments fixture)
2. Catalog JSON payload (Index item list)
3. Router configuration (SPA router)

-}

import Browser
import Html exposing (Html, div, text)
import Html.Attributes exposing (class, id)
import Json.Decode as Decode
import Observatory.Decode as ObsDecode
import Observatory.Model as ObsModel
import Observatory.Msg as ObsMsg
import Observatory.Subscriptions as ObsSubs
import Observatory.Types exposing (RouterConfig, RouterState(..))
import Observatory.Update as ObsUpdate
import Observatory.View as ObsView
import Pages.Index as PagesIndex
import Pages.Router as PagesRouter


type RootModel
    = ObservatoryModel ObsModel.Model
    | IndexModel PagesIndex.IndexModel
    | RouterModel RouterState
    | DecodeError String


type RootMsg
    = ObservatoryMsg ObsMsg.Msg


main : Program Decode.Value RootModel RootMsg
main =
    Browser.element
        { init = init
        , update = update
        , subscriptions = subscriptions
        , view = view
        }


init : Decode.Value -> ( RootModel, Cmd RootMsg )
init flags =
    case Decode.decodeValue ObsDecode.payloadDecoder flags of
        Ok _ ->
            let
                ( obsModel, obsCmd ) =
                    ObsModel.init flags
            in
            ( ObservatoryModel obsModel, Cmd.map ObservatoryMsg obsCmd )

        Err obsErr ->
            case Decode.decodeValue ObsDecode.catalogDecoder flags of
                Ok catalog ->
                    let
                        indexModel =
                            { items = catalog.items
                            , frontpageIds = catalog.frontpageIds
                            , updatedUtc = catalog.updatedUtc
                            , repo = "ian/hn"
                            , actionsUrl = ""
                            , workflowFile = "hn-observatory-pages.yml"
                            }
                    in
                    ( IndexModel indexModel, Cmd.none )

                Err _ ->
                    case Decode.decodeValue ObsDecode.routerConfigDecoder flags of
                        Ok cfg ->
                            ( RouterModel (ItemNotBuilt 50467087 cfg), Cmd.none )

                        Err _ ->
                            ( DecodeError (Decode.errorToString obsErr), Cmd.none )


update : RootMsg -> RootModel -> ( RootModel, Cmd RootMsg )
update msg rootModel =
    case ( msg, rootModel ) of
        ( ObservatoryMsg obsMsg, ObservatoryModel obsModel ) ->
            let
                ( newObsModel, obsCmd ) =
                    ObsUpdate.update obsMsg obsModel
            in
            ( ObservatoryModel newObsModel, Cmd.map ObservatoryMsg obsCmd )

        _ ->
            ( rootModel, Cmd.none )


subscriptions : RootModel -> Sub RootMsg
subscriptions rootModel =
    case rootModel of
        ObservatoryModel obsModel ->
            Sub.map ObservatoryMsg (ObsSubs.subscriptions obsModel)

        _ ->
            Sub.none


view : RootModel -> Html RootMsg
view rootModel =
    case rootModel of
        ObservatoryModel obsModel ->
            Html.map ObservatoryMsg (ObsView.view obsModel)

        IndexModel idxModel ->
            PagesIndex.view idxModel

        RouterModel rState ->
            PagesRouter.view rState

        DecodeError err ->
            div [ class "wrap" ]
                [ div [ class "topbar" ]
                    [ text "HN Epistemic Observatory — Elm" ]
                , div [ id "error" ]
                    [ text ("Payload decode error: " ++ err) ]
                ]
