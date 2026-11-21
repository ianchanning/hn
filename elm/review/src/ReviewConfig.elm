module ReviewConfig exposing (config)

{-| elm-review configuration for the HN Epistemic Observatory Elm display layer.
-}

import Review.Rule as Rule exposing (Rule)


config : List Rule
config =
    [ zeroHashRule
    ]


zeroHashRule : Rule
zeroHashRule =
    Rule.newModuleRuleSchema "EpistemicObservatory.ZeroHash" ()
        |> Rule.withSimpleImportVisitor (\_ -> [])
        |> Rule.fromModuleRuleSchema
