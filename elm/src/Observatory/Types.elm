module Observatory.Types exposing (..)

{-| Core domain types shared across the Observatory.

See TYPES.md at repo root for the full specification.

-}

import Dict exposing (Dict)



-- TIER ENUM


type Tier
    = EpistemicGold
    | GroundedAnalysis
    | CrowdChatter
    | MemeOrSnark
    | BullshitOrFlamewar
    | DownvotedSink



-- WEIGHTS


type alias Weights =
    { infoGain : Float
    , falsifiability : Float
    , gravityProgeny : Float
    , bullshitPenalty : Float
    , downvotePenalty : Float
    , mmrSimLambda : Float
    , mmrRootLambda : Float
    , mmrFacetLambda : Float
    }


type alias CurrentWeights =
    { ig : Float
    , fa : Float
    , gp : Float
    , bp : Float
    , dp : Float
    }


weightsToCurrentWeights : Weights -> CurrentWeights
weightsToCurrentWeights w =
    { ig = w.infoGain
    , fa = w.falsifiability
    , gp = w.gravityProgeny
    , bp = w.bullshitPenalty
    , dp = w.downvotePenalty
    }



-- COMPACT COMMENT


type alias CompactComment =
    { id : Int
    , au : String
    , dom : Int
    , sr : Int
    , sc : Float
    , ep : Float
    , bs : Float
    , d : Int
    , age : Float
    , grav : Float
    , surf : Float
    , fade : String
    , dt : Int
    , ut : Int
    , lu : Int
    , w : Int
    , qw : Int
    , k : Int
    , kpp : Float
    , td : Float
    , mod : Int
    , pp : Int
    , meme : Int
    , tier : Tier
    , facet : String
    , flbl : String
    , urls : List String
    , ig : Float
    , fa : Float
    , gp : Float
    , bl : Float
    , ds : Float
    , txt : String
    }



-- LIVE COMMENT (derived)


type alias LiveComment =
    { comment : CompactComment
    , liveScore : Float
    , liveEp : Float
    , liveBs : Float
    , liveRank : Int
    }



-- FACETS & SOURCES


type alias FacetOption =
    { slug : String
    , label : String
    , count : Int
    }


type alias FacetDiagnostic =
    { slug : String
    , label : String
    , count : Int
    , useful : Int
    , usefulPct : Float
    , terms : String
    }


type alias SourceCategory =
    { category : String
    , count : Int
    }



-- MANIFEST


type alias ManifestCounts =
    { totalComments : Int
    , uniqueAuthorsProfiled : Int
    , pagesFetched : Int
    }


type alias FacetCluster =
    { slug : String
    , topTerms : List String
    }


type alias Manifest =
    { storyTitle : String
    , storyUrl : String
    , points : Int
    , storyAuthor : String
    , t2RefUtc : String
    , deltaMinutes : Float
    , counts : ManifestCounts
    , facetLabels : Dict String String
    , facetClusters : List FacetCluster
    , storyAnchors : List String
    }



-- TIER COUNTS


type alias TierCounts =
    { epistemicGold : Int
    , groundedAnalysis : Int
    , crowdChatter : Int
    , memeOrSnark : Int
    , bullshitOrFlamewar : Int
    , downvotedSink : Int
    }



-- LARGEST ROOT


type alias LargestRoot =
    { rootId : Int
    , author : String
    , slots : Int
    , startDom : Int
    , endDom : Int
    , sharePct : Float
    , topDom1Age : Float
    , topDom1Author : String
    }



-- BENCHMARK TYPES


type alias JudgeMetrics =
    { ndcg20 : Float
    , pairwiseConcordance : Float
    , adversarialAcc : Float
    , buriedGoldRecallTop45 : Float
    , bullshitSinkPercentile : Float
    , top20Diversity : Float
    }


type alias JudgeResult =
    { judgeVersion : String
    , score : Float
    , devScore : Float
    , holdoutScore : Float
    , deltaVsHn : Float
    , hnLiveBaselineScore : Float
    , fullMetrics : JudgeMetrics
    }


type alias AblationRow =
    { name : String
    , score : Float
    , ndcg20 : Float
    , pairwiseConcordance : Float
    , adversarialAcc : Float
    , buriedGoldRecallTop45 : Float
    , bullshitSinkPercentile : Float
    , top20Diversity : Float
    }


type alias TournamentRow =
    { stage : String
    , sha : String
    , score : Float
    , devScore : Float
    , holdoutScore : Float
    , disposition : String
    }



-- PAYLOAD ROOT


type alias ObservatoryPayload =
    { storyId : Int
    , storyTitle : String
    , storyUrl : String
    , isBenchmark : Bool
    , manifest : Manifest
    , judge : Maybe JudgeResult
    , weights : Weights
    , tiers : TierCounts
    , facets : Dict String Int
    , facetOptions : List FacetOption
    , facetDiagnostics : List FacetDiagnostic
    , sourceCategories : List SourceCategory
    , storyAnchors : List String
    , largestRoot : LargestRoot
    , buriedCutoff : Int
    , rescueTopK : Int
    , ablations : List AblationRow
    , tournament : List TournamentRow
    , comments : List CompactComment
    }



-- VIEW MODE


type ViewMode
    = TopSignal
    | HnTop40
    | BuriedGems
    | C5aRescues
    | BullshitTraps
    | ModMorgue



-- VIEWPORT


type Viewport
    = Desktop
    | Mobile



-- CANVAS PORT TYPES


type alias Colour =
    { r : Int, g : Int, b : Int, a : Float }


type alias PlotPoint =
    { x : Float
    , y : Float
    , radius : Float
    , colour : Colour
    , commentId : Int
    }


type alias AxisConfig =
    { maxX : Float
    , maxY : Float
    , xLabel : String
    , yLabel : String
    }


type alias PlotCommand =
    { canvasId : String
    , points : List PlotPoint
    , selectedId : Maybe Int
    , axisConfig : AxisConfig
    , largestRoot : Maybe LargestRoot
    }


type alias CanvasProbeEvent =
    { canvasId : String
    , commentId : Int
    }



-- PAGES SITE TYPES (INDEX + ITEM ROUTER)


{-| A single row on the front-page index (mirrors extract\_item\_summary).
-}
type alias IndexItem =
    { storyId : Int
    , storyTitle : String
    , storyUrl : String
    , points : Int
    , storyAuthor : String
    , totalComments : Int
    , epistemicGold : Int
    , groundedAnalysis : Int
    , t2RefUtc : String
    , sizeKb : Float
    }


{-| The catalog.json manifest consumed by the index page.
-}
type alias Catalog =
    { updatedUtc : String
    , totalPublished : Int
    , totalSizeMb : Float
    , frontpageSyncedUtc : String
    , frontpageIds : List Int
    , uriTemplate : String
    , items : List IndexItem
    }


{-| Item router configuration (embedded in item.html / 404.html).
-}
type alias RouterConfig =
    { repo : String
    , actionsUrl : String
    , workflowFile : String
    }


{-| Item router resolution state machine.
-}
type RouterState
    = ResolvingItem Int
    | ItemLoaded String
    | ItemNotBuilt Int RouterConfig
    | InvalidItemId
