module ViewTest exposing (suite)

{-| Tests for Observatory views and layout rendering.
-}

import Dict
import Expect
import Html
import Observatory.Model exposing (Model, recomputeLiveList)
import Observatory.Msg exposing (Msg)
import Observatory.Types exposing (..)
import Observatory.View exposing (view)
import Observatory.View.Cards exposing (viewCards)
import Observatory.View.Evidence exposing (viewEvidence)
import Observatory.View.Explore exposing (viewExplore)
import Observatory.View.Header exposing (viewHeader)
import Test exposing (..)
import Test.Html.Query as Query
import Test.Html.Selector exposing (class, id, tag, text)


mockPayload : ObservatoryPayload
mockPayload =
    { storyId = 50472038
    , storyTitle = "Show HN: Epistemic Observatory"
    , storyUrl = "https://example.com/story"
    , isBenchmark = False
    , manifest =
        { storyTitle = "Show HN: Epistemic Observatory"
        , storyUrl = "https://example.com/story"
        , points = 142
        , storyAuthor = "socrates"
        , t2RefUtc = "2026-11-21T00:00:00Z"
        , deltaMinutes = 45.0
        , counts =
            { totalComments = 2
            , uniqueAuthorsProfiled = 2
            , pagesFetched = 1
            }
        , facetLabels = Dict.empty
        , facetClusters = []
        , storyAnchors = [ "epistemic", "bayesian" ]
        }
    , judge = Nothing
    , weights =
        { infoGain = 2.35
        , falsifiability = 2.85
        , gravityProgeny = 1.45
        , bullshitPenalty = 2.65
        , downvotePenalty = 3.1
        , mmrSimLambda = 0.35
        , mmrRootLambda = 0.25
        , mmrFacetLambda = 0.15
        }
    , tiers =
        { epistemicGold = 1
        , groundedAnalysis = 1
        , crowdChatter = 0
        , memeOrSnark = 0
        , bullshitOrFlamewar = 0
        , downvotedSink = 0
        }
    , facets = Dict.fromList [ ( "epistemic_science", 2 ) ]
    , facetOptions = [ { slug = "epistemic_science", label = "Epistemic Science", count = 2 } ]
    , facetDiagnostics =
        [ { slug = "epistemic_science"
          , label = "Epistemic Science"
          , count = 2
          , useful = 2
          , usefulPct = 100.0
          , terms = "bayes popper info"
          }
        ]
    , sourceCategories = [ { category = "academic", count = 1 } ]
    , storyAnchors = [ "epistemic", "bayesian" ]
    , largestRoot =
        { rootId = 1
        , author = "plato"
        , slots = 2
        , startDom = 1
        , endDom = 2
        , sharePct = 100.0
        , topDom1Age = 1.5
        , topDom1Author = "plato"
        }
    , buriedCutoff = 500
    , rescueTopK = 80
    , ablations = []
    , tournament = []
    , comments =
        [ { id = 101
          , au = "plato"
          , dom = 1
          , sr = 1
          , sc = 4.5
          , ep = 5.0
          , bs = 0.5
          , d = 0
          , age = 1.5
          , grav = 3.2
          , surf = 1.0
          , fade = "c00"
          , dt = 0
          , ut = 2
          , lu = 0
          , w = 120
          , qw = 20
          , k = 1500
          , kpp = 12.5
          , td = 0.05
          , mod = 0
          , pp = 0
          , meme = 0
          , tier = EpistemicGold
          , facet = "epistemic_science"
          , flbl = "Epistemic Science"
          , urls = [ "https://plato.stanford.edu/epistemology" ]
          , ig = 1.8
          , fa = 2.1
          , gp = 1.1
          , bl = 0.2
          , ds = 0.0
          , txt = "The unexamined life is not worth living.\n> Indeed it is not."
          }
        , { id = 102
          , au = "aristotle"
          , dom = 2
          , sr = 2
          , sc = 3.8
          , ep = 4.2
          , bs = 0.4
          , d = 1
          , age = 1.2
          , grav = 2.9
          , surf = 0.8
          , fade = "c00"
          , dt = 0
          , ut = 1
          , lu = 0
          , w = 90
          , qw = 10
          , k = 950
          , kpp = 9.8
          , td = 0.1
          , mod = 0
          , pp = 0
          , meme = 0
          , tier = GroundedAnalysis
          , facet = "epistemic_science"
          , flbl = "Epistemic Science"
          , urls = []
          , ig = 1.5
          , fa = 1.8
          , gp = 0.9
          , bl = 0.1
          , ds = 0.0
          , txt = "We are what we repeatedly do. Excellence, then, is not an act, but a habit."
          }
        ]
    }


