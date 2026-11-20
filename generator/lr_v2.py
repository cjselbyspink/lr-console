"""Redesign fragments — LR Console, 27 September 2026.

Everything specific to the agreed layout (claude/LR-Console-Layout.md) lives
here; lr_common keeps the measured mechanisms it builds on (dial model, EN16,
BU16 helpers, queued sends, keystroke, positions). Nothing in here reuses the
old merged-sixteen-with-TEK2 code paths.

THE SIXTEEN
    VSN1 elements 0-7 are physical slots 0-7 (rows 1-2 under the jog).
    BU16 rows 1-2 are slots 8-15; the element follows lr_common.BU16_ROT
    (0 degrees since 28 Sep: slot p = element p - 8).
    Slot 15 is the fixed Reset key; slot 14 is a parameter or null, outside
    the radio when null. Map is on BU16 row 4 col 1 (MAP_RC).

WHO HEARS WHAT
    VSN1 hears BU16 presses on eventrx_cb (measured) and selects.
    VSN1 broadcasts the selected slot on MIDI CC 119; BU16 lights its half
    from midirx_cb (UNMEASURED on BU16 — measured on TEK2 only; bench check 1).
    TEK2's holds and view keys reach VSN1 over MIDI CCs 115-117, because
    TEK2's own position report is unreliable and eventrx_cb from a non-VSN
    module has never been trusted (bench check 2: midirx_cb on VSN1).
    LrImportActive(...) arrives on every module from the plugin fork; VSN1
    and VSN2 use it, the others define a no-op so the broadcast is silent.

BUDGET MAP (VSN1, per page)
    255 Setup   kcol, setc, radio, smm, ini loop
    0   Setup   midirx_cb (holds), LrImportActive receiver
    1   Setup   kpar (global parameter table)
    2   Setup   kmsk (mask twins, page 1 only)
    8   Setup   selb, eventrx_cb, selb(0)
    8   Button  tap = revert, long press = reset
    8   Timer   long-press detector
    8   Endless the turn
    13  Setup   klab, ksho, flags
    13  Draw    the render
"""

import lr_common as C
from lr_common import PKG, lua_table, lua_value, send, INI_LOOP, SETC, SMM, \
    MIDI_CH, MIDI_CC_SLOT, SPIKE, SUB_MAX, SEL_BLACKOUT, REV_UNITS, FINE, BLACKOUT, SEND_EVERY, \
    IDLE, RING_IDLE, RING_ON, RING_MS

# MIDI CCs from TEK2 to VSN1. Value 127 = held, 0 = released. CC 117 (Mask)
# is retired as of 28 Sep: mask mode is mirrored from LrC's tool state via
# the plugin reply (module letter "M"), not held on the board.
CC_ROTATE, CC_BEFORE = 116, 115

# Long-press threshold on the jog: held this long without turning = reset to
# default on release; shorter = revert to the turn's start value.
LONG_MS = 600


