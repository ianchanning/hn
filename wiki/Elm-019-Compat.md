# Elm 0.19 Compatibility

## The Sovereign Law
Elm 0.19.3 is an in-place minor patch release fully backwards-compatible with Elm 0.19.1 packages and core syntax. In `elm.json`, always declare `"elm-version": "0.19.1"` so package dependencies and external tooling resolve deterministically without version conflict.

## The Trigger
`-- INCOMPATIBLE ELM VERSION --------------------------------------- elm.json`
`Your elm.json says this package works with Elm 0.19.3, but the package repository only understands 0.19.1.`

## The Pattern
### WRONG
```json
{
    "type": "application",
    "source-directories": [ "src" ],
    "elm-version": "0.19.3",
    "dependencies": { ... }
}
```

### RIGHT
```json
{
    "type": "application",
    "source-directories": [ "src" ],
    "elm-version": "0.19.1",
    "dependencies": { ... }
}
```
