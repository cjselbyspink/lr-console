"""Two-module starter: one EN16 + one VSN1 (18 Nov 2026).

STATUS: generated and stub-tested in a Lua interpreter. NOT tested on
hardware -- the author's board is the six-module one. Treat every behaviour
below as [S] (from source) until you have seen it on your own modules.

Build:  python3 build_all.py out <stamp> flipped lr_starter

What it reuses unchanged from the six-module build: the jog's dial model and
gestures (lr_v2.DIAL_*), the plugin-reply receiver with mask mirroring, crop
straightening and slider follow (lr_v2.VSN1_RECV), the LCD (lr_v2.vsn1_lcd),
and the EN16 Colour Mixer page (lr_pages.en16). It needs the plugin fork.

What is different:
  * The selector is VSN1's own eight keys only, so each page carries eight
    sliders, not sixteen.
  * No module positions anywhere. VSN1 tells its own key presses (source
    offset 127,127) from anything else, and treats anything else as the EN16.
    The two modules can sit either way round.
  * The EN16 can be mounted upright (EN16_ROT = 0, the default here) or a
    quarter-turn anticlockwise as on the six-module board (EN16_ROT = 270).
  * No MIDI between modules (the six-module build uses it to reach BU16).
"""

import lr_common as C
import lr_v2 as V
from lr_common import PKG, lua_table
from lr_pages import (TEMPLATES, BANDS, BAND_RGB, SPLIT_PRESETS, TONE, COOL,
                      FINE, MASK, NAV, CREAM, CULL_R, CULL_G, en16)
from lr_pages2 import params, HOLD

# 0 = EN16 upright (element 0 at the physical top-left, rows of four running
# left to right) [S: the BU16's native map, assumed the same for EN16].
# 270 = as on the six-module board (measured there).
EN16_ROT = 0


def _sub(text, old, new, count=1):
    """Replace with a count check: a silent miss must fail the build."""
    assert text.count(old) == count, (old, text.count(old))
    return text.replace(old, new)


# --------------------------------------------------------------------- EN16
def starter_en16():
    """Red / Orange / Yellow / Green rows, columns Hue / Sat / Lum / preset."""
    _, spec = en16('EN16-A')
    if EN16_ROT == 0:
        # Upright: element i sits at row i // 4, column i % 4.
        sysl = spec[255][0][0][1]
        sysl = _sub(sysl, 'local b = bofs + 3 - (i % 4)', 'local b = bofs + i // 4')
        sysl = _sub(sysl, 'local p = prp[i // 4]', 'local p = prp[i % 4]')
        sysl = _sub(sysl, 'e.s = (i // 4 == 3) and spt[b] or nil',
                    'e.s = (i % 4 == 3) and spt[b] or nil')
        spec[255][0] = [('cb', sysl)]
        band = 'brgb[bofs + 3 - (self:element_index() % 4)]'
        for i in range(16):
            spec[i][2] = [('cb', _sub(spec[i][2][0][1], band,
                                      'brgb[bofs + self:element_index() // 4]'))]
            spec[i][6] = [('cb', _sub(spec[i][6][0][1], band,
                                      'brgb[bofs + self:element_index() // 4]'))]
    else:
        assert EN16_ROT == 270, 'EN16_ROT must be 0 or 270'
    return 'EN16-A', spec


# --------------------------------------------------------------------- VSN1
# selb without the MIDI broadcast (there is no second half of the selector).
SELB8 = _sub(V.SELB16, '  midi_send(%d, 176, %d, p)\n' % (C.MIDI_CH, C.MIDI_CC_SLOT), '')

# Own key presses arrive with source offset 127,127. Anything else is the
# EN16: a preset-column knob puts the preset's name on the LCD.
DISPATCH8 = """
self.eventrx_cb = function(self, h, e, xv, n)
  local i = e[2]
  if h[2] ~= 127 or h[3] ~= 127 then
    if @COND@ then
      local t = sp[@IDX@]
      if t then hx = t[1] hk = t[2] ht = 24 if not hp then hp = true ps = nil ph = nil hv = "" end end
    end
    do return end
  end
  if xv[1] == 0 then return end
  if i < 8 and (mk and kmsk or kpar)[i] then selb(i) end
end
"""


def dispatch8():
    cond, idx = (('i % 4 == 3', 'i // 4') if EN16_ROT == 0
                 else ('i // 4 == 3', '3 - (i % 4)'))
    return _sub(_sub(DISPATCH8, '@COND@', cond), '@IDX@', idx)


def vsn1(labels, short, colours, parameters, mask=None, mask_labels=None,
         start=0, mask_short=None, actions=None):
    """labels/short/colours: {slot 0-7: ...}. parameters / mask: kpar / kmsk
    tables from lr_pages2.params. actions: {slot: (rgb, lua_body)} for keys
    that act instead of selecting a slider."""
    pre = {0: V.VSN1_RECV,
           1: lua_table('kpar', parameters),
           2: lua_table('kmsk', mask or {}),
           4: V.vsn1_hdr({BANDS[b]: BAND_RGB[b] for b in BANDS}),
           5: V.vsn1_presets({b: v for b, v in SPLIT_PRESETS.items() if b < 4})}
    spec = {}
    for i in range(8):
        body = [pre[i]] if i in pre else []
        body.append('if kcol then setc(%d, kcol[%d]) end' % (i, i))
        spec[i] = {0: [('cb', '\n'.join(body))]}
    for i, (rgb, lua) in (actions or {}).items():
        key = V.tek2_key(rgb, lua)
        spec[i][0] = [('cb', spec[i][0][0][1] + '\n' + key[0][0][1])]
        spec[i][3] = key[3]
    spec[8] = {
        0: [('cb', '\n'.join([C.SMM, SELB8, dispatch8(),
                              'if radio then selb(%d) package_send(%s, "state") end' % (start, PKG)]))],
        3: [('cb', V.DIAL_BUTTON)],
        6: [('cb', V.DIAL_TIMER)],
        7: [('cb', V.DIAL_ENDLESS)],
    }
    spec.update(C.vsn1_page_buttons())
    spec[13] = V.vsn1_lcd(labels, short, mask_labels, {}, mask_short)
    spec[255] = {0: [('cb', V.vsn1_system(colours))]}
    spec[255].update(C.SYSTEM_TAIL)
    return 'VSN1L', spec


