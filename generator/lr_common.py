"""Shared Lua for the LR Console — six-module architecture.

Rewritten 8 September 2026. This is a replacement, not a patch: the three-module
version's dispatch, key conventions and LED calls were all superseded by measured
hardware behaviour. Nothing here is carried over untested.

WHAT CHANGED AND WHY
--------------------
* Dispatch is positional and packed. `(h[2] - mbx) * 2 + (mby - h[3])` yields
  0-5 by plate position (column-major, top first). Which module holds which m
  is derived from POSITION below — never hard-code an m value.
  The old `h[2]`-only test conflated the two EN16s, misread BU16 as TEK2, and
  dropped TEK2 events on the floor entirely.
* Button edges come from `xv[1]`, not from a press counter. `xv` is
  {value, min, max}; a press reads 127/0/127 and a release 0/0/127, on both the
  local and cross-module paths. `self.prss` is gone.
* No LED layer -1 anywhere. It fails silently on both `led_color` and
  `led_value`. Every call names an explicit layer.
* `led_color` alpha is the brightness control; `led_value` is an on/off gate
  (and a proportional fill meter on endless rings, which is a third behaviour).
* Every element sets its own range. Generated configs carry no @sen/@sec GUI
  blocks, so encoder/endless mode, min, max and sensitivity are ours to set.
* Undo / Redo / Before-After / Zoom live on BU16, per design spec §2. The
  "TEK2 keys 6-7 are always Undo and Before/After" rule was a three-module
  workaround and is deleted, freeing all eight TEK2 keys for the merged 16.
* Flash labels are computed, not tabulated. A 66-entry `flab` table would not
  fit in one 908-character event; EN16 labels derive from band/property tables
  and everything else is a short per-module lookup.

BUDGET MAP (VSN1, per page)
---------------------------
The 908-character limit forces shared tables to be spread across elements.
Globals cross elements freely, so placement is a budget decision only.

    element 255 Setup   kcol, setc, radio, smm, fls, ini loop
    element 0   Setup   blab (BU16 labels), vlab (VSN2 labels)
    element 1   Setup   kpar (16 params), krst (resets), kstp (step scaling)
    element 8   Setup   selb, dcy, eventrx_cb
    element 13  Setup   bnr, klab, bnd, prp, brgb
    element 13  Draw    the render

Setup runs top-to-bottom by element number, then again for every element via
the System element's ini loop, which must come last. Anything defined in 255
is therefore nil on the first pass — calls into it are guarded.
"""

PKG = '"package-lightroom-classic"'

# ------------------------------------------------- the VSN1 -> TEK2 MIDI radio
# MEASURED 18 September. Module-to-module MIDI is dispatched to non-VSN modules
# even though eventrx_cb is not: VSN1 called midi_send and TEK2's midirx_cb
# fired, with header {14, 127, 126}. header[1] == 14 marks grid-internal
# traffic; the annotation's 13 marks the host. This is the only known way to
# push state to a module that cannot listen on eventrx_cb (§7).
#
# The header's sx/sy do NOT follow the eventrx_cb convention — a VSN1 source
# read 127,126 at TEK2 where the §3 rule predicts 127,128. Unresolved whether
# that is an inverted sign or the listener's own position. [?] Do not reuse the
# §3 arithmetic here; the CC number is the gate, not the source.
#
# Channel 15 (MIDI channel 16), CC 119 — undefined in the MIDI spec, above
# everything in ordinary use and below the channel-mode messages at 120+. The
# message also leaves for the host, so this must stay a number nothing on the
# machine maps. Value is the selected physical slot, 0-15, which fits a CC.
MIDI_CH, MIDI_CC_SLOT = 15, 119

# --------------------------------------------------------------- module identity
# Positional, measured. Index into the packed dispatch value.
EN16A, EN16B, VSN2, BU16, VSN1, TEK2 = range(6)

MODULE_NAMES = {EN16A: 'EN16-A', EN16B: 'EN16-B', VSN2: 'VSN2',
                BU16: 'BU16', VSN1: 'VSN1', TEK2: 'TEK2'}

# (mbx, mby) per listening module: h[2] and h[3] as read when the *source* is
# the top-left module. Derived from the listener's own grid position — h[2] is
# source column relative to the listener, h[3] source row, 127 meaning "same".
# Confirmed for VSN1; the VSN2 value follows from the same geometry.
#
# Everything positional now derives from POSITION, the modules' own
# module_position_x/y readings. module_position_* reports relative to the USB
# host (VSN1 sits at 0,0 and is the host) [inferred from both facts agreeing].
# Rearranging the plate is ONE edit here plus a behavioural check: BU16 Map key
# (VSN2 overlay), BU16 Zoom-hold on the jog dial, an EN16 knob flash on VSN2.
#
#   m = (h[2] - mbx) * 2 + (mby - h[3])  ==  (source_x - XMIN) * 2 + (YMAX - source_y)
#   mbx = 127 - listener_x + XMIN,   mby = 127 + YMAX - listener_y
#
# Measured 18 Sep (original layout):
POS_ORIGINAL = {EN16A: (-2, 0), EN16B: (-2, -1), VSN2: (-1, 0),
                BU16: (-1, -1), VSN1: (0, 0), TEK2: (0, -1)}
# Current plate since 22 Sep: EN16 pair in the middle column, VSN2/BU16 left.
# MEASURED — all three behavioural checks passed on r0921-1700.
POS_SWAPPED = {VSN2: (-2, 0), BU16: (-2, -1), EN16A: (-1, 0),
               EN16B: (-1, -1), VSN1: (0, 0), TEK2: (0, -1)}
