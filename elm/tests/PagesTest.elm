module PagesTest exposing (suite)

{-| Tests for Pages.Index and Pages.Router.
-}

import Expect
import Html
import Observatory.Types exposing (IndexItem, RouterConfig, RouterState(..))
import Pages.Index as Index exposing (IndexModel)
import Pages.Router as Router
import Test exposing (..)
import Test.Html.Query as Query
import Test.Html.Selector exposing (class, id, text)


mockItems : List IndexItem
mockItems =
    [ { storyId = 50472038
      , storyTitle = "Epistemic Machine Studying"
      , storyUrl = "https://example.com/machine-studying"
      , points = 320
      , storyAuthor = "norvig"
      , totalComments = 145
      , epistemicGold = 18
      , groundedAnalysis = 42
      , t2RefUtc = "2026-11-21T06:00:00Z"
      , sizeKb = 85.4
      }
    , { storyId = 50467087
      , storyTitle = "Submodular Epistemic Selection"
      , storyUrl = ""
      , points = 210
      , storyAuthor = "shannon"
      , totalComments = 88
      , epistemicGold = 12
      , groundedAnalysis = 24
      , t2RefUtc = "2026-11-21T05:00:00Z"
      , sizeKb = 64.2
      }
    ]


mockIndexModel : IndexModel
mockIndexModel =
    { items = mockItems
    , frontpageIds = [ 50472038, 50467087 ]
    , updatedUtc = "2026-11-21 08:00 UTC"
    , repo = "ian/hn"
    , actionsUrl = "https://github.com/ian/hn/actions"
    , workflowFile = "observatory.yml"
    }


mockRouterConfig : RouterConfig
mockRouterConfig =
    { repo = "ian/hn"
    , actionsUrl = "https://github.com/ian/hn/actions"
    , workflowFile = "observatory.yml"
    }


suite : Test
suite =
    describe "Pages Modules"
        [ describe "Pages.Index"
            [ test "renders story title rows" <|
                \_ ->
                    Index.view mockIndexModel
                        |> Query.fromHtml
                        |> Query.findAll [ class "storylink" ]
                        |> Query.count (Expect.equal 2)
            , test "renders external sitebit when url present" <|
                \_ ->
                    Index.view mockIndexModel
                        |> Query.fromHtml
                        |> Query.findAll [ class "sitebit" ]
                        |> Query.count (Expect.equal 1)
            , test "renders points and author in subtext" <|
                \_ ->
                    Index.view mockIndexModel
                        |> Query.fromHtml
                        |> Query.findAll [ class "subtext" ]
                        |> Query.first
                        |> Query.has [ text "320 points by norvig" ]
            , test "renders list-pad and topbar-right with Updated UTC" <|
                \_ ->
                    Index.view mockIndexModel
                        |> Query.fromHtml
                        |> Query.has
                            [ class "list-pad"
                            , text "Updated 2026-11-21 08:00 UTC"
                            ]
            ]
        , describe "Pages.Router"
            [ test "renders resolving state" <|
                \_ ->
                    Router.view (ResolvingItem 50472038)
                        |> Query.fromHtml
                        |> Query.find [ id "statusTitle" ]
                        |> Query.has [ text "Loading Better Signal News..." ]
            , test "renders item not built state with CLI command" <|
                \_ ->
                    Router.view (ItemNotBuilt 99999999 mockRouterConfig)
                        |> Query.fromHtml
                        |> Query.find [ id "statusTitle" ]
                        |> Query.has [ text "HN Item 99999999 Not Yet Built" ]
            , test "renders invalid item state" <|
                \_ ->
                    Router.view InvalidItemId
                        |> Query.fromHtml
                        |> Query.find [ id "statusTitle" ]
                        |> Query.has [ text "Missing or Invalid Hacker News Item ID" ]
            ]
        ]