def slots(names, rgb):
    labs = {i: n for i, n in enumerate(names) if n}
    return labs, {i: rgb for i in labs}


# ------------------------------------------------------------- Page 1: Basic
P1_KEYS = ['Temperature', 'Tint', 'Exposure', 'Contrast',
           'Highlights', 'Shadows', 'Whites', 'Blacks']
P1_SHORT = {0: 'Temp', 1: 'Tint', 2: 'Expo', 3: 'Cont',
            4: 'High', 5: 'Shad', 6: 'Whit', 7: 'Blac'}
P1_MASK = ['local_' + n for n in P1_KEYS]


def page1():
    labs, cols = slots(P1_KEYS, TONE)
    return vsn1(labs, P1_SHORT, cols,
                params(P1_KEYS, {0: 4000, 1: 100, 2: 2}, {2: 0.05}, {2: 0.01}),
                params(P1_MASK, {2: 2}, {2: 0.05}, {2: 0.01}), start=2)


# ---------------------------------------------------------- Page 2: Presence
P2_KEYS = ['Texture', 'Clarity', 'Dehaze', 'Vibrance',
           'Saturation', 'Vignette', 'Sharpening', 'Noise Reduction']
P2_SHORT = {0: 'Text', 1: 'Clar', 2: 'Deha', 3: 'Vibr',
            4: 'Satu', 5: 'Vign', 6: 'Shrp', 7: 'L-NR'}
P2_PARAMS = ['Texture', 'Clarity', 'Dehaze', 'Vibrance', 'Saturation',
             'PostCropVignetteAmount', 'Sharpness', 'LuminanceSmoothing']
# Masks have no Vibrance, so that key drives mask Hue, as on the big board.
P2_MASK = ['local_Texture', 'local_Clarity', 'local_Dehaze', 'local_Hue',
           'local_Saturation', None, None, None]


def page2():
    labs, cols = slots(P2_KEYS, TONE)
    for i in (6, 7):
        cols[i] = FINE
    return vsn1(labs, P2_SHORT, cols, params(P2_PARAMS), params(P2_MASK),
                {3: 'Mask Hue'}, mask_short={3: 'Hue'})


# -------------------------------------------------------------- Page 3: Tone
P3_KEYS = ['Curve Highlights', 'Curve Lights', 'Curve Darks', 'Curve Shadows',
           'Shadow Lum', 'Midtone Lum', 'Highlight Lum', 'Balance']
P3_SHORT = {0: 'C-Hi', 1: 'C-Li', 2: 'C-Dk', 3: 'C-Sh',
            4: 'S-Lu', 5: 'M-Lu', 6: 'H-Lu', 7: 'Bal'}
P3_PARAMS = ['ParametricHighlights', 'ParametricLights', 'ParametricDarks',
             'ParametricShadows', 'ColorGradeShadowLum', 'ColorGradeMidtoneLum',
             'ColorGradeHighlightLum', 'SplitToningBalance']


def page3():
    labs, cols = slots(P3_KEYS, COOL)
    for i in range(4):
        cols[i] = TONE
    return vsn1(labs, P3_SHORT, cols,
                params(P3_PARAMS, {0: 100, 1: 100, 2: 100, 3: 100}), start=1)


# ----------------------------------------------------------- Page 4: Actions
# Keys that act instead of selecting. Nothing is selected on this page
# (start=8, a slot that does not exist), so the jog only works in Crop,
# where it straightens.
P4_SHORT = {0: 'Prev', 1: 'Next', 2: 'Rejt', 3: 'Pick',
            4: 'Undo', 5: 'Redo', 6: 'Crop', 7: 'Mask'}
P4_ACTIONS = {
    0: (NAV, C.send('previous-photo')),
    1: (NAV, C.send('next-photo')),
    2: (CULL_R, C.send('flag', 'reject')),
    3: (CULL_G, C.send('flag', 'pick')),
    4: (CREAM, C.send('undo')),
    5: (CREAM, C.send('redo')),
    6: (HOLD, C.send('tool-toggle', 'crop')),
    7: (MASK, C.send('tool-toggle', 'masking')),
}


def page4():
    labs = {i: n for i, n in P4_SHORT.items()}
    cols = {i: rgb for i, (rgb, _) in P4_ACTIONS.items()}
    return vsn1(labs, P4_SHORT, cols, {}, start=8, actions=P4_ACTIONS)


PAGES = {
    'Starter EN16 HSL':    starter_en16,
    'Starter Page 1 VSN1': page1,
    'Starter Page 2 VSN1': page2,
    'Starter Page 3 VSN1': page3,
    'Starter Page 4 VSN1': page4,
}