# Plate since 27 Sep (redesign): VSN2 over TEK2 on the left, EN16 pair in the
# middle, VSN1 over BU16 on the right. No module rotation changed — positions
# only. VSN2 measured (-2, 0) by module_position_* and by the monitor prefix;
# the others from the monitor prefixes [M, 26-27 Sep]. TEK2's own
# module_position_* reading is unreliable at this position (bench findings §6),
# which is why TEK2 -> VSN1 signalling goes over MIDI, never eventrx_cb.
POS_FLIPPED = {VSN2: (-2, 0), TEK2: (-2, -1), EN16A: (-1, 0),
               EN16B: (-1, -1), VSN1: (0, 0), BU16: (0, -1)}
LAYOUTS = {'original': POS_ORIGINAL, 'swapped': POS_SWAPPED, 'flipped': POS_FLIPPED}
POSITION = POS_SWAPPED


def set_layout(name):
    """Select a plate arrangement; call before generating anything."""
    global POSITION, M, LISTENER_BASE
    POSITION = LAYOUTS[name]
    xs = [x for x, _ in POSITION.values()]
    ys = [y for _, y in POSITION.values()]
    xmin, ymax = min(xs), max(ys)
    assert max(xs) - xmin == 2 and ymax - min(ys) == 1, 'dispatch packs a 3x2 plate'
    M = {mod: (x - xmin) * 2 + (ymax - y) for mod, (x, y) in POSITION.items()}
    assert sorted(M.values()) == list(range(6))
    LISTENER_BASE = {mod: (127 - POSITION[mod][0] + xmin, 127 + ymax - POSITION[mod][1])
                     for mod in (VSN1, VSN2, TEK2)}
    # The VSN2 band flash assumes EN16-A directly above EN16-B.
    assert M[EN16B] == M[EN16A] + 1


set_layout('swapped')


# ------------------------------------------------------------------- Lua helpers
def lua_value(v):
    if isinstance(v, str):
        return '"%s"' % v
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, (list, tuple)):
        return '{%s}' % ','.join(lua_value(x) for x in v)
    return repr(v) if isinstance(v, float) else str(v)


def lua_table(name, entries):
    """entries: {int_key: value} -> `name = { [0] = ..., [1] = ... }`.

    Always emitted as one table literal. Appending separate assignment
    statements instead under-predicts the Editor's own length readout by
    roughly 24 characters per statement — mechanism unknown, so don't.
    """
    body = ', '.join('[%d] = %s' % (k, lua_value(entries[k]))
                     for k in sorted(entries))
    return '%s = { %s }' % (name, body)


# ------------------------------------------------------------- merged 16 mapping
# VSN1's eight Hall keys sit directly above TEK2's eight. TEK2 is mounted at
# 180 degrees and the Editor does NOT remap for it (measured: the physically
# top-left TEK2 key reports element 7), so the lower half runs backwards.
#
#   physical slot p   0..3   VSN1 top row      element p
#                     4..7   VSN1 bottom row   element p
#                     8..11  TEK2 top row      element 15 - p
#                    12..15  TEK2 bottom row   element 15 - p
#
# Everything user-facing — parameter lists, labels, colours, the LCD key map —
# is keyed by physical slot. Only the dispatch converts.

def merged_owner(p):
    """Physical slot 0-15 -> (module, element index on that module)."""
    return (VSN1, p) if p < 8 else (TEK2, 15 - p)


def merged_check(items):
    """Fail loudly if a page's merged list isn't exactly 16 physical slots."""
    missing = [p for p in range(16) if p not in items]
    if missing:
        raise ValueError('merged list missing physical slots: %s' % missing)
    return items


# -------------------------------------------------------------- VSN1 System (255)
# LED convention (28 Sep, board-wide): a key idles DIM, goes FULL while
# pressed / selected / its LrC state is active, and is OFF (led_value 0)
# when it cannot act. Alpha carries brightness, led_value only gates
# (Reference §4). Dials: ring at RING_IDLE, RING_ON while turning.
IDLE = 0.15
RING_IDLE, RING_ON, RING_MS = 0.05, 0.5, 400

SETC = """
function setc(e, c)
  if c then element[e]:led_color(1, {{c[1], c[2], c[3], %s}}) end
end
""" % IDLE

# Radio over the eight *local* keys only. TEK2's half of the merged 16 lights
# itself, from its own System element, off the same physical-slot number.
#
# VSN1_DIM is the resting level of an assigned-but-unselected VSN1 key. It was
# briefly raised to 40 to match TEK2, on the assumption that TEK2 would join the
# radio. It cannot (see tek2_dispatch), so TEK2's eight sit at full static
# colour and 0 is restored — the 17 September behaviour. One number if the
# judgement ever changes.
#
# An unassigned slot — no kcol entry — goes fully dark either way, so page 2's
# two spare VSN1 keys never acquire a glow. That guard is worth keeping.
VSN1_DIM = 0

# TEK2's own resting level, used only if TEK2 ever lights a radio. Separate
# constant: the two modules are no longer one lighting decision.
RADIO_DIM = 40

RADIO = """
function radio(p)
  for i = 0, 7 do
    element[i]:led_value(1, (i == p) and 255 or %s)
  end
  local c = kcol[p]
  if c then element[8]:led_color(2, {{c[1], c[2], c[3], 0.2}}) end
end
""" % ('(kcol[i] and %d or 0)' % VSN1_DIM if VSN1_DIM else '0')

