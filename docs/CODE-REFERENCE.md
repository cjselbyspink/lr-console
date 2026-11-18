# LR Console — Code Reference

**Rewritten 28 September 2026 for the redesigned board; folded forward 2
October 2026** (page 2 "Tone", Crop/Mask mirroring, drain batching, EN16
gestures, plugin fork 0.2.16). Anything not in here is not current; §14
lists what was removed and why, so that a superseded belief can be
recognised rather than rediscovered. The bench record behind the rewrite is
`claude/LR-Console-Bench-Findings-2026-09-26.md`; the design as built is
`claude/LR-Console-Layout.md`; the day-by-day since 28 Sep is
`claude/LR-Console-Session-Log-2026-09-28.md`.

Every claim carries a confidence marker:

- **[M]** measured on hardware
- **[S]** read from source (`index.js`, `grid-api.lua`, the plugin Lua)
- **[I]** inferred from something measured, not itself tested
- **[?]** assumed, never confirmed — treat as a bench test waiting to happen
- **[stated]** CJ said so

---

## 1. Physical layout

As seated, far row first:

```
VSN2 (upright)   EN16-A (270°)   VSN1 (host)
TEK2 (180°)      EN16-B (270°)   BU16 (upright)
```

**Plate flipped 27 September** [M]: VSN2 and TEK2 took the left column
(cull keys and holds under the left hand), VSN1 and BU16 the right (the
sixteen under the jog), the EN16 pair stays in the middle. **BU16 went back
to 0° on 28 September** so its caps sit the same way up as VSN1's; the two
halves of the sixteen had read as different colours at 180° [stated], and
the caps are the suspect. Everything BU16-side is resolved through
`lr_common.BU16_ROT` and `lr_v2.bu16_slot_lua()`.

3 mm black Dibond, 3M Dual Lock, adhesive feet. Single USB-C feed into VSN1,
cable leaving the far edge.

**The USB host is VSN1 and works.** [M] What stands from the earlier host
experiments: with the cable in EN16-B, pressing an encoder in its two
left-hand columns blacks out the whole array, and a commit reported as
successful can fail to survive a power cycle. Suspected brownout mid-flash-
write. Reported to Intech; unresolved. Do not host from EN16-B.

**Rotations appear in no config file.** [M] They live in the physical
assembly only. Nothing in an export will ever remind you, so the formulas in
§2 are the only record.

Reach model [stated, 26 Sep]: hands come in from the sides, forearms resting
either side of the board, fingers pointing at each other. Outer columns
prime, centre worst; thumb near, fingers far. This is why HSL sits in the
middle and why the holds are in TEK2's corner.

---

## 2. Element maps

**Diagnose orientation by behaviour, not by LED colour.** [M] Press a key
with an unmistakable, reversible effect and see where it lands. Reading LEDs
through tinted caps has produced wrong conclusions more than once.

**The System element is 255 in every config file, on every module type.**
[S] The Editor labels it by element *count* ("Element 10 (System)" on TEK2,
14 on VSN1, 16 on EN16/BU16, 18 on VSN2). Older notes recording System as 10
or 14 are describing the UI label, not the config field.

### VSN1 (far right, host)

| Element | What |
|---|---|
| 0–7 | Hall keys — 0–3 row 1 (under the jog), 4–7 row 2, left to right |
| 8 | Jog wheel, Endless type |
| 9–12 | Small buttons — pages 1/2/3/4 |
| 13 | LCD |
| 255 | System |

Key Setups double as code hosts (System and the LCD are at their budgets):
key 0 carries the MIDI ear and the plugin receiver, key 1 `kpar`, key 2
`kmsk`, key 4 `hc`/`hse`/`hdr` (the LCD header and EN16 echo matching),
key 5 `sp` (preset names). Element 8's Setup carries `selb`, `eventrx_cb`
and the boot selection.

### BU16 (near right, 0° since 28 Sep)

`element = 4*row + col`, row 0 at the far edge (against VSN1). The physical
slot `p` (8–15) of the sixteen is element `p - 8`; slot 15 (Reset) is
element 7. Rows 3–4 (elements 8–15) are the fixed action keys; Map is
element 12 (row 3 col 0). All four orientations are in `lr_common.BU16_ROT`
(180° was `15 - 4*row - col`, slot = `23 - element`, 16–28 Sep). **The first
build on any new mount is verified by pressing Reset**, not by LED colour.

### TEK2 (near left, 180°)

| Element | What |
|---|---|
| 0–7 | Hall keys |
| 8 | Endless — physically the **right** dial |
| 9 | Endless — physically the **left** dial |
| 255 | System |