def slot_bu16_element(p):
    """Physical slot 8-15 -> BU16 element, for whatever mount lr_common
    says (BU16_ROT). Row 0 of the sixteen's BU16 half is slots 8-11."""
    assert 8 <= p <= 15
    return C.bu16_element((p - 8) // 4, (p - 8) % 4)


def bu16_slot_lua():
    """(lo, hi, expr): the BU16 elements that carry slots 8-15 and the Lua
    expression giving the slot for element `i`. Only 0 and 180 degrees keep
    the rows contiguous under the jog; the other mounts are refused."""
    els = [slot_bu16_element(p) for p in range(8, 16)]
    if C.BU16_ROT == 0:
        return 0, 7, 'i + 8'
    if C.BU16_ROT == 180:
        return 8, 15, '23 - i'
    raise ValueError('BU16 at %d degrees does not stack under VSN1' % C.BU16_ROT)


# A no-op receiver for modules that don't use the plugin's reply. The package
# executes the script on every module; without this, each reply would raise
# "attempt to call a nil value" on four modules — harmless, but noisy on the
# monitor and a wasted error per reply.
LRIA_NOOP = 'LrImportActive = function() end'

# The receiver proper. Fields: id, module (L/D/...), label, param, value,
# rating, flag. Keeps the last echo and a counter so a stale reading is
# visible as stale (lr_n on the screen).
LRIA_RECV = """
lr_n = 0
lr_m = "?"
lr_l = "none"
lr_f = ""
ev_p = ""
ev_v = ""
LrImportActive = function(id, m, l, p, v, r, f)
  lr_n = lr_n + 1
  lr_m = m
  lr_l = l
  lr_f = f
  if p ~= "" then
    ev_p = p
    ev_v = v
  end
  if relab then relab() end
end
"""

# BU16's receiver: the module letter is all it needs — "C" gates the crop
# keys, "M" (on a page with twins) puts rows 1-2 in mask mode. relit lives
# in bu16_midi_rx. kmt is defined in System, which runs before any reply.
LRIA_BU16 = """
tl = "?"
LrImportActive = function(id, m, l, p, v, r, f)
  tl = m
  mk = (m == "M") and next(kmt) ~= nil
  if relit then relit() end
end
"""

# ------------------------------------------------------------------ VSN1 System
# Selected key full, other live keys IDLE, keys that can't act (no twin under
# Mask) off. ring(a) paints the jog ring in the selected slot's colour.
RADIO16 = """
function ring(a)
  local c = kcol[element[8].l_b]
  if c then element[8]:led_color(2, {{c[1], c[2], c[3], a}}) end
end
function radio(p)
  local ok = (not mk) or (kmsk and kmsk[p] ~= nil)
  for i = 0, 7 do
    local c = kcol[i]
    if c then
      element[i]:led_color(1, {{c[1], c[2], c[3], (ok and i == p) and 1 or %s}})
      element[i]:led_value(1, ((not mk) or (kmsk and kmsk[i] ~= nil)) and 255 or 0)
    end
  end
  ring(ok and %s or 0)
end
""" % (IDLE, RING_IDLE)


def vsn1_system(kcol):
    """kcol: {slot: (r,g,b)} for every assigned slot, 0-15. smm lives on
    element 8 now — System was at the budget."""
    return '\n'.join([lua_table('kcol', {k: list(v) for k, v in kcol.items()}),
                      SETC, RADIO16, INI_LOOP])


# ------------------------------------------------------------ VSN1 key 0: ears
# midirx_cb: the two holds from TEK2 (Rotate, Before/After). Gated on
# grid-internal traffic (h[1] ~= 13) and the exact CC. Lives on key 0
# because a callback can only be assigned on `self`, and element 8's Setup
# is full. Mask is not here — see VSN1_RECV.
VSN1_MIDI_RX = """
self.midirx_cb = function(self, h, d)
  if h[1] ~= 13 and d[2] == 176 then
    if d[3] == %d then bm = d[4] > 0 end
  end
end
""" % CC_BEFORE


# VSN1's receiver: the generic one plus slider follow — an echo naming a
# parameter that isn't the selected slot's (a mouse move in LrC, or a page
# the board wasn't on) selects the slot that carries it, in the table in
# force (mask twins while Mask is held). Echoes for the board's own ticks
# always match the selection, so this is a no-op for them.
# Mask mode mirrors LrC (28 Sep): mk is true exactly when the plugin says
# the masking tool is up AND this page has twins (kmsk non-empty) — pages
# without twins ignore masking [stated]. Every reply carries the letter, so
# the board follows LrC whichever way masking was entered or left.
VSN1_RECV = LRIA_RECV + """
lria = LrImportActive
LrImportActive = function(id, m, l, p, v, r, f)
  lria(id, m, l, p, v, r, f)
  local nk = (m == "M") and kmsk ~= nil and next(kmsk) ~= nil
  -- 2 Oct (item 8): Rotate mirrors the crop tool — the jog straightens
  -- whenever LrC is in Crop, no hold needed. CC116 retired.
  rm = (m == "C")
  if nk ~= mk then
    mk = nk
    -- Entering a mask lands on Exposure (slot 2) [stated 28 Sep; never
    -- built until 1 Oct]. Leaving keeps whatever is selected.
    if mk and kmsk[2] and selb then selb(2) elseif radio then radio(element[8].l_b) end
  end
  if p ~= "" and selb then
    local t = mk and kmsk or kpar
    local c = t[element[8].l_b]
    if not c or c[1] ~= p then
      for i = 0, 15 do
        if t[i] and t[i][1] == p then selb(i) end
      end
    end
    if hse then hse(p, v) end
  end
end
"""

# EN16 feedback on the VSN1 LCD (2 Oct, [stated]): an HSL echo
# ("SaturationAdjustmentYellow", 23) takes over the name/value lines for
# ~24 frames in the band's colour — "Yellow Sat 23" — then the selected slot
# returns. hdr() draws those two lines; it lives on key 4's Setup because
# the LCD's Draw is at 907/908 and its Setup is full of tables.
# Presets (EN16 row 3) announce themselves the same way: the preset's name
# on the first line and "shadow sat / highlight sat" from the two echoes on
# the second — the two differ on three of the four presets, so both are
# shown rather than one scaled figure. VSN1 hears the EN16 knob on
# eventrx_cb (vsn1_dispatch) for the name; the values follow by echo.
def vsn1_presets(presets):
    """The sp table rides on key 5's Setup; key 4 (hc, hse, hdr) is at 907."""
    return lua_table('sp', {b: [v[0], list(v[1])] for b, v in presets.items()})


def vsn1_hdr(brgb):
    return 'hc = { %s }' % ', '.join('%s = %s' % (k, lua_value(list(v))) for k, v in brgb.items()) + """
function hse(p, v)
  local a, b = p:match("^(%a-)Adjustment(%a+)$")
  if a then hx = b .. " " .. a:sub(1, 3) hv = v hk = hc[b] ht = 24 hp = false end
  if hp then
    if p == "SplitToningShadowSaturation" then ps = v ht = 24
    elseif p == "SplitToningHighlightSaturation" then ph = v ht = 24 end
    hv = (ps or "-") .. " / " .. (ph or "-")
  end
end
function hdr(d, s, r)
  if (ht or 0) > 0 then
    ht = ht - 1
    d:draw_text_fast(hx, 8, 14, 20, hk or {255, 255, 255})
    d:draw_text_fast(hv, 8, 50, 20, {225, 225, 225})
  else
    d:draw_text_fast(r and (mk and mlab[s] or klab[s]) or "-", 8, 14, 20, kcol[s] or {255, 255, 255})
    d:draw_text_fast(r and ev_p == r[1] and ev_v or "", 8, 50, 20, {225, 225, 225})
  end
end
"""


def vsn1_keys(kpar_lua, kmsk_lua, hdr_lua='', sp_lua=''):
    out = {}
    for i in range(8):
        pre = {0: VSN1_MIDI_RX + VSN1_RECV, 1: kpar_lua, 2: kmsk_lua, 4: hdr_lua, 5: sp_lua}.get(i, '')
        body = [pre] if pre else []
        body.append('if kcol then setc(%d, kcol[%d]) end' % (i, i))
        out[i] = {0: [('cb', '\n'.join(body))]}
    return out


# ------------------------------------------------------------------ VSN1 dial
SELB16 = """
function selb(p)
  if self.l_b ~= p then self.bo = %d end
  self.l_b = p
  if kpar[p] then
    smm()
    element[8]:led_value(2, 255)
  else
    element[8]:led_value(2, 0)
  end
  radio(p)
  midi_send(%d, 176, %d, p)
end
""" % (SEL_BLACKOUT, MIDI_CH, MIDI_CC_SLOT)


def vsn1_dispatch():
    """eventrx_cb: VSN1's own keys select slots 0-7; BU16 rows 1-2 select
    8-15. BU16's Map key (MAP_RC) sets mp on both edges for the LCD. A press on a slot with no parameter (Reset) is ignored here — BU16
    handles Reset itself."""
    mbx, mby = C.LISTENER_BASE[C.VSN1]
    lo, hi, slot = bu16_slot_lua()
    return """
self.eventrx_cb = function(self, h, e, xv, n)
  local m = (h[2] - %d) * 2 + (%d - h[3])
  local i = e[2]
  if m == %d and i == %d then mp = xv[1] > 0 do return end end
  if (m == %d or m == %d) and i // 4 == 3 then
    local t = sp[(m - %d) * 4 + 3 - (i %% 4)]
    if t then hx = t[1] hk = t[2] ht = 24 if not hp then hp = true ps = nil ph = nil hv = "" end end
    do return end
  end
  if xv[1] == 0 then return end
  local p = (m == %d and i < 8) and i or ((m == %d and i >= %d and i <= %d) and (%s) or nil)
  if p and (mk and kmsk or kpar)[p] then selb(p) end
end
""" % (mbx, mby, C.M[C.BU16], map_element(), C.M[C.EN16A], C.M[C.EN16A] + 1, C.M[C.EN16A],
       C.M[C.VSN1], C.M[C.BU16], lo, hi, slot)


# The turn. Mask held swaps the parameter table; Rotate held drives the
# straighten angle. Zoom is no longer here — it is TEK2's left dial.
DIAL_ENDLESS = """
de = (de or 0) + 1
if (self.bo or 0) > 0 then
  self.bo = self.bo - 1
  do return end
end
local v = self:endless_state() - 64
if v > %d or v < -%d then
  ds = (ds or 0) + 1
  self.sr = (self.sr or 0) + 1
  v = self.sr <= %d and (self.av or 0) or 0
else
  self.sr = 0
  self.av = v
end
if fm then ft = true end
local sc = (fm and %s or 1) / %d
local p, amt, res
if rm then
  p, amt, res = "straightenAngle", 20, 0.01
else
  local r = (mk and kmsk or kpar)[self.l_b]
  if r then p, amt, res = r[1], r[2] or 100, (fm and r[4]) or r[3] or 1 end
end
if p then
  if p ~= self.lp then self.ac = 0 self.gt = 0 self.lp = p end
  if not fm then ring(%s) self:timer_start(%s) end
  self.ac = (self.ac or 0) + v * sc * amt
  self.gt = (self.gt or 0) + 1
  if self.gt >= %d then
    self.gt = 0
    local w = self.ac >= 0 and self.ac // res or -((-self.ac) // res)
    self.ac = self.ac - w * res
    if w ~= 0 then
      package_send(%s, "develop", p, w * res, 1)
    end
  end
end
""" % (SPIKE, SPIKE, SUB_MAX, FINE, REV_UNITS, RING_ON, RING_MS, SEND_EVERY, PKG)

# Press: fine mode while held; the timer decides whether a release without a
# turn is a tap (revert) or a long press (reset). Both are plugin commands
# and carry the parameter name, so the board keeps no value state at all.
DIAL_BUTTON = """
self.bo = %d
if self:button_state() > 0 then
  fm = true
  ft = false
  self.lg = false
  self:timer_start(%d)
else
  fm = false
  self:timer_stop()
  ring(%s)
  if not ft then
    if rm then
      package_send(%s, "develop", "straightenAngle", 0, 0)
    else
      local r = (mk and kmsk or kpar)[self.l_b]
      if r then
        package_send(%s, self.lg and "reset-param" or "revert-param", r[1])
      end
    end
  end
end
""" % (BLACKOUT, LONG_MS, RING_IDLE, PKG, PKG)

# The one timer serves two masters: started by a press (LONG_MS) it decides
# long-press; started by a turn (RING_MS, only when not pressed) it dims the
# ring. A turn while pressed sets ft, so the long-press branch can't fire
# from a ring restart.
DIAL_TIMER = """
if fm and not ft then self.lg = true else ring(%s) end
""" % RING_IDLE


def vsn1_dial(start=0):
    return {
        0: [('cb', '\n'.join([SMM, SELB16, vsn1_dispatch(),
                              'if radio then selb(%d) package_send(%s, "state") end' % (start, PKG)]))],
        3: [('cb', DIAL_BUTTON)],
        6: [('cb', DIAL_TIMER)],
        7: [('cb', DIAL_ENDLESS)],
    }


# ------------------------------------------------------------------- VSN1 LCD
# Top: the selected parameter (or the mask twin's name while Mask is held),
# with the hold in force as a small tag. Middle: the last echoed value for the
# selected parameter. Bottom-right corner, near-black: module letter and the
# reply counter, so a stale value is still tellable from a resting one. Bottom: the
# 4x4 map of the sixteen, literally: rows 1-2 VSN1, rows 3-4 BU16 rows 1-2.
# Map held (mp, from BU16 slot 15 on eventrx_cb): the whole block under the
# jog instead, six rows — the sixteen plus BU16 rows 3-4 (ksho 16-23).
#
# 20 Oct: the map's key labels go through @LAB@, so a page that has mask
# twins can show the mask name of a slot under Mask (Vibrance -> "Hue",
# otherwise the map said "Vibr" while the dial drove mask Hue). Pages with no
# twins get the plain ksho[i] and are byte-identical to r1002-1730.
LCD_DRAW_T = """
if not kcol or not lr_m or not ksho or not hdr then self:draw_swap() do return end end
self:draw_area_filled(0, 0, 320, 240, {0, 0, 0})
local s = element[8].l_b
if mp then
  for i = 0, 23 do
    if ksho[i] then
      self:draw_text_fast(@LAB@, 8 + (i % 4) * 78, 10 + (i // 4) * 36, 9, kcol[i] or klc[i] or {99, 99, 99})
    end
  end
  self:draw_swap()
  do return end
end
local r = (mk and kmsk or kpar)[s]
hdr(self, s, r)
local tag = rm and "CROP" or bm and "BEFORE" or mk and "MASK" or fm and "FINE" or ""
if tag ~= "" then self:draw_text_fast(tag, 312 - 15 * #tag, 14, 16, {255, 255, 255}) end
self:draw_text_fast(lr_m .. lr_n, 250, 224, 9, {70, 70, 70})
self:draw_text_fast((ds or 0) .. "s #" .. (de or 0), 8, 80, 9, {90, 90, 90})
for i = 0, 15 do
  -- Under Mask only twin-bearing slots and mask-only keys are drawn
  -- [stated 2 Oct: Vignette/Reset are dark, so the map should agree].
  if ksho[i] and (mk and (kmsk[i] or mlab[i]) or not mk and kcol[i]) then
    local kc = kcol[i] or {120, 230, 180}
    if i ~= s then kc = {kc[1] // 3, kc[2] // 3, kc[3] // 3} end
    self:draw_text_fast(@LAB@, 8 + (i % 4) * 78, 108 + (i // 4) * 30, 9, kc)
  end
end
self:draw_swap()
"""
# A silent replace failure here would ship an unfixed build (it has before),
# so the placeholder count is asserted and the plain draw is built by the
# same replace that is checked.
assert LCD_DRAW_T.count('@LAB@') == 2
LCD_DRAW = LCD_DRAW_T.replace('@LAB@', 'ksho[i]')
LCD_DRAW_MSH = LCD_DRAW_T.replace('@LAB@', 'mk and msh[i] or ksho[i]')
assert '@LAB@' not in LCD_DRAW and '@LAB@' not in LCD_DRAW_MSH


def vsn1_lcd(klab, short, mlab=None, lower_col=None, mshort=None):
    """klab: {slot: full name}. short: {slot: <=4 chars, 0-23}. mlab: mask
    names where they differ from the global (Vibrance slot -> Hue etc.).
    lower_col: {16..23: rgb} for BU16 rows 3-4 in the Map view — kept off
    kcol, which lives on the System element at its budget.
    mshort: {slot: short name} shown in the map (4x4 and the held Map) while
    Mask is up, for slots whose mask twin is a different control (20 Oct).
    Only a page that passes it gets the msh table and the longer Draw."""
    parts = ['lcd_set_backlight(255)', lua_table('klab', klab),
             lua_table('ksho', short), lua_table('mlab', mlab or {})]
    if mshort:
        parts.append(lua_table('msh', mshort))
    parts += [lua_table('klc', {k: list(v) for k, v in (lower_col or {}).items()}),
              'rm = false', 'fm = false', 'bm = false', 'mk = false', 'mp = false']
    return {0: [('cb', '\n'.join(parts))], 8: [('cb', LCD_DRAW_MSH if mshort else LCD_DRAW)]}


# ------------------------------------------------------------------------ BU16
# Rows 1-2: slots 8-15 of the sixteen (paged). Rows 3-4: fixed actions.
def bu16_midi_rx(crop_keys, reset_el):
    """crop_keys: BU16 elements that only work while the crop tool is up
    (tl == "C" from the plugin): off and inert otherwise. reset_el: the
    Reset key, dark under Mask."""
    lo, hi, slot = bu16_slot_lua()
    return """
function relit()
  for i = %d, %d do
    local c = kcol[i]
    if c then
      local on = (not mk) or kmt[i]
      element[i]:led_color(1, {{c[1], c[2], c[3], (on and (%s) == ls) and 1 or %s}})
      element[i]:led_value(1, on and 255 or 0)
    end
  end
  element[%d]:led_value(1, mk and 0 or 255)
  for _, i in ipairs(ck) do element[i]:led_value(1, tl == "C" and 255 or 0) end
  if kmo then for i, c in pairs(kmo) do
    element[i]:led_color(1, {{c[1], c[2], c[3], %s}})
    element[i]:led_value(1, mk and 255 or 0)
  end end
end
self.midirx_cb = function(self, h, d)
  if h[1] ~= 13 and d[2] == 176 then
    if d[3] == %d then ls = d[4] relit() end
  end
end
""" % (lo, hi, slot, IDLE, reset_el, IDLE, MIDI_CC_SLOT) + lua_table('ck', {k + 1: e for k, e in enumerate(crop_keys)})


MAP_RGB = (245, 235, 205)

# BU16's Hall-key LEDs render the same RGB greener than VSN1's (Editor shows
# identical values, board doesn't — [M] 28 Sep, at 0 and 180 degrees, with
# the same caps). Every colour BU16 is given is scaled per channel by this
# before it is emitted, so the two halves of the sixteen match. Judged by
# eye; adjust the constant, not the palettes.
BU16_TINT = (1.0, 0.7, 0.6)


def tint(rgb):
    return tuple(min(255, int(round(c * t))) for c, t in zip(rgb, BU16_TINT))


# The Map hold lives on BU16 row 4 (physical row 6 of the right block),
# column 1 — where the Mask-tool key was until 28 Sep (it duplicated TEK2's
# Mask once mask mode mirrored LrC). (row, col) are physical, resolved
# through bu16_element for the mount. Its element is what VSN1 and VSN2
# listen for on eventrx_cb. Slot 15 is Reset; slot 14 is a parameter or null.
MAP_RC = (3, 0)


def map_element():
    return C.bu16_element(*MAP_RC)


def bu16_page(slot_rgb, fixed_upper, lower, twins=(), crop_only=(), mask_only=None):
    """slot_rgb: {slot 8..15: (r,g,b)} for the paged slots that carry a
    parameter (lit, in the radio). fixed_upper: {slot: (rgb, body)} for
    Reset-like keys in rows 1-2 that are outside the radio. lower:
    {(row, col): (rgb, body)} for rows 3-4. twins: the slots that have a
    mask twin and stay live under Mask. crop_only: (row, col) keys in rows
    3-4 that are dim and inert unless the crop tool is up."""
    ck = [C.bu16_element(r, c) for r, c in crop_only]
    assert len(fixed_upper) == 1, 'exactly one Reset-like key'
    reset_el = slot_bu16_element(next(iter(fixed_upper)))
    rx = bu16_midi_rx(ck, reset_el) + LRIA_BU16
    spec = {i: {0: [('cb', 'self:led_value(1, 0)')]} for i in range(16)}
    kcol = {}
    for p, rgb in slot_rgb.items():
        el = slot_bu16_element(p)
        kcol[el] = list(tint(rgb))
        setup = 'if kcol then setc(%d, kcol[%d]) end' % (el, el)
        spec[el] = {0: [('cb', setup)],
                    # A Button event must exist for the press to broadcast
                    # (not established that a handler-less element does).
                    3: [('cb', 'if self:button_state() > 0 and kcol then setc(%d, kcol[%d]) end' % (el, el))]}
    for p, (rgb, body) in fixed_upper.items():
        el = slot_bu16_element(p)
        _, ev = C.bu16_action(0, 0, tint(rgb), 'if not mk then ' + body + ' end')
        spec[el] = ev
    # mask_only: {slot: (rgb, body)} — a key in the paged block that exists
    # only under Mask (Invert Mask, 2 Oct). Dark and inert otherwise; relit
    # handles the LED through kmo.
    kmo = {}
    for p, (rgb, body) in (mask_only or {}).items():
        el = slot_bu16_element(p)
        kmo[el] = list(tint(rgb))
        _, ev = C.bu16_action(0, 0, tint(rgb), 'if mk then ' + body + ' end')
        spec[el] = ev
    for (row, col), (rgb, body) in lower.items():
        if (row, col) in crop_only:
            body = 'if tl == "C" then ' + body + ' end'
        el, ev = C.bu16_action(row, col, tint(rgb), body)
        spec[el] = ev
    # The Map hold (MAP_RC) on every page: frosted, bright while held, sends
    # nothing — VSN1 and VSN2 hear the edges on eventrx_cb and show the maps.
    # Its Setup also carries the MIDI ear and the receiver.
    assert MAP_RC not in lower, 'the Map key is not in the lower table'
    mel, ev = C.bu16_action(*MAP_RC, tint(MAP_RGB), None, momentary=('', ''))
    ev[0] = [('cb', rx + '\n' + ev[0][0][1])]
    spec[mel] = ev
    kmt = {slot_bu16_element(p): True for p in twins if p in slot_rgb}
    spec[255] = {0: [('cb', '\n'.join([lua_table('kcol', kcol), lua_table('kmt', kmt), lua_table('kmo', kmo),
                                         'mk = false', 'ls = 0', SETC, INI_LOOP, 'relit()']))]}
    spec[255].update(C.SYSTEM_TAIL)
    return spec


# ------------------------------------------------------------------------ TEK2
# 180 degrees: row 3 (far, next to VSN2's keys) is elements 7,6,5,4 for
# columns 1-4; row 4 (near, by the dials) is 3,2,1,0. Element 9 is the
# physically LEFT dial, 8 the RIGHT.
TEK2_ROW3 = (7, 6, 5, 4)
TEK2_ROW4 = (3, 2, 1, 0)
TEK2_LEFT, TEK2_RIGHT = 9, 8


def tek2_hold(cc, rgb, extra_held='', extra_released=''):
    """A frosted hold: bright while held, dim otherwise, CC to VSN1 on both
    edges. extra_* are optional sends on the same edge (Before/After)."""
    body = """
if self:button_state() > 0 then
  midi_send(%d, 176, %d, 127)
  %s
  self:led_color(1, {{%d, %d, %d, 1}})
else
  midi_send(%d, 176, %d, 0)
  %s
  self:led_color(1, {{%d, %d, %d, %s}})
end
""" % (MIDI_CH, cc, extra_held, *rgb, MIDI_CH, cc, extra_released, *rgb, IDLE)
    return {0: [('cb', 'self:led_color(1, {{%d, %d, %d, %s}})\nself:led_value(1, 255)' % (*rgb, IDLE))],
            3: [('cb', body)]}


def tek2_tool_key(rgb, tool, letter):
    """Frosted key that toggles an LrC tool and lights while LrC reports it
    (module letter from the plugin reply). The receiver rides here; it is
    the only thing on TEK2 that reads the reply."""
    # Chained: two tool keys (Mask, Crop since 2 Oct) each add a receiver;
    # a bare assignment would let the later-initialised key silence the other.
    return {0: [('cb', """
local prv = LrImportActive
LrImportActive = function(id, m, l, p, v, r, f)
  if prv then prv(id, m, l, p, v, r, f) end
  self:led_color(1, {{%d, %d, %d, (m == "%s") and 1 or %s}})
end
self:led_color(1, {{%d, %d, %d, %s}})
self:led_value(1, 255)""" % (*rgb, letter, IDLE, *rgb, IDLE))],
            3: [('cb', 'if self:button_state() > 0 then\n  %s\nend' % send('tool-toggle', tool))]}


def tek2_key(rgb, body):
    """One-shot: IDLE, full while pressed."""
    return {0: [('cb', 'self:led_color(1, {{%d, %d, %d, %s}})\nself:led_value(1, 255)' % (*rgb, IDLE))],
            3: [('cb', 'if self:button_state() > 0 then\n  %s\n  self:led_color(1, {{%d, %d, %d, 1}})\nelse\n  self:led_color(1, {{%d, %d, %d, %s}})\nend'
                 % (body, *rgb, *rgb, IDLE))]}


TEK2_DIAL_SETUP = """
self:endless_mode(0)
self:endless_sensitivity(50)
self:endless_min(-100000)
self:endless_max(100000)
self:endless_value(0)
self:led_color(2, {{%d, %d, %d, %s}})
self:led_value(2, 255)
"""

# Zoom: one zoom step per turn event, direction from the sign. The package
# drains one "zoom-in"/"zoom-out" per 50 ms so a fast spin is rate-limited
# there, not here — this is the behaviour the old Zoom hold had, measured.
# 1 Oct: the same BLACKOUT guard as the jog — a press/release shed a few
# spurious ticks and the zoom bounced (session log item 4).
TEK2_ZOOM_TURN = """
if (self.bo or 0) > 0 then
  self.bo = self.bo - 1
  do return end
end
local v = self:endless_state() - 64
if v ~= 0 then package_send(%s, (v > 0) and "zoom-in" or "zoom-out") end
""" % PKG
TEK2_ZOOM_PRESS = 'self.bo = %d\nif self:button_state() > 0 then package_send(%s, "zoom-toggle") end' % (BLACKOUT, PKG)

# Filmstrip: accumulate like a parameter at FILM_PER_REV steps per
# revolution and send ONE next/previous per event when a whole step has
# accrued, dropping any excess so a spin cannot queue a runaway. The plugin
# replies per step, which is the rate measured working at keypress speed.
FILM_PER_REV = 24
TEK2_FILM_TURN = """
local v = self:endless_state() - 64
if v > %d or v < -%d then
  self.sr = (self.sr or 0) + 1
  v = self.sr <= %d and (self.av or 0) or 0
else
  self.sr = 0
  self.av = v
end
self.ac = (self.ac or 0) + v * %d / %d
if self.ac >= 1 then
  self.ac = 0
  package_send(%s, "next-photo")
elseif self.ac <= -1 then
  self.ac = 0
  package_send(%s, "previous-photo")
end
""" % (SPIKE, SPIKE, SUB_MAX, FILM_PER_REV, REV_UNITS, PKG, PKG)


def tek2_dial(el, rgb, turn, press=None):
    """Ring at RING_IDLE; RING_ON while turning, its timer drops it back."""
    lit = 'self:led_color(2, {{%d, %d, %d, %s}})\nself:timer_start(%d)\n' % (*rgb, RING_ON, RING_MS)
    ev = {0: [('cb', TEK2_DIAL_SETUP % (*rgb, RING_IDLE))], 7: [('cb', lit + turn)],
          6: [('cb', 'self:led_color(2, {{%d, %d, %d, %s}})' % (*rgb, RING_IDLE))]}
    if press:
        ev[3] = [('cb', press)]
    return ev


# LrImportActive is cleared before the keys init: the tool keys chain onto
# whatever is there, and a page change must not chain onto the old page's
# closures (whose `self` is now a different key).
def tek2_system():
    return '\n'.join(['LrImportActive = nil', SETC, INI_LOOP])


# ------------------------------------------------------- TEK2 page 2 — Tone
# Colour-grading dial pair (1 Oct 2026, Page2-Proposal). Row 3 is a zone
# radio kept LOCAL to TEK2 (`zn`); both dials read zt[zn][side]. Each dial
# carries its own fine/tap/long state on `self` — the jog's globals fm/ft
# would collide between two dials. Same encoder as the jog (91 000/rev,
# same spike floor [M, Filmstrip]), same arithmetic as DIAL_ENDLESS.
#
# zt[n] = {hue_param, sat_param}; zc[n] = zone colour; zk[n] = row-3 element
# for zone n. za[side] = amount per rev, zr[side] = resolution.
ZONES = {0: ('Global', 'ColorGradeGlobalHue', 'ColorGradeGlobalSat'),
         1: ('Shadows', 'SplitToningShadowHue', 'SplitToningShadowSaturation'),
         2: ('Midtones', 'ColorGradeMidtoneHue', 'ColorGradeMidtoneSat'),
         3: ('Highlights', 'SplitToningHighlightHue', 'SplitToningHighlightSaturation')}
# Row-3 order Global, S, M, H [stated 1 Oct]: col 1's cap is frosted, cols
# 2-4 blue, so S/M/H sit under the matching caps. TEK2_ROW3 = (7, 6, 5, 4).
ZONE_ELEMENT = {n: TEK2_ROW3[n] for n in range(4)}
ZONE_RGB = {0: (225, 225, 225), 1: (70, 90, 230), 2: (150, 190, 255), 3: (255, 200, 120)}
ZONE_BOOT = 2          # Midtones [A — CJ's call after use]
ZONE_AMOUNT = {1: -360, 2: 100}   # hue: negative, matches LrC's wheel [M 1 Oct]
ZONE_RES = {1: 1, 2: 1}

TEK2_ZONE_SYSTEM = """
zn = %d
function zrad()
  for i = 0, 3 do
    local c = zc[i]
    element[zk[i]]:led_color(1, {{c[1], c[2], c[3], (i == zn) and 1 or %s}})
  end
  local c = zc[zn]
  element[%d]:led_color(2, {{c[1], c[2], c[3], %s}})
  element[%d]:led_color(2, {{c[1], c[2], c[3], %s}})
end
""" % (ZONE_BOOT, IDLE, TEK2_LEFT, RING_IDLE, TEK2_RIGHT, RING_IDLE)


def tek2_zone_key(n):
    rgb = ZONE_RGB[n]
    return {0: [('cb', 'self:led_value(1, 255)\nif zrad then zrad() end')],
            3: [('cb', 'if self:button_state() > 0 then\n  zn = %d\n  zrad()\nend' % n)]}


# zring(self, a): this dial's ring in the zone colour at alpha a.
TEK2_PDIAL_SETUP = TEK2_DIAL_SETUP + """
self.side = %d
self.zring = function(s, a)
  local c = zc[zn]
  s:led_color(2, {{c[1], c[2], c[3], a}})
end
"""

TEK2_PDIAL_TURN = """
if (self.bo or 0) > 0 then
  self.bo = self.bo - 1
  do return end
end
local v = self:endless_state() - 64
if v > %d or v < -%d then
  self.sr = (self.sr or 0) + 1
  v = self.sr <= %d and (self.av or 0) or 0
else
  self.sr = 0
  self.av = v
end
if self.fm then self.ft = true end
local sc = (self.fm and %s or 1) / %d
local p, amt, res = zt[zn][self.side], za[self.side], zr[self.side]
if p ~= self.lp then self.ac = 0 self.gt = 0 self.lp = p end
if not self.fm then self:zring(%s) self:timer_start(%s) end
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
""" % (SPIKE, SPIKE, SUB_MAX, FINE, REV_UNITS, RING_ON, RING_MS, SEND_EVERY, PKG)

TEK2_PDIAL_BUTTON = """
self.bo = %d
if self:button_state() > 0 then
  self.fm = true
  self.ft = false
  self.lg = false
  self:timer_start(%d)
else
  self.fm = false
  self:timer_stop()
  self:zring(%s)
  if not self.ft then
    package_send(%s, self.lg and "reset-param" or "revert-param", zt[zn][self.side])
  end
end
""" % (BLACKOUT, LONG_MS, RING_IDLE, PKG)

TEK2_PDIAL_TIMER = """
if self.fm and not self.ft then self.lg = true else self:zring(%s) end
""" % RING_IDLE


def tek2_param_dial(el, side):
    """side 1 = hue (left), 2 = sat (right)."""
    rgb = ZONE_RGB[ZONE_BOOT]
    return {0: [('cb', TEK2_PDIAL_SETUP % (*rgb, RING_IDLE, side))],
            3: [('cb', TEK2_PDIAL_BUTTON)],
            6: [('cb', TEK2_PDIAL_TIMER)],
            7: [('cb', TEK2_PDIAL_TURN)]}


def tek2_tone_system():
    return '\n'.join([
        lua_table('zt', {n: [z[1], z[2]] for n, z in ZONES.items()}),
        lua_table('zc', {n: list(c) for n, c in ZONE_RGB.items()}),
        lua_table('zk', ZONE_ELEMENT),
        lua_table('za', ZONE_AMOUNT), lua_table('zr', ZONE_RES),
        TEK2_ZONE_SYSTEM, 'LrImportActive = nil', SETC, INI_LOOP])


# ------------------------------------------------------------------------ VSN2
# Upright. Row 1 (nearest the screens) is elements 0-3, row 2 is 4-7.
# Screen A (12) sits over columns 1-2, screen B (17) over columns 3-4.
VSN2_LCD_A, VSN2_LCD_B = 12, 17
VSN2_BTN_A, VSN2_BTN_B = (8, 9, 10, 11), (13, 14, 15, 16)


def _flash(rgb, press_body, release_body=''):
    """Button handler: body and full brightness on press, IDLE on release.
    Label keys get repainted by relab() on the plugin's reply anyway."""
    return ('if self:button_state() > 0 then\n  %s\n  self:led_color(1, {{%d, %d, %d, 1}})\n'
            'else\n  %s\n  self:led_color(1, {{%d, %d, %d, %s}})\n  if relab then relab() end\nend'
            % (press_body, *rgb, release_body, *rgb, IDLE))


def vsn2_key(rgb, body, alpha=None):
    """alpha is ignored since 28 Sep: every key idles at IDLE."""
    return {0: [('cb', 'self:led_color(1, {{%d, %d, %d, %s}})\nself:led_value(1, 255)' % (*rgb, IDLE))],
            3: [('cb', _flash(rgb, body))]}


def vsn2_queued_key(rgb, q):
    return {0: [('cb', q['setup'] + '\nself:led_color(1, {{%d, %d, %d, %s}})\nself:led_value(1, 255)' % (*rgb, IDLE))],
            3: [('cb', q['button'] + '\nself:led_color(1, {{%d, %d, %d, %s}})'
                 % (*rgb, 'self:button_state() > 0 and 1 or %s' % IDLE))],
            6: [('cb', q['timer'])]}


# The label keys: full colour when the photo carries that label or flag, dim
# otherwise. lk: element -> label word (or "P"/"R" for the flag keys), lc:
# word -> rgb. Both are set by lr_pages2 in key 0's Setup; the receiver
# calls relab() on every reply.
VSN2_RELAB = """
function relab()
  for i, n in pairs(lk) do
    local c = lc[n]
    local on = (n == lr_l) or (n == lr_f)
    element[i]:led_color(1, {{c[1], c[2], c[3], on and 1 or %s}})
  end
end
"""
LABEL_DIM = IDLE


def vsn2_dispatch():
    """The Map hold from BU16's Map key. (The EN16 band flash that lived
    here moved to the VSN1 LCD on 2 Oct — see vsn1_hdr.)"""
    mbx, mby = C.LISTENER_BASE[C.VSN2]
    a = C.M[C.EN16A]
    return """
self.eventrx_cb = function(self, h, e, xv, n)
  local m = (h[2] - %d) * 2 + (%d - h[3])
  local i = e[2]
  if m == %d and i == %d then
    mp = xv[1] > 0
  end
end
""" % (mbx, mby, C.M[C.BU16], map_element())


# Knob graphic, redrawn from the pre-redesign VSN2 (measured on hardware):
# a rounded-rect body with a ring of dots, static — no readback, so never a
# pointer. Lives in the System element so both Draws call it from there.
KNOB_R, KNOB_RING, KNOB_DOT, KNOB_DOTS = 34, 44, 3, 12
KNOB_CY = 100


def _ring_offsets():
    import math
    return {k: [round(KNOB_RING * math.sin(2 * math.pi * k / KNOB_DOTS)),
                -round(KNOB_RING * math.cos(2 * math.pi * k / KNOB_DOTS))]
            for k in range(KNOB_DOTS)}


VSN2_KNOB = """
function knob(s, x, nm, c)
  local h = {c[1] // 2, c[2] // 2, c[3] // 2}
  s:draw_rectangle_rounded_filled(x - %d, %d, x + %d, %d, %d, c)
  for j = 0, %d do
    local o = rd[j]
    s:draw_rectangle_rounded_filled(x + o[1] - %d, %d + o[2], x + o[1] + %d, %d + o[2], %d, h)
  end
  s:draw_text_fast(nm, x - 8 * #nm, %d, 16, {225, 225, 225})
end
function foot(s)
  s:draw_area_filled(0, %d, %d, %d, {70, 70, 70})
  for i = 0, 3 do
    if s.bl[i] then
      s:draw_text_fast(s.bl[i], s.bx[i], (i %% 2 == 0) and %d or %d, 9, {150, 170, 150})
    end
  end
  s:draw_swap()
end
function kmap(s, t, c)
  for i = 0, 7 do
    if t[i] then
      s:draw_text_fast(t[i], 6 + (i %% 2) * 92, 12 + (i // 2) * 42, 9, c[i] or {200, 200, 200})
    end
  end
end
""" % (KNOB_R, KNOB_CY - KNOB_R, KNOB_R, KNOB_CY + KNOB_R, KNOB_R,
       KNOB_DOTS - 1,
       KNOB_DOT, KNOB_CY - KNOB_DOT, KNOB_DOT, KNOB_CY + KNOB_DOT, KNOB_DOT,
       KNOB_CY + KNOB_RING + 10,
       C.FOOT_RULE, C.VSN2_W, C.FOOT_RULE + 1, C.FOOT_Y1, C.FOOT_Y2)


def vsn2_system():
    return '\n'.join([lua_table('rd', _ring_offsets()), VSN2_KNOB, INI_LOOP])


# Screen A: the page banner and the Zoom knob. Screen B: the LrC mode
# (near-black), the EN16 flash and the Filmstrip knob. Map held (mp):
# each screen shows the two columns of the left block beneath it — VSN2 rows
# 1-2 and TEK2 rows 3-4 — with the TEK2 dial under those columns. The block
# under the jog is VSN1's LCD's business.
VSN2_DRAW_A = """
if not lr_m or not knob or not bnr or not self.mk then self:draw_swap() do return end end
self:draw_area_filled(0, 0, 320, 240, {0, 0, 0})
if mp then
  kmap(self, self.mk, self.mc)
else
  self:draw_text_fast(bnr, 12, 14, 20, {255, 255, 255})
end
knob(self, mp and 250 or 160, "Zoom", {200, 200, 200})
foot(self)
"""

# Screen B: the EN16 band flash, the LrC mode near-black, the Filmstrip knob.
# The echoed value is VSN1's business; it was duplicated here and removed.
VSN2_DRAW_B = """
if not lr_m or not knob or not self.mk then self:draw_swap() do return end end
self:draw_area_filled(0, 0, 320, 240, {0, 0, 0})
if mp then
  kmap(self, self.mk, self.mc)
else
  self:draw_text_fast(md[lr_m] or lr_m, 12, 14, 9, {60, 60, 60})
end
knob(self, mp and 250 or 160, "Filmstrip", {90, 160, 255})
foot(self)
"""


# Page 2 (Tone): the knobs are TEK2's Hue and Sat dials. Zone and value come
# from the plugin echo — zp[param] = {zone, side} — so VSN2 needs nothing
# from TEK2. The zone shows from the first turn, not the key press [stated].
# hz/hv, sz/sv: last echoed zone and value per side. Counter beside the value
# so a stale reading is tellable.
VSN2_ZP = {z[1]: [z[0], 1] for z in ZONES.values()}
VSN2_ZP.update({z[2]: [z[0], 2] for z in ZONES.values()})

VSN2_TONE_PICK = """
local z = zp and zp[ev_p]
if z then
  if z[2] == 1 then hz = z[1] hv = ev_v else sz = z[1] sv = ev_v end
end
"""

VSN2_DRAW_A_TONE = """
if not lr_m or not knob or not bnr or not self.mk then self:draw_swap() do return end end
self:draw_area_filled(0, 0, 320, 240, {0, 0, 0})
%s
if mp then
  kmap(self, self.mk, self.mc)
else
  self:draw_text_fast(bnr, 12, 14, 20, {255, 255, 255})
  self:draw_text_fast((hz or "") .. " " .. (hv or ""), 12, 40, 14, {225, 225, 225})
  self:draw_text_fast(lr_m .. lr_n, 250, 40, 9, {70, 70, 70})
end
knob(self, mp and 250 or 160, "Hue", {200, 200, 200})
foot(self)
""" % VSN2_TONE_PICK

VSN2_DRAW_B_TONE = """
if not lr_m or not knob or not self.mk then self:draw_swap() do return end end
self:draw_area_filled(0, 0, 320, 240, {0, 0, 0})
%s
if mp then
  kmap(self, self.mk, self.mc)
else
  self:draw_text_fast(md[lr_m] or lr_m, 12, 14, 9, {60, 60, 60})
  self:draw_text_fast((sz or "") .. " " .. (sv or ""), 12, 40, 14, {225, 225, 225})
end
knob(self, mp and 250 or 160, "Sat", {150, 190, 255})
foot(self)
""" % VSN2_TONE_PICK


def vsn2_screen(el, draw, mapkeys, mapcol, foot, extra_setup=''):
    setup = '\n'.join(filter(None, [
        'lcd_set_backlight(255)', extra_setup,
        lua_table('self.mk', mapkeys), lua_table('self.mc', {k: list(v) for k, v in mapcol.items()}),
        lua_table('self.bl', foot), lua_table('self.bx', C.foot_x(foot)),
    ]))
    return {0: [('cb', setup)], 8: [('cb', draw)]}