# Range setting. No @sen block exists on a generated page, so mode and
# sensitivity are set here every time, not just min/max.
# Every VSN1 dial parameter is driven by relative sends, and endless_min/max
# clamp the encoder's own counter regardless of mode. A real parameter range
# here would hard-stop the dial after ~100 ticks. Wide range always; Lightroom
# owns the limits. Reset values still come from krst, in absolute mode.
SMM = """
function smm()
  element[8]:endless_mode(0)
  element[8]:endless_sensitivity(50)
  element[8]:endless_min(-100000)
  element[8]:endless_max(100000)
  element[8]:endless_value(0)
end
"""

# One flash slot, set by whichever module last sent an event. Replaces the old
# flab/flab_c index space entirely.
FLS = """
function fls(s, c)
  fl_s = s
  fl_c = c
  fl_t = 24
end
"""

INI_LOOP = 'for i = 0, #element - 1 do element[i]:ini() end'


def vsn1_system(kcol):
    """kcol: {physical_slot: (r,g,b)} for all 16 merged slots."""
    return '\n'.join([lua_table('kcol', {k: list(v) for k, v in kcol.items()}),
                      SETC, RADIO, SMM, FLS, 'fl_t = 0', INI_LOOP])


# ------------------------------------------------------------------ VSN1 dial (8)
# selb is the single funnel for every selection change on VSN1 — it is called
# from eventrx_cb for VSN1's own keys and for TEK2's, and once at Setup. One
# midi_send here keeps TEK2's half in step with no second code path.
SELB = """
function selb(p)
  self.l_b = p
  local r = kpar[p]
  if r then
    smm()
    element[8]:led_value(2, 255)
  else
    element[8]:led_value(2, 0)
  end
  radio(p)
  midi_send(%d, 176, %d, p)
end
""" % (MIDI_CH, MIDI_CC_SLOT)

def vsn1_dispatch(merged=True, zoom_key=11, rotate_key=7, before_key=3):
    """The eventrx_cb body.

    merged=False for pages where TEK2 keeps its own keys for local zone select
    (page 2), so TEK2 key presses are ignored here rather than selecting.

    Two BU16 keys act as cross-module modifiers: held, they change what the VSN1
    dial does. Neither sends anything itself — a tap must not disturb the zoom
    level or the crop angle. BU16 is unpaged, so both work on all four pages.
    """
    mbx, mby = LISTENER_BASE[VSN1]
    tek = ('    if i < 8 and xv[1] > 0 then selb(15 - i) end'
           if merged else '    return')
    return """
self.eventrx_cb = function(self, h, e, xv, n)
  local m = (h[2] - %d) * 2 + (%d - h[3])
  local i = e[2]
  if m == %d then
    if i < 8 and xv[1] > 0 then selb(i) end
  elseif m == %d then
%s
  elseif m == %d then
    if i == %d then
      zm = xv[1] > 0
    elseif i == %d then
      rm = xv[1] > 0
    elseif i == %d then
      bm = xv[1] > 0
    end
  end
end
""" % (mbx, mby, M[VSN1], M[TEK2], tek, M[BU16], zoom_key, rotate_key, before_key)


# MEASURED, 17 September. endless_state() - 64 is a rate, linear in speed, and
# the SUM over one revolution is speed-invariant at ~91,000 units:
#
#     slow      n 321   sum 90,184   avg 281
#     moderate  n 248   sum 91,492   avg 370
#     brisk     n  83   sum 61,041   avg 1326   (39 spikes excluded)
#
# The brisk run reads low only because the excluded spikes were real movement.
# Events fire on a fixed clock (~110 Hz), not per unit of movement, so a slow
# turn produces four times as many events each a quarter the size. That is why
# the per-event average looked superlinear and cost three wrong models.
#
# Two quirks the arithmetic has to handle:
#
# SPIKES. Occasional readings 10-50x their neighbours, scaling with speed (2, 2,
# 39 across the three runs) — a sampling artefact when the encoder moves far
# between reads, not a position glitch. Dropping them loses real movement, so
# substitute the last good reading instead and the total stays honest.
#
# FLOOR. The smallest reading is 278 at ANY speed, in every run. That is a hard
# quantum of 278/91,000 — about 0.3% of a revolution — so the minimum step is
# fixed however the scaling is set. Fine mode exists because of this, not as a
# convenience: at 20 degrees per revolution the coarse minimum is 0.06 degrees.
REV_UNITS = 91000
SPIKE = 3000
# 20 Nov: runaway guard. A spike is replaced by the last good reading (above),
# but nothing limited how many in a row: a RUN of out-of-range readings kept
# repeating the last real rate, ~3.3 tint per event at 110 Hz, 0 -> 150 in
# ~0.4 s with no hand on the dial [reported 20 Nov; mechanism INFERRED, not
# yet measured]. Measured spikes are isolated (2, 2 and 39-in-83 on a brisk
# spin), so SUB_MAX consecutive substitutions keep a brisk turn honest and
# anything longer counts as zero.
SUB_MAX = 2
# Ticks discarded after every selection change, ~110 Hz, so ~90 ms: a key
# press beside the jog, or the counter reset in smm(), must not move the new
# parameter [guard, cause unmeasured].
SEL_BLACKOUT = 10
FINE = 0.15   # 20 Oct: was 0.1 [stated: fine wants slightly less rotation]

# Press-wobble. A press or release on the Endless dial produces a few spurious
# turn ticks, which set `ft` (so a tap's reset is silently eaten) and, under
# Rotate, nudge the crop angle. BLACKOUT ticks after either button edge are
# discarded before anything else happens. ~110 Hz, so 3 is ~27 ms — well below
# perception on a deliberate press-and-turn.
BLACKOUT = 3