**The Editor does not remap for the rotation.** [M] Physical row 3 of the
left block (TEK2's far row, against VSN2's keys) is elements 7,6,5,4 for
columns 1–4; row 4 (near, by the dials) is 3,2,1,0. `lr_v2.TEK2_ROW3/ROW4`.
**TEK2 has two configs**: `TEK2 Fixed` for pages 1/3/4 and `Page 2 TEK2`
(zone radio on row 3, Hue/Sat dials). **Pages on TEK2 follow the global
page change** [M, 1 Oct].

### VSN2 (far left, upright)

| Element | What |
|---|---|
| 0–7 | Hall keys — 0–3 row 1 (nearest the screens), 4–7 row 2 |
| 8–11 | Small buttons under screen A |
| 12 | LCD A (left) |
| 13–16 | Small buttons under screen B |
| 17 | LCD B (right) |

Globals cross both Draw loops in sync [M]; per-screen tables live on `self`
(§11). Key 0's Setup carries the receiver; key 1's the page-2 `zp` table.

### EN16-A / EN16-B (middle column, 270°)

`index = 3 - row + 4*col`, so `row = 3 - (i % 4)` and `col = i // 4`. [M]

| | col 0 Hue | col 1 Sat | col 2 Lum | col 3 presets |
|---|---|---|---|---|
| row 0 | 3 | 7 | 11 | 15 |
| row 1 | 2 | 6 | 10 | 14 |
| row 2 | 1 | 5 | 9 | 13 |
| row 3 | 0 | 4 | 8 | 12 |

Bands top to bottom: Red / Orange / Yellow / Green on EN16-A, Aqua / Blue /
Purple / Magenta on EN16-B. Column 3 carries the split-tone presets
(`SPLIT_PRESETS` rows 0–3 on A, row 4 "Clear" on B).

---

## 3. Cross-module dispatch

`eventrx_cb(self, h, e, xv, n)`.

`h` is `{instr, sx, sy}` [S] — source **position relative to the listener**,
not module type [M, 18 Sep].

```lua
local m = (h[2] - mbx) * 2 + (mby - h[3])
```

Current plate (flipped, since 27 Sep) — `lr_common.POS_FLIPPED`, the build
default:

| m | Module | position x, y |
|---|---|---|
| 0 | VSN2 | −2, 0 |
| 1 | TEK2 | −2, −1 |
| 2 | EN16-A | −1, 0 |
| 3 | EN16-B | −1, −1 |
| 4 | VSN1 | 0, 0 (host) |
| 5 | BU16 | 0, −1 |

Listener bases: VSN1 `(125, 127)`, VSN2 `(127, 127)`. `h[2] = 127 +
(source_x − listener_x)`, `h[3] = 127 + (source_y − listener_y)`. Positions
are measured from the USB host [M: VSN2 probe printed `[-2, 0]` and
`module_position_x/y` = (−2, 0), agreeing]. **Never hard-code an `m` value**;
`lr_common.set_layout()` / the third argument to `build_all.py` derives
everything from the one table. `POS_SWAPPED` (22–26 Sep) and `original` (to
21 Sep) exist only to reproduce old builds.

**Which paths are in use, and measured**:
- VSN1 hears BU16 presses (slot select, Map hold edges) — `eventrx_cb` [M].
- **VSN1 hears EN16 encoder events** (preset-row knobs, for the LCD
  header) — `eventrx_cb` [M, 2 Oct: the preset name appears].
- VSN2 hears BU16's Map key — `eventrx_cb` [M]. (It heard EN16 for the band
  flash until 2 Oct; that moved to VSN1.)
- TEK2 → VSN1 (Before/After hold) — **MIDI** CC115, not `eventrx_cb`.
  CC116 (Rotate) retired 2 Oct: the jog now reads the crop state from the
  plugin reply.
- VSN1 → TEK2 MIDI is measured [M, 18 Sep] but nothing uses it now.

**TEK2's `module_position_*` is unreliable.** [M, 26 Sep, at 0°] Read
(−1, 2), then (2, 1), then (−1, 2) again across power cycles while the
monitor prefix said `[-2, -1]` every time. VSN2 at the same time reported
correctly. Keep TEK2 off position-dependent paths; `module_position_*` must
not be used at runtime for layout detection.

