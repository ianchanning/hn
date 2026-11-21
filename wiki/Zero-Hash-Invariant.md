# Zero-Hash Invariant

## The Sovereign Law
All CSS and Elm color declarations must strictly use `rgb()` / `rgba()` format. Never use hexadecimal color literals (`#ff6600` or `#fff`), because the Python pipeline enforces `assert "#" not in html_doc` across all generated documents and bundles.

## The Trigger
`AssertionError: Zero-hash violated in observatory at char 1234`
`assert "#" not in html_doc`

## The Pattern
### WRONG
```elm
style "background-color" "#ff6600"
style "color" "#ffffff"
```

### RIGHT
```elm
style "background-color" "rgb(255, 102, 0)"
style "color" "rgb(255, 255, 255)"
```