# Lightroom accepts at most one message per 50 ms: index.js keys every develop
# send on the literal group id "develop", overwrites the stored args on each
# call, and drains one id per 50 ms setInterval. Every relative delta generated
# inside that window except the last is DISCARDED — lost movement, not a stale
# update. SEND_EVERY = n sends on every nth turn event, with self.ac carrying
# the remainder across the gap, so nothing is lost to the drain. 1 sends on
# every event (the behaviour up to r0918). ~6 matches the drain at 110 Hz.
#
# NOT yet measured: §7 records that relative sends don't scale linearly with
# delta magnitude, so a batched delta may not equal the sum of its parts. Bench
# test — one revolution at three speeds, SEND_EVERY at 1 and 6, read Exposure
# off the LrC slider — before changing the default.
SEND_EVERY = 6   # 1 Oct: measured on page 3 Shadow Hue — fast rev == slow rev == ~360 at 6; at 1 a fast rev lost ~5/6 and page 2 at 120/rev gave 8 (fast) to 42 (very slow)

# Per-parameter amount per full revolution, the resolution to accumulate in,
# and an optional FINE resolution used while the dial is held (kpar field 4).
# Fine mode runs at a tenth of the rate, so a finer step there costs nothing
# against the 20 Hz drain; the same step in coarse mode would. Fractional
# relative values work (Exposure moves in 0.05-stop steps).
DIAL_ENDLESS = """
if (self.bo or 0) > 0 then
  self.bo = self.bo - 1
  do return end
end
local v = self:endless_state() - 64
if v > %d or v < -%d then v = self.av or 0 else self.av = v end
if fm then ft = true end
local sc = (fm and %s or 1) / %d
if zm then
  package_send(%s, (v > 0) and "zoom-in" or "zoom-out")
else
  local p, amt, res
  if rm then
    p, amt, res = "straightenAngle", 20, 0.01
  else
    local r = kpar[self.l_b]
    if r then p, amt, res = r[1], r[2] or 100, (fm and r[4]) or r[3] or 1 end
  end
  if p then
    self.ac = (self.ac or 0) + v * sc * amt / res
    self.gt = (self.gt or 0) + 1
    if self.gt >= %d then
      self.gt = 0
      local w = self.ac >= 0 and self.ac // 1 or -((-self.ac) // 1)
      self.ac = self.ac - w
      if w ~= 0 then
        package_send(%s, "develop", p, w * res, 1)
      end
    end
  end
end
""" % (SPIKE, SPIKE, FINE, REV_UNITS, PKG, SEND_EVERY, PKG)

# Press and hold turns the dial fine; a tap with no movement resets — or, with
# the Zoom key held, toggles the zoom (LrC's zoom-toggle: fit <-> the last zoom
# level, which the dial has just set). The dial knows whether it turned while
# held, so a tap and a press-and-turn are distinct; the blackout is what keeps
# a wobble from counting as a turn. self.bo is set on BOTH edges: the release
# wobbles as much as the press.
DIAL_BUTTON = """
self.bo = %d
if self:button_state() > 0 then
  fm = true
  ft = false
else
  fm = false
  if not ft then
    if rm then
      package_send(%s, "develop", "straightenAngle", 0, 0)
    elseif zm then
      package_send(%s, "zoom-toggle")
    else
      local r = kpar[self.l_b]
      local k = kkey[self.l_b]
      if k then
        k()
      elseif r then
        package_send(%s, "develop", r[1], krst[self.l_b] or 0, 0)
      end
    end
  end
end
""" % (BLACKOUT, PKG, PKG, PKG)


def vsn1_dial(merged=True, start=0, zoom_key=11, rotate_key=7, before_key=3):
    return {
        0: [('cb', '\n'.join([SELB, vsn1_dispatch(merged, zoom_key, rotate_key, before_key),
                              'if radio then selb(%d) end' % start]))],
        3: [('cb', DIAL_BUTTON)],
        7: [('cb', DIAL_ENDLESS)],
    }


# ------------------------------------------------------------------ VSN1 LCD (13)
# Steady state is a literal map of the sixteen keys sitting under the screen:
# two rows for VSN1's own, a rule, two rows for TEK2's. The selected slot is
# full brightness, the rest at a third. Above it, the selected parameter's full
# name, and a line naming what TEK2's two dials currently drive.
#
# The banner is the page theme only, and only for the first ~30 Draw ticks.
# It is not the layout reminder — the key map is, and the key map is permanent.
LCD_DRAW = """
self:draw_area_filled(0, 0, 320, 240, {0, 0, 0})
local s = element[8].l_b
if zm then
  self:draw_text_fast("ZOOM", 8, 34, 45, {255, 255, 255})
elseif rm then
  self:draw_text_fast(fm and "ROT FINE" or "ROTATE", 8, 34, 45, {255, 255, 255})
elseif bm then
  self:draw_text_fast("BEFORE", 8, 34, 45, {255, 255, 255})
elseif fm then
  self:draw_text_fast("FINE", 8, 34, 45, {255, 255, 255})
else
  self:draw_text_fast(klab[s] or "-", 8, 34, 20, kcol[s] or {255, 255, 255})
end
self:draw_area_filled(0, 152, 320, 153, {70, 70, 70})
for i = 0, 15 do
  if klab[i] then
    local c = kcol[i] or {255, 255, 255}
    if i ~= s then c = {c[1] // 3, c[2] // 3, c[3] // 3} end
    local y = 104 + (i // 4) * 26
    if i > 7 then y = y + 14 end
    self:draw_text_fast(ksho[i], 8 + (i % 4) * 78, y, 9, c)
  end
end
self:draw_swap()
"""


