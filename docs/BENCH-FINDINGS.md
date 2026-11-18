# LR Console — Bench Findings, 26 September 2026

Return-path bench tests run by CJ on the current (swapped) plate, board loaded
with r0921 + page 3 r0923-1300. To be merged into `LR-Console-Code-Reference.md`
§3, §8, §14 and §15 at the end of the design session. Confidence markers as in
the Reference.

---

## 1. Module positions on the current plate — Reference §3 is stale

The Reference's `module_position_x/y` table lists the **original** plate. The
`m` table above it was updated for the 22 Sep swap; the position table was not.
Reading it caused a wrong module attribution on 26 Sep.

Current plate (since 22 Sep), positions from the host [M, 26 Sep — VSN2's
probe printed `[-2, 0]`; the others follow from the m table]:

| Module | x, y |
|---|---|
| VSN2 | −2, 0 |
| BU16 | −2, −1 |
| EN16-A | −1, 0 |
| EN16-B | −1, −1 |
| VSN1 | 0, 0 |
| TEK2 | 0, −1 |

Original plate (to 21 Sep), history only: EN16-A (−2,0), EN16-B (−2,−1),
VSN2 (−1,0), BU16 (−1,−1).

---

## 2. The LrC → board return path works [M]

Probe: a global `LrImportActive(a..g)` incrementing a counter and printing its
arguments, stored on VSN1 (System Setup) and VSN2 (Hall element 0 Setup — the
System element was full). Both printed count 1 at store, proving the probe.

**Result.** Pressing ★2 on VSN2: both modules printed count 2 with
`177617, ISO 3200, f/8.0, 1/80 sec, 700 mm, 2, <empty>`. The rating argument
matched the key pressed. `execute-lua-script` from the Editor reaches the
modules, and `LrImportActive` is called with the plugin's payload.

**Delivery is to every module that defines the function** — VSN1 and VSN2
both fired on one press. Whether the four modules without it also receive
the script is not directly shown; the natural reading is broadcast to all six
[I], with a silent "call nil" on modules that don't define it. A production
build should define a no-op on every module.

**Why 22 Sep saw nothing.** The Raw Packet view does not show Editor→module
scripts, and/or the frozen window missed it. The mechanism was never at fault.
Record as: *the Raw Packet view is not a probe for `execute-lua-script`; a
printing global is.*

**Plugin side.** `GridEditor.log` (now at
`~/Library/Logs/Adobe/Lightroom/LrClassicLogs/`, moved from `~/Documents` in
the LrC 14 SDK) shows `COMMAND rating` per press. The sender socket was
connected at the time. `sendCurrentActivePhoto` itself is unlogged, so
plugin-side send success is inferred from arrival, not logged.

**Payload note.** Arguments arrive as numbers where numeric (id, rating) and
strings otherwise; the flag argument printed empty on an unflagged photo, not
`0`. Parse defensively.

---

## 3. Rate test, keypress rate [M]

Holding Next did not auto-repeat (Hall keys have no repeat). Pressing Next as
fast as possible from image 394 to 432: **39 consecutive replies, counter 3 →
41, photo ids 177579 → 177617 consecutive, no gaps, no reordering, both
modules in step throughout.** Rate not timed; "as fast as I could press",
roughly 4–6/s [I].

Not yet tested: 10–20/s (needs a scripted sender or a dial). Nothing
misbehaved at keypress rate; no module fault, no array hang.

---

## 4. Socket churn — a constraint on readback design [S, from the log]

`GridEditor.log` (61k lines) holds 2,727 socket timeouts and 375 socket
rebuilds. `Start.lua` tears both sockets down after 5 s of silence and
reconnects; each rebuild is a ~2 s window (`Creating` → `connected`) in which
a reply has nowhere to go. Any readback feature must tolerate a missing reply
and never depend on one arriving. It also means a "slider follows the mouse"
observer could go silent for 2 s at a time; the LCD should show staleness.

---

## 5. Plugin location

`~/Documents/grid-userdata/packages/package-lightroom-classic`
[stated]. The `.lrplugin` is inside; Show Package Contents to reach the Lua.
Fork it out of there before editing (a package update overwrites it).

---

