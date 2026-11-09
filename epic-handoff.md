# epic-router handoff — DropBear V2 → STM32H7 adapter DSN parse failure

## Board
`~/Projects/dropbear-v2-stm32-adapter/kicad/adapter.dsn` (9,704 bytes)

Pure passthrough adapter: DropBear V2 (Teensy 4.1 socket, bottom) → DCWerx STM32H743
(Mega 2560 footprint, top). 2-layer F.Cu/B.Cu. **40 nets, 9 components, 142 pads,
0 vias** — placement-only (no tracks yet). All 40 nets are simple 2-pin connections
(J1 Teensy pad → Mega header position) except GND (9 pads) and +5V/+3V3 (4+4 pads).
Board outline: 101.7 × 56.0 mm.

## Command attempted
```bash
cd ~/Projects/dropbear-v2-stm32-adapter/kicad
~/Downloads/EpicRouter/rust/target/release/epic-cli route \
  -de adapter.dsn -do adapter.ses -mp 20
```

## Error (verbatim)
```
Warning: Deprecated settings path 'router.max_passes'; use 'router.autorouter.max_passes' instead. The old path will be removed in a future release.
Error: parse error at (pcb: DSN structure parsing failed
```

## Classification
**DSN parse rejection** — not a build failure, not a launch crash, not flag misuse.
The binary exists and runs. The tutorial_board.dsn from the same repo parses and routes
successfully (control: 438 nets, 0 violations, EXIT=0). Our generated DSN does not.

## Root cause
The generated DSN uses a simplified Specctra emission that doesn't match what
the `epic-dsn` crate's Rust port of the Java `SpecctraDsnStreamReader` expects.
The tutorial_board.dsn (from `examples/tutorial_board/`) parses fine — proving the
parser works. The issue is our DSN generator (a ~50-line Python script producing
the s-expression) doesn't emit the full Specctra structure the parser requires.

Specifically: the error is `board_outline_ok = false` after reading the entire
`(pcb ...)` scope — the parser never set the `board_outline_ok` flag because it
didn't find a `(boundary (path pcb 0 ...))` block it recognized inside
`(structure ...)`. Our DSN does contain that block, but the parser's token scanner
may not be matching it due to format differences (whitespace, keyword order,
missing sub-blocks like `(plane ...)`, missing `(property (index N))` on layers,
or resolution/unit mismatch).

## What a SUCCESSFUL output looks like
- `adapter.ses` written alongside the DSN (Specctra session file with routes)
- epic-cli stdout: `Info: board loaded: N items, N nets, 0 pre-existing violations`
  followed by routing passes and a final score
- Exit code 0
- The `.ses` file can be imported back into KiCad via pcbnew Python API
  (`pcbnew.ImportSpecctraSES`) or the KiCad GUI (File→Import→Specctra Session)

## What we need from the fix
1. Make the DSN parse (or tell us exactly what's wrong with our DSN format)
2. Return the `adapter.ses` output file
3. We will apply the routes to the live board and run DRC

## DSN content summary
- 40 nets, all simple 2-pin passthrough (J1 pad ↔ Mega header pad)
- GND: 9 pads (will become zone pour post-routing)
- +5V: 4 pads (0.76mm trace width requested)
- +3V3: 4 pads (0.5mm trace width)
- 33 signal nets: 0.254mm trace width
- Design rules: signal min 0.254mm/0.254mm clearance, via 0.46/0.91mm
- Board outline: rect (−1.32, −54.66) to (100.38, 1.32) in mm
- Coordinate units: mm (resolution 10000)

## Reference
The tutorial_board.dsn from `examples/tutorial_board/` parses and routes
successfully — use it as the format reference. The failing DSN uses the same
top-level structure but with our board's data.
