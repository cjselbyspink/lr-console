# LR Console — Layout (as built, 2 October 2026)

The design **as built in r1002-1730 and plugin fork 0.2.16**. Supersedes the
27/28 Sep edition; where the two differ, this one is what is on the board.
Confidence markers as in the Code Reference: [M] measured, [S] from source,
[A] assumed, [?] unknown, [stated] CJ said so. Day-by-day record of how it
got here: `claude/LR-Console-Session-Log-2026-09-28.md`; design argument for
page 2: `claude/LR-Console-Page2-Proposal-2026-10-01.md`.

## 1. Plate

As seated. Row numbering is physical: on the left, row 1 is nearest the
screens and row 4 nearest the dials; on the right, row 1 is under the jog and
row 6 nearest you.

```
VSN2  (upright: screens A B · minis · 8 keys)   EN16-A (270°)   VSN1 (LCD · jog · 8 keys)
TEK2  (180°: 8 keys · 2 dials at near edge)     EN16-B (270°)   BU16 (upright)
```

Positions from the host [M]: VSN2 (−2,0), TEK2 (−2,−1), EN16-A (−1,0),
EN16-B (−1,−1), VSN1 (0,0), BU16 (0,−1). `BU16_ROT = 0`. TEK2's own
`module_position_*` is unreliable; TEK2 signals VSN1 over MIDI only
(CC115, Before/After) and otherwise reads the plugin reply like everyone
else.

## 2. Pages

Four pages on VSN1's LCD buttons. **Fixed on every page**: the left block
except TEK2 row 3 on page 2, VSN2's minis, BU16 rows 5–6. **Paged**: the
sixteen (VSN1 rows 1–2 + BU16 rows 1–4 upper half), the VSN2 banner and
knob graphics, and — on page 2 only — TEK2's row 3 and both dials.

| Page | Name | The sixteen | TEK2 dials |
|---|---|---|---|
| 1 | Develop | Basic panel + Vignette; mask twins | Zoom · Filmstrip |
| 2 | Tone | Parametric curve + grading singles | **Hue · Sat** of the selected grading zone |
| 3 | Detail | Sharpening, NR, Vignette, Grain | Zoom · Filmstrip |
| 4 | — | dark | Zoom · Filmstrip |

The "TEK2 is unpaged" convention of September is gone [stated 30 Sep]: a
dip-in page can borrow the dials.

## 3. Keymap — every key on the board

### Left block (VSN2 rows 1–2, TEK2 rows 3–4), column 1 at the plate's left edge

| Row | col 1 | col 2 | col 3 | col 4 |
|---|---|---|---|---|
| 1 VSN2 | **Reject** | **Pick** | Green | Purple |
| 2 VSN2 | Red | Yellow | Blue | **Clear** |
| 3 TEK2 | **Crop** (toggle, mirrors LrC) | Library | Develop | Survey |
| 4 TEK2 | **Mask** (toggle, mirrors LrC) | **Before/After** (hold) | Copy | Paste |

**Page 2, TEK2 row 3 instead**: **Global · Shadows · Midtones · Highlights**
— a radio choosing the colour-grading zone the dials drive; Midtones lit on
entry [A, CJ's call after use]. Order is Global first so S/M/H sit under the
three matching blue caps [stated].

VSN2 minis, left to right: under screen A **★1 · ★2 · ★3 · Auto WB**; under
screen B **Reference · Compare · Auto Tone · Clipping**.

TEK2 dials (near edge), pages 1/3/4: left **Zoom** (turn = in/out, press =
fit ↔ last; press-wobble blacked out); right **Filmstrip** (24 photos per
revolution). Page 2: left **Hue**, right **Sat** of the selected zone, each
with the jog's full press model (hold-and-turn fine, tap revert, hold ≥0.6 s
reset); rings in the zone colour.

### Right block (VSN1 rows 1–2, BU16 rows 1–6), column 1 at the module's left, row 1 under the jog

Page 1 — Develop:

| Row | col 1 | col 2 | col 3 | col 4 |
|---|---|---|---|---|
| 1 VSN1 | Temp | Tint | Exposure | Contrast |
| 2 VSN1 | Highlights | Shadows | Whites | Blacks |
| 3 BU16 | Texture | Clarity | Dehaze | Vibrance |
| 4 BU16 | Saturation | Vignette | **Invert Mask** (mask-only) | **Reset** |
| 5 BU16 | Undo | Redo | **Prev** | **Next** |
| 6 BU16 | **Map** (hold) | **LrC** (focus) | Crop X | Crop O |

Page 2 — Tone (rows 5–6 as page 1):

| Row | col 1 | col 2 | col 3 | col 4 |
|---|---|---|---|---|
| 1 VSN1 | Curve Highlights | Curve Lights | Curve Darks | Curve Shadows |
| 2 VSN1 | — | — | — | — |
| 3 BU16 | Shadow Lum | Midtone Lum | Highlight Lum | Global Lum |
| 4 BU16 | Blending | Balance | — | **Reset** |