## 6. Plate flipped for reach — VSN2 and TEK2 both turned 180° [M]

CJ tried the hybrid plate with VSN2 top-left and TEK2 bottom-left, then turned
both modules 180° so that VSN2's Hall keys sit in the far-left corner and its
screens meet TEK2's dials at the seam. Preferred [stated]: better access to the
eight far-left keys without reaching over dials; TEK2's keys on the near edge
are a hand-move either way. No caps moved yet.

Measured on VSN2 (screen element Setup, 26 Sep): `module_position_x/y` =
(−2, 0), `module_rotation()` = 2 (180°) — agrees with the monitor prefix
`[-2, 0]`.

**TEK2's `module_position_x/y` is unreliable [M].** `module_rotation()` = 0
(TEK2 now at 0°), but position read (−1, 2), then (2, 1) after a power cycle,
then (−1, 2) again after the BU16 pogo contact was fixed, while the monitor
prefix was `[-2, -1]` every time. On 19 Sep, at 180°, it read (0, −1) and
matched. **Pattern [I]:** both readings are the true (−2, −1) rotated — (−1, 2)
by 90°, (2, 1) by 180° — so TEK2 at 0° applies a spurious rotation to its own
position. VSN2 at 180° reports correctly. Not noise from the flaky BU16.
Consequence: TEK2 → VSN1 signalling (holds, view keys) goes over MIDI, where
position never enters, not `eventrx_cb`. The Editor's prefix is
what the generator's `POSITION` table follows; `module_position_*` must not be
used at runtime for layout detection until this is understood. Whether the
listener-relative `h` values in `eventrx_cb` from TEK2 are affected is
untested — the three behavioural dispatch checks are mandatory on the first
build for this plate.

Positions on this plate [I except VSN2]: VSN2 (−2,0), EN16-A (−1,0),
VSN1 (0,0); TEK2 (−2,−1), EN16-B (−1,−1), BU16 (0,−1).

**Consequences for the generator:** TEK2's `7 − (row·4 + col)` formula no
longer applies — the un-rotated map does, and element 8 is now the physically
*left* dial. VSN2 needs rotation handling it never had: element 0 is
bottom-right of the key block, screen A (12) is on the right, and the small
buttons sit between keys and screens.

## 7. VSN2 screens cannot be rotated in software [M]

- `grid-api.lua` has no rotation parameter on any draw call and no rotate
  global [S].
- Intech forum, May 2026: a user asked for VSN1R screen rotation; Intech staff
  asked whether a rotated-text function would do; no follow-up.
  https://forum.intech.studio/t/rotate-vsn1r-lcd-screen/880
- Probe on VSN2 (26 Sep): `pairs(_G)` enumerated 170 globals; none matched
  `gui`, `rot` or `orient`. Proper null — the enumeration ran (`pcall` true).

So with VSN2 at 180° the screens read upside down. Options recorded: (1)
text-free screens — swatches, bars, pips beside TEK2's dials, text on VSN1;
(2) accept inverted text; (3) VSN2 upright, keys one block lower. Leaning to
(1) [CJ to decide]. Map overlay (24 words on VSN2) is the casualty of (1).
Worth asking Intech for 180° text on the forum thread.

## 8. Plugin fork drop (a) — measured working, 27 Sep [M]

Fork `com.selbyspink.lrconsole` 0.1.1 (project `fork/`), stock plugin
disabled. With the LrIA probe on VSN1 and VSN2, all four steps passed:

| Step | Board printed | Log |
|---|---|---|
| ★2 on the board | `177617 D red "" "" 2 ""` | `COMMAND rating` → `REPLY rating` |
| Label changed with the mouse | label → `yellow`, counter +1 | `REPLY meta` |
| `G` then `D` on the keyboard | module `L` then `D` | `REPLY module` ×2 |
| Click another photo in the filmstrip | new id, its label and rating | `REPLY photo` |

So the reply contract `LrImportActive(id, MODULE, LABEL, PARAM, VALUE,
rating, flag)` works through the stock package unchanged, and the 0.3 s
watcher makes mouse, keyboard and filmstrip changes visible to the board. The
board also receives a state reply on every reconnect (`REPLY module` at start).

