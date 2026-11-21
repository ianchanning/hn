# Elm Tuples Max Three

## The Sovereign Law
Elm only supports 2-tuples `( a, b )` and 3-tuples `( a, b, c )`. Any tuple with four or more items causes a compiler rejection; always use named records (`type alias ...`) instead.

## The Trigger
`-- BAD TUPLE ------------------------------------------------------ src/...`
`I only accept tuples with two or three items. This has too many:`

## The Pattern
### WRONG
```elm
type alias Quad a b c d =
    ( a, b, c, d )
```

### RIGHT
```elm
type alias Quad a b c d =
    { first : a
    , second : b
    , third : c
    , fourth : d
    }
```