Row 2 is a deliberate gap between the curve and the grading remainder
[stated]; row 4 col 3 keeps page 1's gap before Reset.

Page 3 — Detail, LrC panel order (rows 5–6 as page 1):

| Row | col 1 | col 2 | col 3 | col 4 |
|---|---|---|---|---|
| 1 VSN1 | Sharpness | Radius | Detail | Masking |
| 2 VSN1 | Lum NR | Lum Detail | Lum Contrast | Colour NR |
| 3 BU16 | Col Detail | Col Smooth | Vig Amount | Vig Midpoint |
| 4 BU16 | Vig Feather | Grain Amount | Grain Size | **Reset** |

VSN1 jog: turn = selected slot; hold-and-turn = fine; tap = revert to turn
start; hold ≥ 0.6 s and release without turning = Adobe default. **In Crop
the jog straightens** (no key held; tap zeroes the angle). VSN1's four LCD
buttons = pages 1–4.

## 4. Cap plan

| Cap | Keys | Where |
|---|---|---|
| Tall smoky (4) | Reject, Pick | left block row 1 cols 1–2 |
| | Prev, Next | BU16 row 5 cols 3–4 |
| Frosted (4) | Crop, Mask, Before/After | TEK2 row 3 col 1; row 4 cols 1–2 |
| | Map | BU16 row 6 col 1 |
| Orange (2) | Clear | VSN2 row 2 col 4 |
| | Reset | BU16 row 4 col 4 |
| Cream (2) | Undo, Redo | BU16 row 5 cols 1–2 |
| Light blue (4) | Library, Develop, Survey | TEK2 row 3 cols 2–4 |
| | LrC (focus) | BU16 row 6 col 2 |
| Black | everything else, incl. Copy/Paste on TEK2 | |

Frosted = carries state: the holds (bright while held) plus Crop and Mask,
bright while LrC is in that tool. Light blue = rarely struck, told apart by
touch. **Caps were not swapped** when Copy/Paste and Undo/Redo changed
modules on 1 Oct — the LED palettes followed the caps instead (cream LEDs on
Undo/Redo, grey-blue on Copy/Paste). On page 2 TEK2 row 3's frosted + three
blue caps carry the zone keys; accepted mismatch on a dip-in page. TEK2 row
3 col 1 wants relabelling "Crop".

## 5. Left block — behaviour

- **Colour labels** send `color-toggle,<colour>`: the same colour again
  clears it. Full brightness only while the photo carries that label, 15 %
  otherwise; Reject/Pick likewise for the flag. Driven by every plugin
  reply, so mouse changes show within 0.3 s.
- **Clear** = rating 0 + flag remove (timer queue). Not the label.
- **Crop** (2 Oct): `tool-toggle,crop`; lit while the plugin reports `C`.
  **The jog straightens whenever LrC is in Crop**, however Crop was entered
  (key, `R`, mouse) — `rm` mirrors the letter; the old Rotate hold and
  CC116 are gone. LCD tag `CROP`.
- **Mask**: `tool-toggle,masking`; lit while the plugin reports `M`. Mask
  mode on the board mirrors LrC; see §6.
- **Before/After**: held, `view develop_before`; released, `develop_loupe`.
- **Library**: from any other module → Library Grid; in Library, Grid ↔
  Loupe. **Develop** = `view develop_loupe`. **Survey** = `view survey`.
- **Copy / Paste**: the plugin's develop-settings copy/paste. The Copy
  Settings dialog's ticks decide what is copied — set them once in LrC;
  not board-controllable [M].
- Page 2: **zone keys** set `zn` locally on TEK2; nothing crosses a module.
  **Hue** −360 per revolution (clockwise lowers hue, matching LrC's wheel
  [M]), wraps at 0/360 (plugin `HUE_WRAP`); **Sat** 100 per revolution.

**VSN2 screens** (upright). A: page banner and the left knob (Zoom; on
page 2 **Hue** with zone name, value and reply counter from the echo). B:
the LrC mode word near-black (Library / Develop / Crop / Mask, or the
module's name) and the right knob (Filmstrip; on page 2 **Sat** with zone
and value). **Map held**: each screen shows the two key columns beneath it
(row-major, four rows), page-2 row 3 showing the zone names in zone
colours. The EN16 band flash that used to live on screen B moved to the
VSN1 LCD on 2 Oct.

## 6. Right block — the sixteen and the actions

The 4×4 under the jog is VSN1's eight + BU16 rows 1–2 (slots 0–15, Reset
fixed at slot 15). Selection is a radio across both modules (VSN1 → BU16 on
CC119). Boot/entry selection: Exposure on page 1, Curve Lights on page 2.

