module Main exposing (main)

{-| HN Epistemic Observatory — Elm entry point.

Consumes:
- Single-page production payload (ObservatoryPayload from build_dashboard.py)
- Single-page Pages payload (Catalog or RouterConfig from build_pages_site.py)
- Multi-page dev payload containing { observatory, catalog, router, page }
-}

import Browser
import Html exposing (Html, div, span, text)
import Html.Attributes exposing (class, id, style)
import Html.Events exposing (onClick)
import Json.Decode as Decode
import Observatory.Decode as ObsDecode
import Observatory.Model as ObsModel
import Observatory.Msg as ObsMsg
import Observatory.Ports as Ports
import Observatory.Subscriptions as ObsSubs
import Observatory.Types exposing (Catalog, ObservatoryPayload, RouterConfig, RouterState(..))
import Observatory.Update as ObsUpdate
import Observatory.View as ObsView
import Pages.Index as PagesIndex
import Pages.Router as PagesRouter


type ActiveTab
    = TabObservatory
    | TabIndex
    | TabRouter


type alias DevBundle =
    { activeTab : ActiveTab
    , obsModel : Maybe ObsModel.Model
    , indexModel : Maybe PagesIndex.IndexModel
    , routerState : Maybe RouterState
    }


type RootModel
    = ProductionObservatory ObsModel.Model
    | ProductionIndex PagesIndex.IndexModel
    | ProductionRouter RouterState
    | DevMode DevBundle
    | DecodeError String


type RootMsg
    = ObservatoryMsg ObsMsg.Msg
    | SwitchDevTab ActiveTab


main : Program Decode.Value RootModel RootMsg
main =
    Browser.element
        { init = init
        , update = update
        , subscriptions = subscriptions
        , view = view
        }


type alias RawDevBundle =
    { observatory : Maybe ObservatoryPayload
    , catalog : Maybe Catalog
    , router : Maybe RouterConfig
    , page : String
    }


devBundleDecoder : Decode.Decoder RawDevBundle
devBundleDecoder =
    Decode.map4 RawDevBundle
        (Decode.maybe (Decode.field "observatory" ObsDecode.payloadDecoder))
        (Decode.maybe (Decode.field "catalog" ObsDecode.catalogDecoder))
        (Decode.maybe (Decode.field "router" ObsDecode.routerConfigDecoder))
        (Decode.oneOf [ Decode.field "page" Decode.string, Decode.succeed "observatory" ])


init : Decode.Value -> ( RootModel, Cmd RootMsg )
init flags =
    case Decode.decodeValue devBundleDecoder flags of
        Ok rawBundle ->
            case rawBundle.observatory of
                Just obsPayload ->
                    let
                        ( om, obsCmd ) =
                            ObsModel.initFromPayload obsPayload

                        im =
                            case rawBundle.catalog of
                                Just cat ->
                                    Just
                                        { items = cat.items
                                        , frontpageIds = cat.frontpageIds
                                        , updatedUtc = cat.updatedUtc
                                        , repo = "ianchanning/hn"
                                        , actionsUrl = ""
                                        , workflowFile = "hn-observatory-pages.yml"
                                        }

                                Nothing ->
                                    Nothing

                        rs =
                            case rawBundle.router of
                                Just cfg ->
                                    Just (ItemNotBuilt 50467087 cfg)

                                Nothing ->
                                    Nothing

                        tab =
                            case rawBundle.page of
                                "catalog" ->
                                    TabIndex

                                "index" ->
                                    TabIndex

                                "router" ->
                                    TabRouter

                                _ ->
                                    TabObservatory

                        bundle =
                            { activeTab = tab
                            , obsModel = Just om
                            , indexModel = im
                            , routerState = rs
                            }

                        initCmd =
                            if tab == TabObservatory then
                                Cmd.map ObservatoryMsg obsCmd

                            else
                                Cmd.none
                    in
                    ( DevMode bundle, initCmd )

                Nothing ->
                    initSinglePayload flags

        Err _ ->
            initSinglePayload flags


initSinglePayload : Decode.Value -> ( RootModel, Cmd RootMsg )
initSinglePayload flags =
            case Decode.decodeValue ObsDecode.payloadDecoder flags of
                Ok _ ->
                    let
                        ( obsModel, obsCmd ) =
                            ObsModel.init flags
                    in
                    ( ProductionObservatory obsModel, Cmd.map ObservatoryMsg obsCmd )

                Err obsErr ->
                    case Decode.decodeValue ObsDecode.catalogDecoder flags of
                        Ok catalog ->
                            let
                                indexModel =
                                    { items = catalog.items
                                    , frontpageIds = catalog.frontpageIds
                                    , updatedUtc = catalog.updatedUtc
                                    , repo = "ianchanning/hn"
                                    , actionsUrl = ""
                                    , workflowFile = "hn-observatory-pages.yml"
                                    }
                            in
                            ( ProductionIndex indexModel, Cmd.none )

                        Err _ ->
                            case Decode.decodeValue ObsDecode.routerConfigDecoder flags of
                                Ok cfg ->
                                    ( ProductionRouter (ItemNotBuilt 50467087 cfg), Cmd.none )

                                Err _ ->
                                    ( DecodeError (Decode.errorToString obsErr), Cmd.none )