def vsn1_lcd(klab, short=None):
    """klab: {physical_slot: label} for up to 16 merged slots. Unpopulated
    slots are simply absent and the Draw loop's guard skips them.

    short: {slot: 4-char label} for the key map. Defaults to the first four
    characters of the full name, which is fine where names differ early and
    useless where they do not — page 4's Vignette and Noise groups all collapse
    to the same four letters. Supply explicit ones there."""
    short = short or {}
    ksho = {k: short.get(k, v[:4]) for k, v in klab.items()}
    setup = '\n'.join(['lcd_set_backlight(255)', lua_table('klab', klab),
                       lua_table('ksho', ksho),
                       'zm = false', 'rm = false', 'fm = false', 'bm = false'])
    return {0: [('cb', setup)], 8: [('cb', LCD_DRAW)]}


# ----------------------------------------------------------------- VSN1 keys 0-7
def vsn1_keys(tables_0='', tables_1=''):
    """Hall keys light themselves and carry the two overflow table blocks.

    tables_0 / tables_1 are plain Lua source strings — whatever didn't fit in
    the LCD's or the dial's own Setup. They come first in each Setup so that a
    nil kcol on the first top-to-bottom pass — kcol lives in element 255, which
    runs last — cannot abort the Setup before the tables exist.
    """
    out = {}
    for i in range(8):
        pre = {0: tables_0, 1: tables_1}.get(i, '')
        body = [pre] if pre else []
        body.append('if kcol then setc(%d, kcol[%d]) end' % (i, i))
        out[i] = {0: [('cb', '\n'.join(body))]}
    return out


def vsn1_page_buttons(pages=(0, 1, 2, 3)):
    """Elements 9-12. Gated on the press edge — the old ungated version fired
    page_load twice per press."""
    return {9 + k: {0: [('sn', 'self:element_name("Page %d")' % (n + 1))],
                    3: [('cb', 'if self:button_state() > 0 then page_load(%d) end' % n)]}
            for k, n in enumerate(pages)}


# ------------------------------------------------------------------------- TEK2
# TEK2 at 180 degrees, not remapped by the Editor. Element 8 is the physically
# RIGHT dial, element 9 the physically LEFT one — measured, and the reverse of
# what the unrotated module does.
TEK2_LEFT_DIAL, TEK2_RIGHT_DIAL = 9, 8


def tek2_midi_rx():
    """TEK2's ear, via MIDI, since eventrx_cb never reaches it.

    Gated on header[1] ~= 13 so host traffic can never move the radio, and on
    the exact CC so nothing else on the bus can either. `radio` is a global from
    element 255, which runs last, so the first Setup pass assigns a closure that
    resolves it at call time — no guard needed inside the callback.
    """
    return """
self.midirx_cb = function(self, h, d)
  if h[1] ~= 13 and d[2] == 176 and d[3] == %d then
    radio(d[4])
  end
end
""" % MIDI_CC_SLOT


TEK2_SETD = """
function setd(e, r, wrap)
  if r then
    element[e]:endless_mode(0)
    element[e]:endless_sensitivity(50)
    element[e]:endless_min(-100000)
    element[e]:endless_max(100000)
    element[e]:endless_value(0)
    element[e]:led_color(2, {{r[4], r[5], r[6], 0.35}})
    element[e]:led_value(2, 255)
  else
    element[e]:led_value(2, 0)
  end
end
"""

# Same model as VSN1's dial (DIAL_ENDLESS): the sum over one revolution is
# REV_UNITS, field 7 is units per revolution, field 8 is the resolution the
# accumulator works in, and spikes substitute the last good reading.
TEK2_DIAL_ENDLESS = """
local r = %s[%s]
local v = self:endless_state() - 64
if v > 3000 or v < -3000 then v = self.av or 0 else self.av = v end
if r then
  local amt = r[7] or 120
  local res = r[8] or 1
  self.ac = (self.ac or 0) + v * amt / (91000 * res)
  local w = self.ac >= 0 and self.ac // 1 or -((-self.ac) // 1)
  self.ac = self.ac - w
  if w ~= 0 then
    package_send(%s, "develop", r[1], w * res, 1)
  end
end
"""


# ------------------------------------------------------------------------- EN16
# Unpaged: both EN16s carry the same HSL grid on all four page slots, so one
# file per module loads four times. 270 degrees, so index = 3 - row + 4*col.
# Columns are Hue / Saturation / Luminance / reserved.
# NOTE: this is a plain string, never passed through Python %-formatting, so the
# Lua modulo is a single %. Doubling it here emits `%%` to the device and the
# parser rejects it as a binary operator with no right-hand expression.
# Columns 0-2 are HSL: e.p is the parameter name. Column 3 is a split-tone
# preset: e.s is its entry from spt, { {r,g,b}, shadow_hue, shadow_sat,
# highlight_hue, highlight_sat }, keyed by band row. A column-3 encoder with
# no preset entry stays dark and inert. e.lv (strength %), e.tr (timer running)
# and e.ph (which saturation the timer sends next) start here.
EN16_HSL = """
function hsl(e)
  local i = e:element_index()
  local b = bofs + 3 - (i % 4)
  local p = prp[i // 4]
  e.p = p and (p .. bnd[b]) or nil
  e.s = (i // 4 == 3) and spt[b] or nil
  e.lv = 100
  e:encoder_mode(0)
  e:encoder_sensitivity(100)
  e:encoder_min(0)
  e:encoder_max(127)
  local c = e.p and brgb[b] or (e.s and e.s[1])
  if c then
    e:led_color(1, {{c[1], c[2], c[3], bla}})
    e:led_value(1, 255)
  else
    e:led_value(1, 0)
  end
end
"""