**Two things learned the hard way:**
- **Plain `pcall` cannot wrap SDK calls** — they yield to LrC's scheduler and
  fail with "Yielding is not allowed within a C or metamethod call". Use
  `LrTasks.pcall`. Cost one round trip (0.1.0 → 0.1.1).
- **An unlabelled photo reports `colorNameForLabel` = `"gray"`, not `"none"`**
  as the SDK reference says. Normalised in the plugin from drop (b).

## 8a. Drop (b) — value echo, revert, reset — measured working, 27 Sep [M]

Fork 0.2.1. With the LrIA probe on VSN1 and VSN2:

- **Slow jog turn on Exposure:** one `REPLY echo` per tick, 0.05 → 0.60,
  fields 4/5 = `Exposure`, value. Board printed every one.
- **Fast spin:** three `develop` commands inside ~105 ms produced two echoes
  (0.7, 0.75) — the throttle coalesced, the trailing value was sent.
  Note the board's own step accumulation means a spin sends few commands;
  the plugin-side rate limit was not stressed beyond ~30/s momentarily.
- **`revert-param,Exposure`** (throwaway key on BU16): turn to 0.95, pause,
  turn to 1.15, press → 0.95, one `REPLY revert`. Turn-start capture works.
- **`reset-param,Exposure`** → 0, one `REPLY reset`.
- **Reload safety (0.2.1):** a new instance stops the old one before binding.
  Before this, Reload Plug-in left the old instance holding port 23111 —
  the earlier flood of `failed to open localhost:23111`. Restart LrC when
  upgrading from ≤0.2.0; reload is fine thereafter.
- **`gray` → `none`** confirmed on an unlabelled photo.

Reply contract, final: `LrImportActive(id, MODULE, LABEL, PARAM, VALUE, rating, flag)`
with MODULE `L`/`D`/initial, LABEL red|yellow|green|blue|purple|none, PARAM/VALUE
set only on echo/revert/reset replies, flag `P`/``/`R`.

## 8b. Redesign build r0927-1030 — page 1 on the bench, 27 Sep [M]

Loaded with plugin 0.2.2 (see caveat). Survived a power cycle. Nine checks:

| # | Check | Result |
|---|---|---|
| 1 | BU16 row-1 press selects on VSN1's LCD | pass |
| 2 | **BU16 lights its half of the radio from VSN1's MIDI broadcast** (`midirx_cb` on BU16) | **pass — first measured** |
| 3 | **Mask hold on TEK2 reaches VSN1 over MIDI** (`midirx_cb` on VSN1, CC 117) | **pass — first measured** |
| 4 | Jog turn shows the echoed value and counter on VSN1's LCD | pass |
| 5 | EN16 knob flashes its band on VSN2 screen B | pass (value line hidden while the flash shows — design gap, fixed next build) |
| 6 | Pick, Green, Green again → flag, label, label cleared | pass |
| 7 | Jog tap = revert, long press = reset | pass |
| 8 | TEK2 left dial zoom + press toggle; right dial filmstrip | pass |
| 9 | Library key (view,library) | not yet tested — see below |

**Plug-in reload does NOT replace a running instance.** Each Reload Plug-in
gets a fresh Lua environment: the new instance's `_G.running` is nil, so the
0.2.1 handoff never fires, and the old instance keeps its own `_G`, its own
sockets and its own `handleMessage`. Symptoms: the new instance logs
`failed to open localhost:23111` at ~200/s, while commands are handled by
the OLD code. Every plugin update needs a Lightroom restart. The 0.2.1
"reload-safe" claim is withdrawn; the earlier conclusion that a reloaded
file's `handleMessage` is picked up by the old socket was also wrong.

## 9. What this opens and what is still gated

- **Built and measured (drops a, b):** module-aware board, colour-toggle-to-none,
  state on reconnect, value echo, click-to-revert, double-click-to-reset.
- **Still to build:** slider-follows-mouse (drop c, needs a develop observer).
  Jog-as-filmstrip at detent rate is open.
- **Still gated on the 10–20/s test:** a fast jog spin, echo-on-write at dial
  rate, any per-tick value readout.
- **Superseded beliefs** (for Reference §14): "the return path may be dead";
  "which modules execute `execute-lua-script` is unknown".