`e` is `{page, element, type}` [S]; `e[2]` is the raw element index on the
sender. `e[3]` stayed 3 through both button edges [M]. `xv` is `{value, min,
max}` [M]: press `127/0/127`, release `0/0/127`. **`xv[1] > 0` is the press
gate**; the Map hold uses both edges. For an encoder source `xv[1]` is the
encoder state, so a listener that only wants presses must branch on the
source module before the `xv[1] == 0` return (VSN1's `eventrx_cb` does).

Reverse-engineered on hardware; no documentation for the signature exists.

---

## 4. LED rules

**Layer `-1` does not work.** [M] Fails silently on both LED calls. Every
LED call names an explicit layer.

**`led_color(layer, {{r,g,b,a}})` — note the DOUBLE braces: the argument is
a table OF tables, one colour per inner table.** A single-brace call
`led_color(1, {r,g,b,a})` is accepted and does nothing [M, 27 Sep: `relab()`
shipped that way and the label keys never changed]. `build_all.py` lints
for it. **Alpha is the brightness control.** [M]
**`led_value(layer, x)` gates** [M]: 0 is dark, any non-zero is on. To make a
key dark, gate it. On Endless encoder LED rings `led_value` is a proportional
fill meter [M]; for a mode indicator hold `led_value(2, 255)` and vary alpha.

**The board-wide convention (28 Sep)** — `lr_common.IDLE`, `RING_IDLE`,
`RING_ON`, `RING_MS`: keys idle at alpha **0.15**, go to **1** while
pressed / selected / their LrC state is active, and are **off** via
`led_value(1, 0)` when they cannot act. Dial rings **0.05** idle, 0.5 while
turning, back after 400 ms on the element's timer. EN16 knobs 0.05 idle
(`lr_pages.EN16_IDLE`), 0.5 while turning.

**BU16's LEDs render greener/bluer than VSN1's at the same RGB** [M, 28
Sep]. Every colour BU16 is given is scaled by `lr_v2.BU16_TINT = (1.0, 0.7,
0.6)` before it is emitted. Adjust the constant, never the palettes; the
other modules take palette values as they are. Consequence: a colour meant
to match across BU16 and TEK2 needs two constants (`VIEW_KEY` / `VIEW_TEK`
for the blue caps, 2 Oct — "not perfect, leave it" [stated]).

**`led_value` on Hall keys is a gate, not a level.** Never use `led_value`
for brightness.

---

## 5. Ranges, the dial model and the drain

Generated configs carry no `@sen`, `@sbc`, `@sglc`, `@gms` or `@sec` GUI
blocks and **the Editor does not re-insert them** [M]. Any element on a
generated page needs its range set by hand in Setup: Endless
`endless_mode(0)`, `endless_sensitivity(50)`, `endless_min`, `endless_max`,
then `endless_value(0)` (value after min/max). Encoder `encoder_mode(0)`,
`encoder_sensitivity(100)`, `encoder_min(0)`, `encoder_max(127)`.

**`endless_state() - 64` is a rate, linear in speed, and the SUM over one
revolution is speed-invariant at ~91,000 units.** [M, 17 Sep]

| turn | events | sum | mean |
|---|---|---|---|
| slow | 321 | 90,184 | 281 |
| moderate | 248 | 91,492 | 370 |
| brisk | 83 | 61,041 (39 spikes excluded) | 1,326 |

Events fire on a fixed clock (~110 Hz), not per unit of movement. Scale by
the sum, never by the individual reading. Two quirks: **spikes** (10–50×
neighbours, substitute the last good reading — `SPIKE`) and **a floor of
278** (the minimum step is ~0.3 % of a revolution however scaled, which is
why fine mode exists). Parameters carry units per revolution and a
resolution; fine mode scales by 0.1. A negative amount reverses the dial
(hue, so clockwise runs the way LrC's wheel does [M]). **Fractional sends
are truncated, so the fraction is accumulated on `self.ac` and whole units
sent as they cross** [M]. **Every dial needs the wide range (±100000)** [M].

**The drain** [S, `index.js`; acted on 1 Oct]: the package keys every
`develop` send on the literal group id `"develop"`, overwrites the stored
args on each call, and drains one group id per 50 ms `setInterval`. **Every
message in a window except the last is discarded.** At 110 Hz a fast rev
lost ~5 of 6 sends — "spinning faster covers less" [M, 1 Oct]. Rules:

- Jog and TEK2 param dials: `SEND_EVERY = 6` — accumulate, send the sum on
  every sixth event. Fast rev ≈ slow rev [M]. Residual speed-dependence
  (hue: 270° deliberate, 190–200° fast per rev) is the §7 non-linearity of
  batched relative deltas; accepted, felt right [stated].
- EN16 HSL knobs: detents accumulate, the knob's timer sends at most every
  60 ms (`EN16_SEND_MS`).
- Presets: **one message** (`preset,…`), its own group id, so it cannot
  collide with `develop`. The old four-send chain per knob raced across
  elements *and modules* and lost messages in the drain [M, 2 Oct].
- Two senders at once (jog + TEK2 dial, say) still share the `develop` slot
  and lose each other's sends. Not fixed; the tally never saw the case.

Per-revolution amounts are therefore nominal; delivered/nominal ran
0.25–0.75 before batching. Re-feel before tuning any amount.

Debugging note: a readout of the last event value looks like a resting floor
between turns. Always show the event count alongside a value.

TEK2's dials: Zoom sends one step per event by sign (press-wobble
`BLACKOUT`, 2 Oct); Filmstrip accumulates at 24 steps per revolution; on
page 2 both run the jog's `DIAL_ENDLESS` arithmetic with a zone table and
per-dial `self.fm/ft/lg` state.

---

## 6. Setup ordering and the character budget

Setup runs top-to-bottom by element number, on load and on commit [M], then
again for every element via the System element's `for i = 0, #element - 1 do
element[i]:ini() end`, which must come last. **Anything defined in element
255 is nil during the first pass** — guard calls (`if kcol then … end`) and
define tables before any call. Setup also runs several times per commit.

Because Setup re-runs, **wrapping a global function must re-establish the
base first** — `lr_v2.VSN1_RECV` redefines `LrImportActive` and then wraps
it. Where two keys on one module each add a receiver (TEK2's Mask and Crop),
they **chain** onto the previous `LrImportActive` and the System Setup sets
it to nil first, so a page change cannot chain onto the old page's closures
[M, 2 Oct].

**Structural rules the Editor assumes** [M]: every element has an event 0;
element numbering contiguous plus 255; events ascending. `build_all.py`
checks all three.

**908 characters per event, measured minified. The build's figure matched
the Editor's to the character at 907/908** [M, 2 Oct]. It under-predicts by
~24 characters when content is added as separate statements rather than
inside one table literal, so `lua_table` emits one literal (integer keys;
`lr_pages2.str_table` for string keys). When an event hits the ceiling,
move a function onto a spare key's Setup (as `hdr`/`hse` did, taking the
LCD Draw from 907 to 756).

Current hot spots (r1002-1730): VSN1 key 0 Setup **762**, key 4 747, key 8
740, LCD Draw 756; EN16-A System 766; Page 2 TEK2 System 703; VSN2 screen
Setups 696.

**Unresolved:** a value assigned in a System element Setup was once read as
nil elsewhere. [?]

---

## 7. Transport constraints

**Only one `package_send` per event execution reaches Lightroom.** [M] Last
call wins. Anything needing two or more spreads them across ticks via the
element's timer (`self:timer_start(ms)` fires that element's event 6;
one-shot, re-arm each tick [M]). Used by VSN2's Clear key and the EN16
accumulators.

**`page_load(n)` (0-indexed) syncs all six modules natively.** [M] Never
broadcast a page change.

**`eventrx_cb` is a VSN-family capability.** [M, 18 Sep] VSN1 and VSN2
receive everything; TEK2 and EN16 never fire it, for anyone's events. Use
MIDI to reach a non-VSN module.

**Module-to-module MIDI reaches every module tested** [M]: VSN1 → TEK2 (18
Sep), VSN1 → BU16 and TEK2 → VSN1 (27 Sep). `midi_send(15, 176, CC, v)`:

| CC | Direction | Meaning |
|---|---|---|
| 119 | VSN1 → BU16 | selected physical slot (8–15 light on BU16) |
| 117 | — | retired 28 Sep (was Mask held); reserved |
| 116 | — | retired 2 Oct (was Rotate held); reserved |
| 115 | TEK2 → VSN1 | Before/After held / released |

- **`header[1] == 14` marks grid-internal traffic**; 13 is the host. Every
  receiver gates on `h[1] ~= 13 and d[2] == 176 and d[3] == <CC>`.
- `header[2]/[3]` do NOT follow the §3 convention and are never used.
- The message also leaves for the host; channel 15 and CCs 115–119 are
  reserved.

**VSN1 is the single authority on selection** (`selb`): a BU16 press goes to
VSN1 via `eventrx_cb`, VSN1 selects and broadcasts on CC119.

**`execute-lua-script` — the Editor's route onto the board — works and
reaches every module** [M, 26 Sep]. Every module defines `LrImportActive`
(a no-op where unused) so the call never lands on nil. Exercised at the
plugin's 20 replies/s echo rate [M, 2 Oct] without visible loss.

**Socket churn** [S, log]: the plugin rebuilds its sockets after 5 s of
silence; each rebuild is a ~2 s window in which a reply has nowhere to go.
Readback must tolerate a missing reply — hence the counter on the LCD.

**`immediate_send` bricked a module** (Sep). Still prohibited [?].

**Cross-element field access**: reads of Lua-set fields work [M]; writes
fail [M]; method calls work.

---

## 8. Lightroom: the package, the plugin fork, and Hammerspoon

### Package (unchanged, stock) [S, `index.js`]

```lua
package_send(PKG, "<action>")
package_send(PKG, "view", "<view>")
package_send(PKG, "<rating|flag|color>", "<value>")
package_send(PKG, "develop", "<param>", value, mode)  -- mode 0 abs, 1 relative
```

The package relays any `"<command>,<args…>"` string to the plugin unchanged
**except** that the overlay setting can swallow commands and
`watchForActiveWindow` drops them when LrC isn't frontmost. It drains one
message per group id (`args[0]`) per 50 ms (§5). It turns the plugin's
`active-photo-result` into `LrImportActive(id, isoSpeed, aperture,
shutterSpeed, focalLength, rating, flag)` via `execute-lua-script`. Named
fields only — that is why the fork repurposes them.

**Views:** `loupe`, `grid`, `compare`, `survey`, `people`, `develop_loupe`,
`develop_before`, `develop_before_after_horiz/vert`,
`develop_reference_horiz/vert`. **rating:** `+1`, `-1`, `1`–`5`. **flag:**
`pick`, `reject`, `remove`. **color:** `red|yellow|green|blue|purple|none`.
`export`/`import` have no plugin handler; never assign.

### `keyboard_send` [M]

```
keyboard_send(delay, [is_modifier, state, code] * n)
  is_modifier 1/0; state 0 up, 1 down, 2 down-and-up; code = HID bitmask
  (LCtrl 1, LShift 2, LAlt 4, LMeta 8) or HID usage ID (a=4 … z=29, Tab=43, '=52)
```

`C.keystroke()` emits down-and-up and unwinds modifiers in reverse; use
nothing else. **Gate every keystroke** on `button_state() > 0`. In use:
`cmd+shift+u` (Auto WB), `cmd+u` (Auto Tone), `j` (clipping), `x` and `o`
(crop, gated on `C`), **`alt+quote` (Invert Mask, gated on `M`; a no-op in
LrC outside a mask [M])**, **`ctrl+alt+cmd+l` (LrC focus — a global
Hammerspoon hotkey, see below)**.

### Hammerspoon (2 Oct)

The board can't focus an app; a keystroke chord caught by a global hotkey
can. `~/.hammerspoon/init.lua`:

```lua
hs.hotkey.bind({"ctrl", "alt", "cmd"}, "L", function()
  hs.application.launchOrFocus("Adobe Lightroom Classic")
end)
```

[M] from the keyboard and from the board. The pattern generalises: anything
outside the plugin's reach is a chord plus a Hammerspoon binding.

### The plugin fork — `fork/`, `com.selbyspink.lrconsole` [M, 0.2.16]

Lives in `grid-userdata/packages/package-lrconsole/lrconsole.lrdevplugin/`
(outside the stock package folder); the stock Grid Editor plugin stays
installed and **disabled** (both bind `127.0.0.1:23111`). Log:
`~/Library/Logs/Adobe/Lightroom/LrClassicLogs/LRConsole.log` — `COMMAND
<name>` in, `REPLY <reason> <json>` out, `PRESET`, `RESET-PARAM`,
`SELECT-TOOL`, `REVEAL-ADJUSTED` traces. **Read it before diagnosing
anything on the LrC side** — it root-caused the mask-entry bug in minutes.

**Every plugin update needs a Lightroom restart.** [M, three times now]
Reload Plug-in starts the new file while the old instance keeps the socket.
Version strings live in Info, Start and MenuItemAbout; `LR Console fork
0.2.x starting` in the log is the proof.

**Reply contract:** `LrImportActive(id, MODULE, LABEL, PARAM, VALUE, rating,
flag)`. MODULE `L` library, `D` develop, `C` develop + crop tool, `M`
develop + masking, otherwise the module name. LABEL normalised (`gray` →
`none`). PARAM/VALUE on echo/follow/revert/reset/preset replies, else `""`.
Sent on: any board command that changes state; every 0.3 s watcher tick
that sees module, tool, photo, label, rating or flag change; every value
echo (**≤ 20/s** since 0.2.14, trailing value always sent); every follow;
`state`.

**Commands beyond stock:**

| Command | Effect |
|---|---|
| `state` | reply now (VSN1 sends it at boot) |
| `color-toggle,<colour>` | that label, or none if already it |
| `reset-param,<p>` | Adobe default; echoes |
| `revert-param,<p>` | back to the turn's start; echoes |
| `preset,sh,ss,hh,hs` | **0.2.15** — split-tone shadow hue/sat, highlight hue/sat in one message; echoes both sats |
| `view,library` | from another module → Library Grid; in Library, Grid ↔ Loupe |
| `select-tool,<t>` / `tool-toggle,<t>` | `masking`, `crop`, `loupe` |

**Relative `develop` on the four 0–360 hues wraps** (`HUE_WRAP`, 0.2.11):
`setValue` clamps otherwise [M].

**Turn:** starts at the first `develop` tick on a parameter; ends at a tick on
a *different* parameter, a revert/reset, or a photo change.

**Slider follow:** in Develop the plugin polls `WATCH` (58 parameters: pages
1–3 globals, the four `Parametric*`, `local_*`) at 5 Hz on echo-idle ticks
(`scanTick % 4` at the 0.05 s loop); a value that moved without a board tick
is `REPLY follow` and VSN1 selects its slot. **A change where either side is
nil is ignored** (0.2.13): every `local_*` flips nil ↔ 0 on mask
enter/exit/create, and the first in WATCH order (Temperature) used to be
taken as a slider move — 952 stray follows in the log, the "mask lands on
Temp" bug [M]. In real use: "works absolutely great" [stated].

**`revealAdjustedControls(true)`** (0.2.16, `Start.lua`, retried until LrC is
in Develop): LrC expands the panel holding any slider the board moves.
"Works PERFECTLY" [stated]. `revealPanel(param)` exists as the per-tick
alternative; not needed.

**SDK facts** [M]: plain `pcall` cannot wrap SDK calls — use `LrTasks.pcall`;
SDK calls from the socket callback run inside `LrTasks.startAsyncTask`;
`develop` calls `switchToModule("develop")`; **LrC rounds `SharpenRadius` to
0.1**, so a finer step is a no-op; `photo:copySettings()` uses whatever the
Copy Settings dialog last had ticked — not controllable from the board.

---

## 9. Develop parameters

**Mask parameters work.** [M] `local_*` for the Basic set. With the Masking
panel open and no mask selected, `setValue` on a `local_*` does nothing.
**`local_Amount` is dead** [M]. `local_Hue` (page 1 Vibrance slot under
Mask) is still **unverified** [?]. **Mask `local_Temperature`/`local_Tint`
are always ±100** [M].

### Colour Grading — flat lookup, no pattern [S, all M on the dial 1 Oct]

| | Hue | Saturation | Luminance |
|---|---|---|---|
| Shadow | `SplitToningShadowHue` | `SplitToningShadowSaturation` | `ColorGradeShadowLum` |
| Midtone | `ColorGradeMidtoneHue` | `ColorGradeMidtoneSat` | `ColorGradeMidtoneLum` |
| Highlight | `SplitToningHighlightHue` | `SplitToningHighlightSaturation` | `ColorGradeHighlightLum` |
| Global | `ColorGradeGlobalHue` | `ColorGradeGlobalSat` | `ColorGradeGlobalLum` |

Plus `SplitToningBalance` (−100/100), `ColorGradeBlending` (0–100; LrC's
panel order is **Blending then Balance**). Hues are 0–360, **0 at 3
o'clock rising anticlockwise** on LrC's wheel, so the board's amount is
−360 [M].

### Parametric curve [M on the dial, 1 Oct]

`ParametricHighlights`, `ParametricLights`, `ParametricDarks`,
`ParametricShadows`, ±100. On page 2 row 1. Split points parked.

### Detail (page 3) [M, 1 Oct]

`Sharpness` (0–150), `SharpenRadius` (0.5–3.0, rounds to 0.1),
`SharpenDetail`, `SharpenEdgeMasking`, `LuminanceSmoothing`,
`LuminanceNoiseReductionDetail`, `LuminanceNoiseReductionContrast`,
`ColorNoiseReduction`, `ColorNoiseReductionDetail`,
`ColorNoiseReductionSmoothness`, `PostCropVignetteAmount`,
`PostCropVignetteMidpoint`, `PostCropVignetteFeather`, `GrainAmount`,
`GrainSize`. `GrainFrequency` (roughness) is the assumed name, parked.

### HSL

`HueAdjustment` / `SaturationAdjustment` / `LuminanceAdjustment` + band, all
eight bands. [M in use]. Echo names match `^(%a-)Adjustment(%a+)$`, which
is how the VSN1 LCD labels them.

---

## 10. The sixteen, and TEK2's zones

VSN1's eight (slots 0–7) and BU16 rows 1–2 (slots 8–15) form one 4×4 radio
under the jog. Slot 15 is Reset on every page. Slot 14 is **Invert Mask on
page 1, present only under Mask** (`mask_only` in `bu16_page`, `kmo`
table); Vig Feather on page 3; null on page 2. **Everything user-facing is
keyed by physical slot.**

**Mask mode (`mk`) mirrors LrC**: each module sets `mk` from the reply's
`M` letter, only when the page has twins. **The rising edge selects
Exposure** (`selb(2)`) [M]; falling keeps the slot. Under `mk` the LCD map
draws only twin-bearing slots and mask-only keys. The board holds no mask
state of its own.

**Crop mode (`rm`) mirrors LrC** (2 Oct): VSN1 sets `rm = (m == "C")`; the
jog straightens while it holds, tap zeroes. TEK2's Crop key toggles the
tool and lights from the letter; BU16's crop X/O gate on it.

**Page 2 zones** live on TEK2 alone: `zn` set by the row-3 radio,
`zt[zn][side]` read by the dials, zone colour on both rings. VSN2 derives
the zone for its readout from the echoed parameter *name*, so it learns the
zone on the first turn, not the key press [stated, accepted].

---

## 11. Screen roles

**VSN1's LCD**: `hdr()` draws the selected parameter's name (slot colour)
and echoed value — or, for ~24 frames after an EN16 echo, the band
("Yellow Sat") or preset name and its value(s) in the band/preset colour;
the hold tag right-aligned (`CROP` / `BEFORE` / `MASK` / `FINE`); the 4×4
map (selection bright; under Mask only live slots); bottom-right the module
letter and reply counter. **Map held**: the six-row map of VSN1 + all of
BU16. Draw at 756/908.

**VSN2 A**: page banner, left knob graphic (Zoom; page 2 Hue with zone,
value, counter). **VSN2 B**: mode word near-black, right knob (Filmstrip;
page 2 Sat with zone and value). The EN16 flash is gone from B. **Map
held**: each screen shows the two key columns beneath it, page-2 row 3 as
zone names in zone colours.

Text renders at ~15 px/char at sizes 9 and 16, ~19 px/char at 20 [M].
**Draw must `draw_area_filled` the whole screen every call** [M]. **Any
array indexed in Draw needs a nil guard** [M]. Per-screen tables live on
`self` [M]. Draw is the clock for the header timer.

---

## 12. Key conventions

- **Frosted = carries state**: Before/After and Map are holds; Crop and
  Mask are toggles bright while LrC is in that tool.
- **Tall smoky = the cull pairs**: Reject/Pick left edge, Prev/Next right.
- **Orange = clears or resets**: Clear (VSN2), Reset (BU16).
- **Cream = Undo/Redo** (since 1 Oct; was Copy/Paste — the caps stayed
  and the functions moved).
- **Light blue = rarely struck, told apart by touch**: Library, Develop,
  Survey, LrC focus.
- Keys whose meaning depends on LrC state show it; **dark is honest**.
- Gate every one-shot on `button_state() > 0` locally or `xv[1] > 0`
  cross-module; holds use both edges.
- **Encoder gesture set, everywhere**: turn = coarse; hold-and-turn = fine;
  tap = revert (jog, TEK2 dials) or reset-to-zero (EN16 HSL); hold ≥ 0.6 s
  = Adobe default (jog, TEK2). Exception by decision: EN16 presets — press
  fires, spin scales [stated 2 Oct].
- Press-wobble: `BLACKOUT` ticks consumed on both edges of every Endless
  dial's button.
- A key's meaning does not change with the page, **except TEK2 row 3 and
  the dials on page 2** [stated 30 Sep — the unpaged-TEK2 convention is
  superseded].

---

## 13. Toolchain

**Files, all in the project's `v2/`** (the container is not persistent —
write back after every build): `gridgen.py`, `lr_common.py` (dial model,
EN16, BU16 helpers, keystroke, positions), `lr_pages.py` (templates,
palettes, presets, `en16()`), `lr_v2.py` (every redesign fragment, TEK2
page 2, VSN2 tone draws), `lr_pages2.py` (page definitions), `build_all.py`.
Templates are the six `Default … Configuration` exports saved as
`templates/Default_<type>_Configuration_<n>.json`.

`python3 build_all.py out MMDD-HHMM` builds all sixteen profiles and checks
budget, wrapper shape, determinism, lint and structure.

**After every generator edit, read the generated event back out of the JSON
and look at it.** Then **diff element code against the previous stamp** so
only the changed configs are imported.

**Deployment** (since 1 Oct): the session has `grid-userdata` connected;
configs are written straight into `configs/` as `LR_r<stamp>_<name>.json`,
the previous stamp moved to `configs/to_delete/` (CJ sweeps), the plugin's
`.lua` files written into the package folder, then **restart LrC**. Import
is manual per module in the Editor; verify by reading back from the module.

**Diagnostics**: `LRConsole.log` first for anything LrC-side. The Editor's
monitor prefixes each line with the source module's `[x, y]`; `print` works
from Setup, Button and `eventrx_cb`. Use the VSN1 LCD with its counter for
anything the monitor can't show. Lua syntax: `lupa` in the container
(`luac` isn't installed).

---

## 14. Deleted — do not resurrect

Each of these was believed, is wrong, and cost time.

| Superseded belief | Reality |
|---|---|
| `h[2]` alone identifies the sending module | Positional, needs `h[3]` (§3) |
| Layer `-1` means "all layers" | Does not work at all (§4) |
| `led_value` controls brightness | It gates; alpha is brightness (§4) |
| TEK2's `eventrx_cb` is broken; report it | No non-VSN module receives it (§7) |
| The USB host must be EN16-A | VSN1 hosts; only EN16-B is bad (§1) |
| `endless_state() - 64` is a fixed per-event delta / an accumulating counter | A velocity; scale by the revolution sum (§5) |
| A real dial range per parameter | Wide range always (§5) |
| Auto-inserted `@sen`/`@sbc` blocks re-clamp ranges | The Editor doesn't re-insert them (§5) |
| Grid Editor 1.7.2 caused a firmware write mismatch | EN16-B host fault (§1) |
| `draw_area_filled(x, y, w, h, c)` | Takes corners (§11) |
| Mask Temperature is Kelvin on raw | Always ±100 (§9) |
| `page_number()` | `page_current()` |
| Parametric split defaults 40/50/60 | 25/50/75 |
| The LrC return path may be dead | Works, reaches every module (§7) |
| `module_position_*` can detect the layout at runtime | TEK2 lies; use the `POSITION` table (§3) |
| The merged sixteen is VSN1 + TEK2 | VSN1 + BU16 (§10) |
| VSN2 rotated 180° with text-free screens | Upright; screens can't rotate |
| A reloaded plugin is picked up by the old socket | Restart LrC after every change (§8) |
| Plain `pcall` around SDK calls | `LrTasks.pcall` (§8) |
| `local_Amount` drives mask Amount | Dead (§9) |
| Mask is a hold on the board, CC117 | Mirrors LrC's tool letter (§10) |
| A turn ends after 0.5 s without a tick | Ends on another parameter, revert/reset or photo change (§8) |
| `lua_table` for any table | Integer keys only; `str_table` for strings (§6) |
| `led_color(1, {r,g,b,a})` | Double braces, always (§4) |
| BU16 at 180°, slot = `23 - element` | Upright; slot = `element + 8` (§2) |
| **"Spinning faster covers less" is an encoder fault / needs a new dial model** | It was index.js's 50 ms drain discarding sends. Batch (§5, 1 Oct) |
| **Rotate is a hold on TEK2 over CC116** | The jog straightens whenever LrC reports `C`; Rotate's key is the Crop toggle (§10, 2 Oct) |
| **TEK2 is unpaged; the dials are always Zoom/Filmstrip** | Page 2 borrows row 3 and both dials (§2, §12) |
| **Page 2 is Detail, page 3 is Colour** | Page 2 is Tone (curve + grading), page 3 is Detail (Layout) |
| **"Tone curve is not on the board"** | Four `Parametric*` slots on page 2 row 1 (§9). Deferred features go in the handover by name — this one was silently dropped on 27 Sep and cost a session |
| **EN16 presets send four messages on a per-element timer chain** | One `preset,…` message; the chain raced across elements and modules (§5, §8) |
| **The EN16 band flash belongs on VSN2 screen B** | It belongs on the VSN1 LCD with the value, like every other readout (§11) |
| **A `local_*` change in follow is a slider move** | nil ↔ value is a mask appearing/disappearing (§8) |
| **VSN1 → TEK2 MIDI is unmeasured** (Page-2 proposal, 1 Oct) | Measured 18 Sep. The local-zone design was still the right call |
| **The "recovering hand" wants Undo/Redo nearest the dials** | CJ moved them to BU16 after use; design reasoning yields to use (1 Oct) |
| **`revealPanel` per tick is how to make LrC show the slider** | `revealAdjustedControls(true)` once does it (§8) |

---

## 15. Open

- **Watch in use** (CJ reports; don't pre-empt): per-rev pace across dials
  post-batching (item 7 coarse/fine was argued against the lossy path);
  echo lag at 20/s; the mask-entry fix; TEK2 blue-cap LED colour.
- `local_Hue` [?]; `ColorGradeBlending` default [?].
- Two simultaneous `develop` senders share the drain slot (§5). Document,
  don't fix, unless the simultaneous case arises in use.
- Hue's residual speed-dependence (§5) — tune only if asked.
- Dial readouts: filmstrip *N of M*, zoom level; slider bars (per-parameter
  range table). Design pass, not started.
- `midi_send` and the one-per-event limit; `header[2]/[3]`; `sysexrx_cb`;
  `immediate_send`'s brick; `lcd_set_backlight` long form [?]; the
  System-Setup nil anomaly (§6) [?].
- VSN2 screen rotation — Intech forum request, no reply.
- "Auto" chord; stars 4–5; Remove tool; virtual copy; vignette style; grain
  roughness; split points — parked by design.
- Page 4 is dark; drop the page button if it never earns content.
- `lr_pages.py`/`lr_common.py` still carry pre-redesign code paths; prune.
  The ASCII diagram above `STAR` in `lr_pages.py` contradicts the code.
- **Publishing** (Intech forum, GitHub): see Handover 2026-10-02 §5. Check
  the stock plugin's licence before publishing the fork.
