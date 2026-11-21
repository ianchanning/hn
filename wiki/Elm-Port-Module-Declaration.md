# Elm Port Module Declaration

## The Sovereign Law
A module declared with `port module` MUST define at least one port within its own body. If a module merely consumes ports imported from another module, it must be declared with `module`, not `port module`.

## The Trigger
`-- NO PORTS ------------------------------------------------------- src/Main.elm`
`This module does not declare any ports, but it says it will:`
`1| port module Main exposing (main)`
`   ^^^^^^^^^^^`
`Switch this to module and you should be all set!`

## The Pattern
### WRONG
```elm
port module Main exposing (main)

import Observatory.Ports exposing (drawPlot)
-- No port declarations in this file!
```

### RIGHT
```elm
module Main exposing (main)

import Observatory.Ports exposing (drawPlot)
-- Ports live in Observatory/Ports.elm (which is declared as `port module`)
```