# ----------------------------------------------------------- column 3 presets
# Press fires the preset; spin scales its strength. Design from 19 Aug.
#
# 2 Oct rebuild: ONE message per preset state — `preset,sh,ss,hh,hs` to the
# fork (0.2.15), which sets all four and echoes the two saturations. The
# old four-send timer chain per element raced the chain of whichever preset
# was active before (different element, or a different EN16 module, which
# share nothing) through index.js's single 50 ms drain: Clear after
# Teal/orange left one saturation standing until a second press [stated].
# "preset" is its own drain group, so it cannot collide with develop sends
# either. Balance is left alone so a balance set by hand survives a preset.
#
#   press   pact = this element. lv = 100. Send.
#   spin    lv += d * SPIN_GAIN, clamped 0..300 (%); the saturations go as
#           preset_sat * lv / 100. Sends coalesce on the element's timer at
#           most every EN16_SEND_MS. A spin on a preset that is not pact
#           fires it first, so "spin before press" still does the right thing.
#
# timer_start is a ONE-SHOT (measured 21 Sep). Also measured: an encoder event
# fires once at load with delta 0, and event 6 fires once at init on every
# element — both are gated or harmless here.
SPIN_GAIN = 4        # percent of the preset per encoder unit; tune by feel

# Diagnostic prints to the Editor's debug monitor (source module [x,y] is
# prefixed automatically). Off for a production build.
EN16_DEBUG = False
def _dbg(line):
    return line if EN16_DEBUG else ''

# HSL knobs (2 Oct, item 9): EN16_STEP per detent, 1 while the knob is held
# (fm); a tap (press, release, no turn) resets the band to 0 — the jog's
# gesture set. Detents accumulate in self.ac and the timer sends the sum
# at most every EN16_SEND_MS, because every develop send on the board shares
# index.js's one 50 ms drain slot and a brisk twist used to lose half its
# detents. pd = a send is pending on the timer; otherwise the timer is the
# ring-dim countdown.
EN16_STEP = 5
EN16_SEND_MS = 60

EN16_TURN = """
local d = self:encoder_state() - 64
if d == 0 then return end
if self.p then
  self.ft = true
  self.ac = (self.ac or 0) + d * (self.fm and 1 or %d)
  local c = brgb[bofs + 3 - (self:element_index() %% 4)]
  self:led_color(1, {{c[1], c[2], c[3], %s}})
  if not self.pd then self.pd = true self:timer_start(%d) end
elseif self.s then
  if pact ~= self:element_index() then pfire(self) end
  local l = self.lv + d * %d
  if l < 0 then l = 0 elseif l > 300 then l = 300 end
  self.lv = l
  if not self.pd then self.pd = true self:timer_start(%d) end
end
""" % (EN16_STEP, RING_ON, EN16_SEND_MS, SPIN_GAIN, EN16_SEND_MS)

EN16_PRESS = """
if self.p then
  if self:button_state() > 0 then
    self.fm = true
    self.ft = false
  else
    self.fm = false
    if not self.ft then package_send(%s, "develop", self.p, 0, 0) end
  end
elseif self.s and self:button_state() > 0 then
  pfire(self)
end
""" % PKG

EN16_TIMER = """
if self.p then
  if self.pd then
    self.pd = false
    if (self.ac or 0) ~= 0 then
      package_send(%s, "develop", self.p, self.ac, 1)
      self.ac = 0
      self.pd = true
      self:timer_start(%d)
    else
      self:timer_start(%d)
    end
  else
    local c = brgb[bofs + 3 - (self:element_index() %% 4)]
    self:led_color(1, {{c[1], c[2], c[3], bla}})
  end
  do return end
end
if self.pd then self.pd = false psend(self) end
""" % (PKG, EN16_SEND_MS, RING_MS)

# psend: the whole preset state in one message. pfire: press. Both live in
# the System element so the four column-3 encoders are identical single-line
# calls, like hsl().
EN16_PFIRE = """
function psend(e)
  local s = e.s
  package_send(%s, "preset", s[2], s[3] * e.lv // 100, s[4], s[5] * e.lv // 100)
end
function pfire(e)
  pact = e:element_index()
  e.lv = 100
  psend(e)
end
""" % PKG


def en16_system(bands, brgb, alpha=0.1, band_offset=0, presets=None):
    """band_offset 0 for EN16-A (Red/Orange/Yellow/Green), 4 for EN16-B.

    presets: {band_row: (label, (r,g,b), sh, ss, hh, hs)} for the four rows
    this module carries. Only the rows on this module are emitted, and the
    label is documentary — EN16 has nowhere to show it.

    alpha: idle brightness. 0.1 was the settled value (readable in full
    afternoon sun; 0.05 confirmed too dim). 28 Sep: CJ wants the board
    dimmer, so lr_pages passes 0.07 — between the two measured points [?].
    A knob goes to RING_ON while turning and drops back on its timer.
    """
    spt = {b: [list(v[1]), v[2], v[3], v[4], v[5]]
           for b, v in (presets or {}).items()}
    mine = range(band_offset, band_offset + 4)   # only this module's rows
    return '\n'.join([
        lua_table('bnd', {b: bands[b] for b in mine}),
        lua_table('brgb', {b: list(brgb[b]) for b in mine}),
        lua_table('spt', spt),
        EN16_HSL,
        EN16_PFIRE,
        INI_LOOP,
    ])