**Mask mode (page 1 only — the only page with twins)**: the plugin's `M`
letter puts the board in mask mode within ~0.3 s whichever way masking was
entered. The selected slot drives its `local_` twin; Vibrance → mask Hue;
Vignette has no twin. Slots without a twin and Reset are dark, inert and
**absent from the LCD map**; slot 14 becomes **Invert Mask** (Option+' as
a keystroke; lit and live under Mask only [M]). **Entering a mask selects
Exposure** [M, 1–2 Oct]; leaving keeps the selection. The plugin ignores
`nil ↔ value` flips on `local_*` in slider follow — those are masks
appearing and disappearing, not slider moves, and were the cause of the
"lands on Temp" bug [M, from the log].

**BU16 rows 5–6** (fixed): Undo/Redo; Prev/Next mirror Reject/Pick at the
other edge; **Map** (hold); **LrC** types Ctrl+Opt+Cmd+L, which Hammerspoon
on the Mac binds to "activate Lightroom Classic" [M] — the fix for "typed
into Claude, turned a knob, nothing happened"; **Crop X / Crop O** off and
inert unless the crop tool is up (outside it `x` rejects the photo [M]).

**Map** (hold): VSN1's LCD shows the whole block under the jog, six rows;
VSN2 shows the left block.

## 7. Brightness convention

Every key idles at alpha **0.15**, goes to **1** while pressed, selected,
or its LrC state is active, and is **off** (`led_value 0`) when it cannot
act. Dial rings idle at **0.05**, 0.5 while turning, back 400 ms after the
last tick. EN16 knobs 0.05 idle, 0.5 while turning. BU16's colours are
scaled by `BU16_TINT = (1.0, 0.7, 0.6)` because its LEDs run green/blue of
VSN1's at the same RGB [M]; TEK2 is untinted, so the blue-cap keys have two
constants (`VIEW_KEY` on BU16, `VIEW_TEK` on TEK2 — "not perfect, leave
it" [stated 2 Oct]).

## 8. Encoders and the plugin

- **Jog turn**: relative `develop,<param>,<delta>,1`, echoed back as value.
  The dial fires at ~110 Hz while moving and index.js passes **one
  `develop` message per 50 ms, discarding the rest** [S], so deltas are
  accumulated and sent every sixth event (`SEND_EVERY = 6`, 1 Oct [M]: a
  fast rev used to deliver a sixth of a slow one; now equal within the §7
  non-linearity). Per-rev amounts are nominal — Highlights ≈ −30/rev
  coarse, −10 fine, "a good pace" [stated].
- **Tap**: `revert-param` — back to where the current turn started. A turn
  starts at the first tick on a parameter and ends at a tick on a different
  parameter, a revert/reset, or a photo change. **Hold ≥ 0.6 s, release
  without turning**: `reset-param`.
- **EN16 HSL knobs** (2 Oct): **5 per detent, 1 while held, tap = reset the
  band to 0** — the jog's gesture set. Detents accumulate and go out at most
  every 60 ms on the knob's timer (same drain). LED ring bright while
  turning. The **VSN1 LCD** shows band + Hue/Sat/Lum + value in the band
  colour for ~1 s from the echo.
- **EN16 presets** (row 3): press fires, spin scales strength 0–300 % of the
  preset's base saturations (so Teal/orange tops out at 60/60 — deliberate).
  **One message** `preset,sh,ss,hh,hs` to the plugin (0.2.15), which sets all
  four and echoes both sats; the LCD shows the preset name and "sh / hl".
  Press-to-zero deliberately *not* applied here [stated]. Balance untouched.
- **Slider follow**: the plugin polls 58 parameters at 5 Hz in Develop; a
  value that moved without a board tick is echoed and VSN1 selects its slot.
  "Works absolutely great" [stated 1 Oct].
- **Echo** at up to 20/s (0.2.14, was 10): "much snappier, less
  overshooting; I can rely on the VSN1 screen to edit" [stated 2 Oct].
- **`revealAdjustedControls(true)`** (0.2.16): LrC expands the panel of any
  slider the board moves. "Works PERFECTLY" [stated 2 Oct].

## 9. VSN1 LCD

Selected parameter's name (size 20, slot colour) — or, for ~24 frames after
an EN16 echo, the band/preset header in its colour; the hold in force
right-aligned (CROP / BEFORE / MASK / FINE); the echoed value (or the
EN16 value / preset sats); the 4×4 map of the sixteen with the selection
bright and, under Mask, only twin-bearing and mask-only slots drawn; and —
bottom-right, near-black — the module letter and reply counter (`D25`), so
a stale value can be told from a resting one. Map held: the six-row map
instead. The header lives in `hdr()` on key 4's Setup; the Draw is at
756/908.

## 10. Parked

- Slider graphic for the value (needs a per-parameter range table).
- "Auto" as a momentary modifier.
- Both left modules rotated 180° in place, once Intech ship screen rotation.
- Stars 4–5; Remove tool; Virtual copy; Vignette style; Grain roughness
  (`GrainFrequency` [A]); parametric split points.
- Filmstrip *N of M* and zoom-level readouts.
- Preset-column gesture consistency (decided against, 2 Oct; revisit only
  if a thumb reaches for a tap-to-zero).