mockModel : Model
mockModel =
    let
        cw =
            { ig = 2.35, fa = 2.85, gp = 1.45, bp = 2.65, dp = 3.1 }
    in
    { payload = Just mockPayload
    , currentWeights = cw
    , activeMode = TopSignal
    , searchQuery = ""
    , selectedFacet = "all"
    , selectedCommentId = Nothing
    , liveList = recomputeLiveList cw mockPayload.comments
    , proofDrawerOpen = True
    , labDrawerOpen = True
    , tunerDrawerOpen = True
    , gravityDrawerOpen = True
    , viewport = Desktop
    , error = Nothing
    }


suite : Test
suite =
    describe "Observatory Views"
        [ describe "Observatory.View.Header"
            [ test "renders story title and author" <|
                \_ ->
                    viewHeader mockModel mockPayload
                        |> Query.fromHtml
                        |> Query.find [ class "story-title" ]
                        |> Query.has [ text "Show HN: Epistemic Observatory" ]
            , test "renders 2 mode tabs (Top 40 & HN Top 40)" <|
                \_ ->
                    viewHeader mockModel mockPayload
                        |> Query.fromHtml
                        |> Query.findAll [ class "mode-tab" ]
                        |> Query.count (Expect.equal 2)
            ]
        , describe "Observatory.View.Evidence"
            [ test "renders KPI strip in live mode" <|
                \_ ->
                    viewEvidence mockModel mockPayload
                        |> Query.fromHtml
                        |> Query.findAll [ class "kpi-cell" ]
                        |> Query.count (Expect.equal 6)
            , test "renders facet diagnostic table" <|
                \_ ->
                    viewEvidence mockModel mockPayload
                        |> Query.fromHtml
                        |> Query.find [ id "facetDiagTable" ]
                        |> Query.has [ tag "table" ]
            ]
        , describe "Observatory.View.Explore"
            [ test "renders 5 weight tuner sliders" <|
                \_ ->
                    viewExplore mockModel mockPayload
                        |> Query.fromHtml
                        |> Query.findAll [ class "slider-row" ]
                        |> Query.count (Expect.equal 5)
            , test "renders both canvas elements" <|
                \_ ->
                    let
                        q =
                            viewExplore mockModel mockPayload
                                |> Query.fromHtml
                    in
                    q
                        |> Query.findAll [ tag "svg" ]
                        |> Query.count (Expect.equal 2)
            ]
        , describe "Observatory.View.Cards"
            [ test "renders comment cards for live comments" <|
                \_ ->
                    viewCards mockModel mockPayload
                        |> Query.fromHtml
                        |> Query.findAll [ class "c-card" ]
                        |> Query.count (Expect.equal 2)
            , test "renders blockquote formatting" <|
                \_ ->
                    viewCards mockModel mockPayload
                        |> Query.fromHtml
                        |> Query.find [ class "hn-quote" ]
                        |> Query.has [ text "> Indeed it is not." ]
            ]
        , describe "Observatory.View (Top-level)"
            [ test "renders wrapper and main sections" <|
                \_ ->
                    view mockModel
                        |> Query.fromHtml
                        |> Query.has [ class "wrap" ]
            , test "renders sheet-foot footer" <|
                \_ ->
                    view mockModel
                        |> Query.fromHtml
                        |> Query.find [ class "sheet-foot" ]
                        |> Query.has [ class "sheet-foot" ]
            ]
        ]