def en16_element0(alpha, band_offset):
    """prp, bla and bofs ride on element 0's Setup (System is at the budget).
    Globals; element 0 runs first, so they exist for every later hsl()."""
    return '\n'.join([
        lua_table('prp', {0: 'HueAdjustment', 1: 'SaturationAdjustment',
                          2: 'LuminanceAdjustment'}),
        'bla = %s' % alpha,
        'bofs = %d' % band_offset,
    ])


def en16_elements():
    """Every one of the sixteen encoders carries the same four events; the
    System table decides what each one does. Event 6 (timer) only ever runs
    on column 3, but a uniform element is one thing to read."""
    return {i: {0: [('cb', 'hsl(self)')],
                2: [('cb', EN16_TURN)],
                3: [('cb', EN16_PRESS)],
                6: [('cb', EN16_TIMER)]} for i in range(16)}


# ------------------------------------------------------------------------- BU16
# Orientation has changed twice, so it is a parameter rather than a baked-in
# formula. It appears in NO config file — it lives in the physical assembly
# only, and nothing in an export will ever remind you.
#
#   BU16_ROT = 0     element = 4*row + col          (native)
#   BU16_ROT = 90    element = 12 + row - 4*col     (dead edge facing outward)
#   BU16_ROT = 180   element = 15 - 4*row - col     (16-28 Sep)
#   BU16_ROT = 270   element = 3 - row + 4*col
#
# History: 90 degrees was a workaround for a dead edge; 180 from 16 Sep to
# 28 Sep (port nearest you); 0 from 28 Sep. Confirm by behaviour, never by
# LED colour: press Reset and see where it lands.
#
# Diagnose orientation by pressing a key with an unmistakable, reversible
# effect and seeing where it lands. LED colour is a poor test — the caps are
# different materials and tint what shows through.
# 28 Sep: back to 0 degrees. At 180 the BU16's Hall-key LEDs sat under caps
# rotated relative to VSN1's and the two halves of the sixteen read as
# different colours [stated]; CJ re-seated the module upright. Everything
# that depends on the mount goes through bu16_element / lr_v2.bu16_slot_lua.
BU16_ROT = 0


def bu16_element(row, col):
    if BU16_ROT == 90:
        return 12 + row - 4 * col
    if BU16_ROT == 180:
        return 15 - 4 * row - col
    if BU16_ROT == 270:
        return 3 - row + 4 * col
    return 4 * row + col


# The plugin's complete non-develop command surface, read from components.js
# rather than guessed. Five families:
#   ("<action>")                     one argument
#   ("view", "<view>")
#   ("<rating|flag|color>", "<val>")
#   ("develop", "<param>", v, mode)
#   ("overlay-control", <n>)
ACTIONS = ['next-photo', 'previous-photo', 'undo', 'redo', 'create-virtual',
           'zoom-toggle', 'zoom-in', 'zoom-out', 'zoom-onetoone', 'copy',
           'paste', 'reset', 'selectall', 'goto-remove', 'goto-mask',
           'goto-crop', 'export', 'import']
VIEWS = ['loupe', 'grid', 'compare', 'survey', 'people', 'develop_loupe',
         'develop_before_after_horiz', 'develop_before_after_vert',
         'develop_before', 'develop_reference_horiz', 'develop_reference_vert']
FLAGS = ['pick', 'reject', 'remove']
COLORS = ['red', 'yellow', 'green', 'blue', 'purple', 'none']


def send(*args):
    """Emit a package_send with the right arity for the family."""
    parts = [PKG] + [lua_value(a) if isinstance(a, str) else str(a) for a in args]
    return 'package_send(%s)' % ', '.join(parts)


def bu16_action(row, col, rgb, body, momentary=None):
    """One fixed-meaning key. momentary: (held_body, released_body) for the
    hold-to-view keys, which the release edge in xv[1] now makes possible."""
    el = bu16_element(row, col)
    held, released = momentary if momentary else (body, '')
    press = """
if self:button_state() > 0 then
  %s
  self:led_color(1, {{%d, %d, %d, 1}})
else
  %s
  self:led_color(1, {{%d, %d, %d, %s}})
end
""" % (held, *rgb, released, *rgb, IDLE)
    return el, {
        0: [('cb', 'self:led_color(1, {{%d, %d, %d, %s}})\nself:led_value(1, 255)'
             % (*rgb, IDLE))],
        3: [('cb', press)],
    }


# Only one package_send per event execution reaches Lightroom — the last call
# wins and earlier ones are discarded silently. Anything needing two or more
# sends therefore has to spread them across ticks.
#
# The queue lives on the element that owns it: self:timer_start(ms) fires that
# element's own event 6, so there are no globals and no cross-element calls.
# The first send goes out immediately on press so the key still feels instant;
# the rest follow at `period` intervals. timer_start is a one-shot (measured
# 21 Sep), so each tick re-arms it while items remain — the two-item Clear key
# worked before that was known only because two items need exactly one tick.
QUEUE_PERIOD = 60