update : RootMsg -> RootModel -> ( RootModel, Cmd RootMsg )
update msg rootModel =
    case ( msg, rootModel ) of
        ( ObservatoryMsg obsMsg, ProductionObservatory obsModel ) ->
            let
                ( newObsModel, obsCmd ) =
                    ObsUpdate.update obsMsg obsModel
            in
            ( ProductionObservatory newObsModel, Cmd.map ObservatoryMsg obsCmd )

        ( ObservatoryMsg obsMsg, DevMode bundle ) ->
            case bundle.obsModel of
                Just om ->
                    let
                        ( newOm, obsCmd ) =
                            ObsUpdate.update obsMsg om
                    in
                    ( DevMode { bundle | obsModel = Just newOm }, Cmd.map ObservatoryMsg obsCmd )

                Nothing ->
                    ( rootModel, Cmd.none )

        ( SwitchDevTab tab, DevMode bundle ) ->
            let
                cmd =
                    if tab == TabObservatory then
                        case bundle.obsModel of
                            Just om ->
                                Cmd.map ObservatoryMsg (Ports.sendPlots om)

                            Nothing ->
                                Cmd.none

                    else
                        Cmd.none
            in
            ( DevMode { bundle | activeTab = tab }, cmd )

        _ ->
            ( rootModel, Cmd.none )


subscriptions : RootModel -> Sub RootMsg
subscriptions rootModel =
    case rootModel of
        ProductionObservatory obsModel ->
            Sub.map ObservatoryMsg (ObsSubs.subscriptions obsModel)

        DevMode bundle ->
            case ( bundle.activeTab, bundle.obsModel ) of
                ( TabObservatory, Just om ) ->
                    Sub.map ObservatoryMsg (ObsSubs.subscriptions om)

                _ ->
                    Sub.none

        _ ->
            Sub.none


view : RootModel -> Html RootMsg
view rootModel =
    case rootModel of
        ProductionObservatory obsModel ->
            Html.map ObservatoryMsg (ObsView.view obsModel)

        ProductionIndex idxModel ->
            PagesIndex.view idxModel

        ProductionRouter rState ->
            PagesRouter.view rState

        DevMode bundle ->
            div []
                [ viewDevNav bundle.activeTab
                , case bundle.activeTab of
                    TabObservatory ->
                        case bundle.obsModel of
                            Just om ->
                                Html.map ObservatoryMsg (ObsView.view om)

                            Nothing ->
                                div [ class "wrap" ] [ text "No observatory payload loaded in dev bundle." ]

                    TabIndex ->
                        case bundle.indexModel of
                            Just im ->
                                PagesIndex.view im

                            Nothing ->
                                div [ class "wrap" ] [ text "No catalog payload loaded in dev bundle." ]

                    TabRouter ->
                        case bundle.routerState of
                            Just rs ->
                                PagesRouter.view rs

                            Nothing ->
                                div [ class "wrap" ] [ text "No router config loaded in dev bundle." ]
                ]

        DecodeError err ->
            div [ class "wrap" ]
                [ div [ class "topbar" ]
                    [ text "Better Signal News — Elm" ]
                , div [ id "error" ]
                    [ text ("Payload decode error: " ++ err) ]
                ]


viewDevNav : ActiveTab -> Html RootMsg
viewDevNav active =
    let
        tabBtn tab label =
            let
                isActive =
                    active == tab

                bc =
                    if isActive then
                        "rgb(204, 204, 194)"

                    else
                        "transparent"

                bg =
                    if isActive then
                        "rgb(236, 236, 228)"

                    else
                        "transparent"

                fg =
                    if isActive then
                        "rgb(34, 34, 34)"

                    else
                        "rgb(0, 0, 0)"
            in
            span
                [ onClick (SwitchDevTab tab)
                , style "background" bg
                , style "color" fg
                , style "padding" "3px 8px"
                , style "cursor" "pointer"
                , style "border-radius" "4px"
                , style "border-width" "1px"
                , style "border-color" bc
                , style "border-style" "solid"
                , style "user-select" "none"
                , style "text-transform" "lowercase"
                ]
                [ text label ]
    in
    div
        [ style "background" "rgb(246, 246, 239)"
        , style "border-bottom" "1px solid rgb(255, 102, 0)"
        , style "margin-bottom" "8px"
        , style "padding" "6px 12px"
        , style "display" "flex"
        , style "gap" "10px"
        , style "align-items" "center"
        ]
        [ span [ style "color" "rgb(255, 102, 0)" ] [ text "ELM DEV:" ]
        , tabBtn TabIndex "Frontpage"
        , tabBtn TabObservatory "Item"
        , tabBtn TabRouter "Router"
        ]
