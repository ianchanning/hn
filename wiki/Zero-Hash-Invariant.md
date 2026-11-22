# Zero-Hash Invariant

## The Sovereign Law
All CSS and Elm declarations must contain zero `#` characters: use `rgb()` / `rgba()` (never hex `#ff6600`) AND attribute selectors `[id="foo"]` (never CSS `#foo` ID selectors), because the Python pipeline enforces `assert "#" not in html_doc` and `assert "#" not in css` across all generated documents and stylesheets.

## The Trigger
`AssertionError: Zero-hash violated in observatory at char 1234`
`AssertionError: Zero-hash violated in elm/static/style.css`
`assert "#" not in html_doc`

## The Pattern
### WRONG
```elm
style "background-color" "#ff6600"
style "color" "#ffffff"
```
```css
#cards > article { background: #f6f6ef; }
```

### RIGHT
```elm
style "background-color" "rgb(255, 102, 0)"
style "color" "rgb(255, 255, 255)"
```
```css
[id="cards"] > article { background: rgb(246, 246, 239); }
```