def queued(items, period=QUEUE_PERIOD):
    """items: package_send argument tuples, sent in order. Returns the Setup,
    Button and Timer event bodies for one element."""
    rest = items[1:]
    tbl = ', '.join('[%d] = {%s}' % (i + 1, ', '.join(lua_value(a) for a in t))
                    for i, t in enumerate(rest))
    button = ('if self:button_state() > 0 then\n  %s\n  self.qi = 1\n'
              '  self:timer_start(%d)\nend' % (send(*items[0]), period))
    timer = """
local t = self.q[self.qi]
if t then
  self.qi = self.qi + 1
  if t[3] then
    package_send(%s, t[1], t[2], t[3])
  elseif t[2] then
    package_send(%s, t[1], t[2])
  else
    package_send(%s, t[1])
  end
  if self.q[self.qi] then self:timer_start(%d) end
end
""" % (PKG, PKG, PKG, period)
    return {'setup': 'self.q = { %s }' % tbl, 'button': button, 'timer': timer}


def bu16_system():
    return INI_LOOP


# ------------------------------------------------------------------------- VSN2
# VSN1's layout minus the dial, plus a second screen. Confirmed on hardware:
#   0-7 Hall keys | 8-11 buttons, screen A | 12 LCD A | 13-16 buttons, screen B
#   17 LCD B
# Globals cross both Draw loops in sync, so one label table serves both screens.
VSN2_LCD_A, VSN2_LCD_B = 12, 17
VSN2_BTN_A, VSN2_BTN_B = range(8, 12), range(13, 17)


def vsn2_button(el, rgb, *args, alpha=1):
    return el, {
        0: [('cb', 'self:led_color(1, {{%d, %d, %d, %s}})\nself:led_value(1, 255)'
             % (rgb[0], rgb[1], rgb[2], alpha))],
        3: [('cb', 'if self:button_state() > 0 then\n  %s\nend' % send(*args))],
    }


# ------------------------------------------------------------- system event tail
# page_load(page_number()) on the System element keeps all six modules in step
# natively. Never broadcast page changes — that hung the array badly enough to
# need a factory reset.
SYSTEM_TAIL = {4: [('cb', 'page_load(page_current())')]}


# Screen size. 320x240 is INFERRED, not measured: every Draw clears (0,0)-(320,
# 240) and VSN1's key map draws down to y~200 with the same primitives, so the
# surface is at least that tall.
VSN2_W, VSN2_H = 320, 240

# Under-screen labels track the bottom edge. draw_text_fast has a size FLOOR:
# sizes 9 and 16 both render at ~15 px/char (measured off a photo, 21 Sep —
# "Highlight" at 16 and "Before/A V" at 9 have the same pitch; only 30 is
# visibly larger). So the labels are staggered on two lines — 0 and 2 up, 1
# and 3 down — and each is centred over its own button, with x computed at
# build time from the label length (foot_x). Each LINE holds about 20
# characters across its two labels, not 20 each.
FOOT_RULE, FOOT_Y1, FOOT_Y2 = VSN2_H - 52, VSN2_H - 46, VSN2_H - 24
CHAR_W = 15
# Centres of the four physical buttons under each screen, in screen x.
# Read off a photo (21 Sep): roughly 12%, 35%, 58%, 81% of the width. Each
# label is centred on its button; the stagger keeps neighbours apart.
BTN_CX = (40, 114, 188, 262)


def foot_x(labels):
    """{0..3: label} -> {0..3: x}, each label centred on its button and kept
    at least 4 px inside the screen edge."""
    out = {}
    for i, l in labels.items():
        w = CHAR_W * len(l)
        out[i] = max(4, min(VSN2_W - 4 - w, BTN_CX[i] - w // 2))
    return out


# ============================================================ keyboard_send
# Signature reverse-engineered from the Editor's Macro Input Field, since the
# annotations declare `keyboard_send()` with no parameters at all:
#
#   keyboard_send(delay, [is_modifier, state, code] * n)
#
#   is_modifier  1 modifier, 0 normal key
#   state        0 up, 1 down, 2 down-and-up
#   code         HID modifier bitmask for modifiers, HID usage ID for keys
#
# Codes are HID usage IDs, so keyboard layout is irrelevant at runtime — the
# Editor's "Layout" dropdown only maps characters to codes while authoring.
#
# The GUI does no pairing check: it will build a sequence that presses a key
# and never releases it, or that ends with modifiers still held. That is the
# latched-modifier runaway the console-wide rule exists to avoid, so this
# builder always emits down-and-up for the key and unwinds modifiers in
# reverse order.
DIAL_DIV = 280

MODS = {'ctrl': 1, 'shift': 2, 'alt': 4, 'opt': 4, 'cmd': 8, 'meta': 8, 'gui': 8}

HID = {'tab': 43, 'enter': 40, 'esc': 41, 'space': 44, 'bksp': 42,
       'left': 80, 'right': 79, 'down': 81, 'up': 82,
       'comma': 54, 'period': 55, 'slash': 56,
       'minus': 45, 'equals': 46, 'lbracket': 47, 'rbracket': 48,
       'quote': 52}   # apostrophe; Option+' = Invert Mask [stated 2 Oct]
HID.update({c: 4 + i for i, c in enumerate('abcdefghijklmnopqrstuvwxyz')})
HID.update({str((i + 1) % 10): 30 + i for i in range(10)})
HID.update({'f%d' % n: 57 + n for n in range(1, 13)})


def keystroke(combo, delay=25):
    """'cmd+shift+u' -> a complete, balanced keyboard_send call."""
    parts = [p.strip().lower() for p in combo.split('+')]
    mods, key = parts[:-1], parts[-1]
    if key not in HID:
        raise KeyError('no HID usage ID for %r' % key)
    seq = [delay]
    for m in mods:
        seq += [1, 1, MODS[m]]
    seq += [0, 2, HID[key]]
    for m in reversed(mods):
        seq += [1, 0, MODS[m]]
    return 'keyboard_send(%s)' % ', '.join(str(v) for v in seq)
