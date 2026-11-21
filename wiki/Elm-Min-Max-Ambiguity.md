# Elm Min Max Ambiguity

## The Sovereign Law
Never expose `min` or `max` unqualified from `Html.Attributes`. Always import `Html.Attributes as Attr` and qualify `Attr.min` / `Attr.max`, because `Basics.min` and `Basics.max` are in Elm's default prelude.

## The Trigger
`-- AMBIGUOUS NAME ----------------------------- src/...`
`This usage of min is ambiguous:`
`This name is exposed by 2 of your imports, so I am not sure which one to use:`
`    Basics.min`
`    Html.Attributes.min`

## The Pattern
### WRONG
```elm
import Html.Attributes exposing (min, max)

input [ min "0", max "5" ] []
```

### RIGHT
```elm
import Html.Attributes as Attr exposing (class, id)

input [ Attr.min "0", Attr.max "5" ] []
```
