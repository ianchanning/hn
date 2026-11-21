# Payload Hydration

## The Sovereign Law
Python embeds the full observatory state inside `<script id="observatoryData" type="application/json">`. Elm receives this untrusted JSON payload as raw `Json.Decode.Value` flags in `Browser.element`, decodes it via `Observatory.Decode.decodePayload`, and hydrates the tea `Model` in `init`.

## The Trigger
`-- TYPE MISMATCH -------------------------------------------------- src/Main.elm`
Passing typed records directly into Elm flags from JS without decoding, leading to runtime unhandled exceptions if the schema evolves.

## The Pattern
### WRONG
```elm
-- Untyped or direct record flag expectation
main : Program Flags Model Msg
main =
    Browser.element
        { init = \flags -> ( { payload = flags }, Cmd.none )
        , ...
        }
```

### RIGHT
```elm
-- Raw Json.Decode.Value flags decoded safely
main : Program D.Value Model Msg
main =
    Browser.element
        { init = \flagsValue ->
            case D.decodeValue decodePayload flagsValue of
                Ok payload ->
                    Model.init payload
                Err _ ->
                    Model.initFallback
        , ...
        }
```
