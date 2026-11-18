"""Page definitions for the redesign (claude/LR-Console-Layout.md), 27 Sep 2026.

Six modules. EN16 pair unchanged from lr_pages. TEK2 fixed on every page.
VSN2 differs per page only by its banner (the maps are fixed). VSN1 and BU16 rows 1-2 are paged.
"""

import os
import lr_common as C
import lr_v2 as V
from lr_pages import (EXPORTS, TEMPLATES, BANDS, BAND_RGB, SPLIT_PRESETS,
                      TONE, COOL, MASK, FINE, CREAM, WARN, STAR, NAV, CULL_R,
                      CULL_G, en16)

# ------------------------------------------------------------------- palettes
LABEL_RGB = {'red': (255, 0, 25), 'yellow': (255, 220, 0), 'green': (0, 255, 40),
             'blue': (0, 90, 255), 'purple': (140, 0, 255), 'none': (120, 120, 120)}
HOLD = (180, 220, 255)
VIEW = (200, 200, 210)
VIEW_KEY = (120, 170, 255)   # light-blue cap on BU16 (tinted there)
VIEW_TEK = (190, 210, 250)   # TEK2 view keys; (160,185,232) read a hair dark [stated 2 Oct]
UNDO = (170, 190, 210)

DEFAULT_AMOUNT = 120
# 20 Oct [stated]: coarse moves in whole 5s so a spin lands on neat values
# instead of 33 etc.; fine stays at 1. Exposure, Radius and Temperature set
# their own. Relative steps: they are 5s from wherever the value already is.
DEFAULT_RES = 5
DEFAULT_FINE_RES = 1


def str_table(name, entries):
    """String-keyed sibling of lua_common.lua_table: one table literal."""
    return '%s = { %s }' % (name, ', '.join('%s = %s' % (k, C.lua_value(v))
                                             for k, v in entries.items()))


def params(names, amount=None, res=None, fine=None):
    amount, res, fine = amount or {}, res or {}, fine or {}
    return {i: [p, amount.get(i, DEFAULT_AMOUNT), res.get(i, DEFAULT_RES),
                fine.get(i, res.get(i, DEFAULT_FINE_RES))]
            for i, p in enumerate(names) if p}


# ============================================================ TEK2 — fixed
def tek2():
    r3, r4 = V.TEK2_ROW3, V.TEK2_ROW4
    spec = {}
    # 2 Oct (item 8b): Crop toggle, lit while LrC is in Crop; the jog
    # straightens whenever it is (rm mirrors the letter). Was the Rotate hold.
    spec[r3[0]] = V.tek2_tool_key(HOLD, 'crop', 'C')
    spec[r3[1]] = V.tek2_key(VIEW_TEK, C.send('view', 'library'))      # fork drop (c)
    spec[r3[2]] = V.tek2_key(VIEW_TEK, C.send('view', 'develop_loupe'))  # LrC module order
    spec[r3[3]] = V.tek2_key(VIEW_TEK, C.send('view', 'survey'))
    # Mask: a toggle that mirrors LrC (28 Sep). Press = tool-toggle; the LED
    # and the sixteen's mask mode both follow the plugin's module letter.
    spec[r4[0]] = V.tek2_tool_key(MASK, 'masking', 'M')
    spec[r4[1]] = V.tek2_hold(V.CC_BEFORE, HOLD,
                              C.send('view', 'develop_before'),
                              C.send('view', 'develop_loupe'))
    # 1 Oct: Copy/Paste and Undo/Redo swapped modules [stated 30 Sep] — Undo/
    # Redo now on BU16 row 5 (BU16_LOWER), Copy/Paste here.
    # Caps not swapped [stated 1 Oct]: TEK2's dark caps carry Copy/Paste, the
    # cream caps on BU16 row 5 carry Undo/Redo, so the palettes follow the caps.
    spec[r4[2]] = V.tek2_key(UNDO, C.send('copy'))
    spec[r4[3]] = V.tek2_key(UNDO, C.send('paste'))
    # The receiver is on the Mask key (tek2_tool_key); nothing else needs one.
    spec[V.TEK2_LEFT] = V.tek2_dial(V.TEK2_LEFT, (225, 225, 225), V.TEK2_ZOOM_TURN, V.TEK2_ZOOM_PRESS)
    spec[V.TEK2_RIGHT] = V.tek2_dial(V.TEK2_RIGHT, (90, 160, 255), V.TEK2_FILM_TURN)
    spec[255] = {0: [('cb', V.tek2_system())]}
    spec[255].update(C.SYSTEM_TAIL)
    return 'TEK2', spec


def tek2_tone():
    """Page 2 only: row 3 = grading zone radio, dials = Hue / Sat of the
    zone. Row 4 as the fixed page (Page2-Proposal, 1 Oct)."""
    r3, r4 = V.TEK2_ROW3, V.TEK2_ROW4
    spec = {}
    for n in range(4):
        spec[V.ZONE_ELEMENT[n]] = V.tek2_zone_key(n)
    spec[r4[0]] = V.tek2_tool_key(MASK, 'masking', 'M')
    spec[r4[1]] = V.tek2_hold(V.CC_BEFORE, HOLD,
                              C.send('view', 'develop_before'),
                              C.send('view', 'develop_loupe'))
    spec[r4[2]] = V.tek2_key(UNDO, C.send('copy'))
    spec[r4[3]] = V.tek2_key(UNDO, C.send('paste'))
    spec[V.TEK2_LEFT] = V.tek2_param_dial(V.TEK2_LEFT, 1)
    spec[V.TEK2_RIGHT] = V.tek2_param_dial(V.TEK2_RIGHT, 2)
    spec[255] = {0: [('cb', V.tek2_tone_system())]}
    spec[255].update(C.SYSTEM_TAIL)
    return 'TEK2', spec


# ============================================================ VSN2 — per page
VSN2_KEYS = {
    0: (CULL_R, C.send('flag', 'reject')),
    1: (CULL_G, C.send('flag', 'pick')),
    2: (LABEL_RGB['green'], C.send('color-toggle', 'green')),
    3: (LABEL_RGB['purple'], C.send('color-toggle', 'purple')),
    4: (LABEL_RGB['red'], C.send('color-toggle', 'red')),
    5: (LABEL_RGB['yellow'], C.send('color-toggle', 'yellow')),
    6: (LABEL_RGB['blue'], C.send('color-toggle', 'blue')),
}
# Clear: rating 0 and flag remove, through the timer queue.
VSN2_CLEAR = 7

MINI_A = [((235, 205, 120), C.send('rating', '1'), 0.25),
          ((235, 205, 120), C.send('rating', '2'), 0.55),
          ((235, 205, 120), C.send('rating', '3'), 1),
          ((170, 170, 190), C.keystroke('cmd+shift+u'), 1)]        # Auto WB
MINI_B = [((170, 190, 170), C.send('view', 'develop_reference_horiz'), 1),
          ((170, 190, 170), C.send('view', 'compare'), 1),
          ((170, 170, 190), C.keystroke('cmd+u'), 1),               # Auto Tone
          ((170, 190, 170), C.keystroke('j'), 1)]                   # Clipping
FOOT_A = {0: '*1', 1: '*2', 2: '*3', 3: 'Auto WB'}
FOOT_B = {0: 'Ref', 1: 'Compare', 2: 'Auto Tone', 3: 'Clip'}

# Maps shown while Map is held: the left block (VSN2 rows 1-2, TEK2 rows
# 3-4) split by screen, each showing the two columns beneath it, row-major.
# The block under the jog goes on VSN1's LCD (MAP_BU16_LOWER, rows 5-6).
MAP_LEFT = {0: 'Rejt', 1: 'Pick', 2: 'Grn', 3: 'Purp',
            4: 'Red', 5: 'Yell', 6: 'Blue', 7: 'Clr',
            8: 'Crop', 9: 'Libr', 10: 'Devl', 11: 'Surv',
            12: 'Mask', 13: 'Bef/A', 14: 'Copy', 15: 'Past'}
MAP_LEFT_C = {0: CULL_R, 1: CULL_G, 2: LABEL_RGB['green'], 3: LABEL_RGB['purple'],
              4: LABEL_RGB['red'], 5: LABEL_RGB['yellow'], 6: LABEL_RGB['blue'], 7: WARN,
              8: HOLD, 9: VIEW_TEK, 10: VIEW_TEK, 11: VIEW_TEK,
              12: MASK, 13: HOLD, 14: UNDO, 15: UNDO}


# Page 2: TEK2 row 3 is the grading zone radio (tek2_tone), so the map says so.
MAP_LEFT_TONE = {**MAP_LEFT, 8: 'Glob', 9: 'Shad', 10: 'Mid', 11: 'High'}
MAP_LEFT_TONE_C = {**MAP_LEFT_C, **{8 + n: V.ZONE_RGB[n] for n in range(4)}}


def map_half(cols, labels=MAP_LEFT, colours=MAP_LEFT_C):
    """Columns (0,1) or (2,3) of the left-block map as an 8-entry row-major table."""
    keys = [r * 4 + c for r in range(4) for c in cols]
    return ({k: labels[i] for k, i in enumerate(keys)},
            {k: colours[i] for k, i in enumerate(keys)})


MAP_BU16_LOWER = {16: 'Undo', 17: 'Redo', 18: 'Prev', 19: 'Next',
                  20: 'MAP', 21: 'LrC', 22: 'CrpX', 23: 'Ovly'}
MAP_BU16_LOWER_C = {16: CREAM, 17: CREAM, 18: NAV, 19: NAV,
                    20: V.MAP_RGB, 21: VIEW_KEY, 22: FINE, 23: FINE}


def vsn2(banner, tone=False):
    spec = {}
    for i, (rgb, body) in VSN2_KEYS.items():
        spec[i] = V.vsn2_key(rgb, body)
    spec[VSN2_CLEAR] = V.vsn2_queued_key(WARN, C.queued([('rating', '0'), ('flag', 'remove')]))
    # Key 0 carries the EN16 flash listener and the plugin receiver.
    spec[0][0] = [('cb', V.vsn2_dispatch() + V.LRIA_RECV + '\n' + spec[0][0][0][1])]
    for k, (rgb, body, alpha) in enumerate(MINI_A):
        spec[V.VSN2_BTN_A[k]] = V.vsn2_key(rgb, body, alpha)
    for k, (rgb, body, alpha) in enumerate(MINI_B):
        spec[V.VSN2_BTN_B[k]] = V.vsn2_key(rgb, body, alpha)
    # Label/flag key tables and relab() ride on key 0 too.
    lc = dict(LABEL_RGB, P=CULL_G, R=CULL_R)
    lc.pop('none')
    lk = {0: 'R', 1: 'P', 2: 'green', 3: 'purple', 4: 'red', 5: 'yellow', 6: 'blue'}
    spec[0][0] = [('cb', '\n'.join([str_table('lc', {k: list(v) for k, v in lc.items()}),
                                     C.lua_table('lk', lk), V.VSN2_RELAB % V.LABEL_DIM,
                                     spec[0][0][0][1]]))]
    a_setup = 'bnr = "%s"' % banner
    # The EN16 band tables are globals; they ride on key 1's Setup because
    # screen B's own Setup is at the budget with the map in it.
    # (EN16 band tables left here 2 Oct — the flash moved to VSN1's LCD.)
    if tone:
        spec[1][0] = [('cb', str_table('zp', V.VSN2_ZP) + '\n' + spec[1][0][0][1])]
    b_setup = str_table('md', {'L': 'Library', 'D': 'Develop', 'C': 'Crop', 'M': 'Mask'})
    ml, mc = (MAP_LEFT_TONE, MAP_LEFT_TONE_C) if tone else (MAP_LEFT, MAP_LEFT_C)
    amap, acol = map_half((0, 1), ml, mc)
    bmap, bcol = map_half((2, 3), ml, mc)
    da, db = (V.VSN2_DRAW_A_TONE, V.VSN2_DRAW_B_TONE) if tone else (V.VSN2_DRAW_A, V.VSN2_DRAW_B)
    spec[V.VSN2_LCD_A] = V.vsn2_screen(V.VSN2_LCD_A, da, amap, acol, FOOT_A, a_setup)
    spec[V.VSN2_LCD_B] = V.vsn2_screen(V.VSN2_LCD_B, db, bmap, bcol, FOOT_B, b_setup)
    spec[255] = {0: [('cb', V.vsn2_system())]}
    spec[255].update(C.SYSTEM_TAIL)
    return 'VSN2', spec


# ============================================================ BU16 rows 3-4
BU16_LOWER = {
    (2, 0): (CREAM, C.send('undo')),    # 1 Oct: swapped with TEK2's Copy/Paste; cream caps stay
    (2, 1): (CREAM, C.send('redo')),
    (2, 2): (NAV, C.send('previous-photo')),
    (2, 3): (NAV, C.send('next-photo')),
    # (3, 0) is the Map hold (V.MAP_RC) — the Mask-tool key that was here
    # duplicated TEK2's Mask once mask mode mirrored LrC (28 Sep).
    # (3, 1): bring LrC to the front. Ctrl+Opt+Cmd+L is a global Hammerspoon
    # hotkey on the Mac [stated 2 Oct, tested from the keyboard]; the board
    # just types it. Light-blue cap, like the view keys.
    (3, 1): (VIEW_KEY, C.keystroke('ctrl+alt+cmd+l')),
    (3, 2): (FINE, C.keystroke('x')),    # crop aspect: portrait/landscape
    (3, 3): (FINE, C.keystroke('o')),    # crop overlay cycle
}
# X and O are Lightroom's crop-tool keys; outside the crop tool X rejects
# the photo (measured 27 Sep). Dim and inert unless the plugin says "C".
BU16_CROP_ONLY = [(3, 2), (3, 3)]
# Reset in the corner; slot 14 is null on page 1 (a gap between the
# parameters and Reset [stated]) and a parameter where a page has one.
RESET_SLOT = 15


def bu16_for(colours, twins=(), mask_only=None):
    """colours: {slot 8..15: rgb} for the page's paged slots; twins: those
    with a mask twin (live under the Mask hold); mask_only: {slot: (rgb,
    body)} keys that exist only under Mask."""
    return 'BU16', V.bu16_page(colours, {RESET_SLOT: (WARN, C.send('reset'))}, BU16_LOWER, twins,
                               crop_only=BU16_CROP_ONLY, mask_only=mask_only)


# ============================================================ VSN1 assembly
def vsn1(labels, short, colours, parameters, mask=None, mask_labels=None, start=0,
         mask_short=None):
    short = {**short, **MAP_BU16_LOWER}
    spec = V.vsn1_keys(C.lua_table('kpar', parameters),
                       C.lua_table('kmsk', mask or {}),
                       V.vsn1_hdr({BANDS[b]: BAND_RGB[b] for b in BANDS}),
                       V.vsn1_presets(SPLIT_PRESETS))
    spec[8] = V.vsn1_dial(start)
    spec.update(C.vsn1_page_buttons())
    spec[13] = V.vsn1_lcd(labels, short, mask_labels, MAP_BU16_LOWER_C, mask_short)
    spec[255] = {0: [('cb', V.vsn1_system(colours))]}
    spec[255].update(C.SYSTEM_TAIL)
    return 'VSN1L', spec


def slots(names, rgb):
    labs = {i: n for i, n in enumerate(names) if n}
    return labs, {i: rgb for i in labs}


# =================================================================== Page 1 —
# Develop. LrC Basic order, WB first. Slot 14 null, 15 Reset (BU16, fixed).
P1_KEYS = ['Temperature', 'Tint', 'Exposure', 'Contrast',
           'Highlights', 'Shadows', 'Whites', 'Blacks',
           'Texture', 'Clarity', 'Dehaze', 'Vibrance',
           'Saturation', 'Vignette', None, None]
P1_SHORT = {0: 'Temp', 1: 'Tint', 2: 'Expo', 3: 'Cont', 4: 'High', 5: 'Shad',
            6: 'Whit', 7: 'Blac', 8: 'Text', 9: 'Clar', 10: 'Deha', 11: 'Vibr',
            12: 'Satu', 13: 'Vign', 14: 'Inv', 15: 'RSET'}
P1_PARAMS = ['Temperature', 'Tint', 'Exposure', 'Contrast',
             'Highlights', 'Shadows', 'Whites', 'Blacks',
             'Texture', 'Clarity', 'Dehaze', 'Vibrance',
             'Saturation', 'PostCropVignetteAmount', None, None]
P1_AMOUNT = {0: 4000, 1: 100, 2: 2}
P1_RES = {2: 0.05}           # Temperature takes the default 5 coarse / 1 fine too (20 Oct, stated)
P1_FRES = {2: 0.01}
# Mask twins, same slots. Vibrance -> Hue (no mask Vibrance). Vignette has no
# twin and the mask Amount slider has no SDK parameter (MIDI2LR never gained
# one; local_Amount measured dead 27 Sep), so that slot falls through to the
# global. Mask Temp/Tint are +-100, not Kelvin.
P1_MASK = ['local_Temperature', 'local_Tint', 'local_Exposure', 'local_Contrast',
           'local_Highlights', 'local_Shadows', 'local_Whites', 'local_Blacks',
           'local_Texture', 'local_Clarity', 'local_Dehaze', 'local_Hue',
           'local_Saturation', None, None, None]
P1_MASK_AMOUNT = {2: 2}
P1_MASK_RES = {2: 0.05}
P1_MASK_FRES = {2: 0.01}
P1_MASK_LABELS = {11: 'Mask Hue', 14: 'Invert Mask'}
# The map's short label for a slot under Mask, where the twin is a different
# control from the global (20 Oct, bug: the map said "Vibr" while the dial
# drove mask Hue). Slots 0-10 and 12 have twins of the same name, so need none.
P1_MASK_SHORT = {11: 'Hue'}


def page1_vsn1():
    labs, cols = slots(P1_KEYS, TONE)
    short = {k: v for k, v in P1_SHORT.items() if v}
    cols[RESET_SLOT] = WARN
    return vsn1(labs, short, cols,
                params(P1_PARAMS, P1_AMOUNT, P1_RES, P1_FRES),
                params(P1_MASK, P1_MASK_AMOUNT, P1_MASK_RES, P1_MASK_FRES),
                P1_MASK_LABELS, start=2, mask_short=P1_MASK_SHORT)


# Slot 14 — the gap — carries Invert Mask under Mask only [stated 2 Oct].
# Option+' in LrC; no-op outside a mask (measured).
P1_MASK_ONLY = {14: (MASK, C.keystroke('alt+quote'))}


def page1_bu16():
    return bu16_for({p: TONE for p in range(8, 14)},
                    twins=[i for i, n in enumerate(P1_MASK) if n and i >= 8],
                    mask_only=P1_MASK_ONLY)


def page1_vsn2():
    return vsn2('Develop')


# =================================================================== Page 2 —
# Tone: parametric curve on row 1, the grading singles on rows 3-4, Hue/Sat
# on TEK2's dials (tek2_tone). Row 2 and row 4 col 3 are deliberately empty
# [stated 1 Oct]. No mask twins.
P2_KEYS = ['Curve Highlights', 'Curve Lights', 'Curve Darks', 'Curve Shadows',
           None, None, None, None,
           'Shadow Lum', 'Midtone Lum', 'Highlight Lum', 'Global Lum',
           'Blending', 'Balance', None, None]   # LrC order: Blending first [stated]
P2_SHORT = {0: 'C-Hi', 1: 'C-Li', 2: 'C-Dk', 3: 'C-Sh',
            8: 'S-Lu', 9: 'M-Lu', 10: 'H-Lu', 11: 'G-Lu',
            12: 'Blnd', 13: 'Bal', 15: 'RSET'}
P2_PARAMS = ['ParametricHighlights', 'ParametricLights', 'ParametricDarks', 'ParametricShadows',
             None, None, None, None,
             'ColorGradeShadowLum', 'ColorGradeMidtoneLum', 'ColorGradeHighlightLum',
             'ColorGradeGlobalLum',
             'ColorGradeBlending', 'SplitToningBalance', None, None]
P2_AMOUNT = {0: 100, 1: 100, 2: 100, 3: 100}


def page2_vsn1():
    labs, cols = slots(P2_KEYS, COOL)
    for i in range(4):
        cols[i] = TONE
    cols[RESET_SLOT] = WARN
    return vsn1(labs, P2_SHORT, cols, params(P2_PARAMS, P2_AMOUNT), start=1)


def page2_bu16():
    return bu16_for({p: COOL for p in range(8, 14)})


def page2_vsn2():
    return vsn2('Tone', tone=True)


# =================================================================== Page 3 —
# Detail (was page 2 until 1 Oct).
# 1 Oct: Effects panel order is Vignette then Grain [stated]; Radius is
# 0.5-3.0 and stepped in whole units at resolution 1 (measured) — 0.1 now,
# 0.05 under Fine.
P3_KEYS = ['Sharpness', 'Radius', 'Detail', 'Masking',
           'Lum NR', 'Lum Detail', 'Lum Contrast', 'Colour NR',
           'Col Detail', 'Col Smooth', 'Vig Amount', 'Vig Midpoint',
           'Vig Feather', 'Grain Amount', 'Grain Size', None]
P3_SHORT = {0: 'Shrp', 1: 'Rad', 2: 'Det', 3: 'EMsk', 4: 'L-NR', 5: 'L-Dt',
            6: 'L-Ct', 7: 'C-NR', 8: 'C-Dt', 9: 'C-Sm', 10: 'V-Am', 11: 'V-Md',
            12: 'V-Ft', 13: 'G-Am', 14: 'G-Sz', 15: 'RSET'}
P3_PARAMS = ['Sharpness', 'SharpenRadius', 'SharpenDetail', 'SharpenEdgeMasking',
             'LuminanceSmoothing', 'LuminanceNoiseReductionDetail',
             'LuminanceNoiseReductionContrast', 'ColorNoiseReduction',
             'ColorNoiseReductionDetail', 'ColorNoiseReductionSmoothness',
             'PostCropVignetteAmount', 'PostCropVignetteMidpoint',
             'PostCropVignetteFeather', 'GrainAmount', 'GrainSize', None]
P3_AMOUNT = {1: 3}
P3_RES = {1: 0.1}
P3_FRES = {1: 0.05}


def page3_vsn1():
    labs, cols = slots(P3_KEYS, FINE)
    cols[RESET_SLOT] = WARN
    return vsn1(labs, P3_SHORT, cols, params(P3_PARAMS, P3_AMOUNT, P3_RES, P3_FRES))


def page3_bu16():
    return bu16_for({p: FINE for p in range(8, 15)})


def page3_vsn2():
    return vsn2('Detail')


# =================================================================== Page 4 —
# Dark: the sixteen unassigned, Reset and rows 3-4 still live.
def page4_vsn1():
    cols = {RESET_SLOT: WARN}
    return vsn1({}, {15: 'RSET'}, cols, {})


def page4_bu16():
    return bu16_for({})


def page4_vsn2():
    return vsn2('-')


PAGES = {
    'EN16-A HSL':   lambda: en16('EN16-A'),
    'EN16-B HSL':   lambda: en16('EN16-B'),
    'TEK2 Fixed':   tek2,
    'Page 2 TEK2':  tek2_tone,
    'Page 1 VSN1':  page1_vsn1,
    'Page 1 BU16':  page1_bu16,
    'Page 1 VSN2':  page1_vsn2,
    'Page 2 VSN1':  page2_vsn1,
    'Page 2 BU16':  page2_bu16,
    'Page 2 VSN2':  page2_vsn2,
    'Page 3 VSN1':  page3_vsn1,
    'Page 3 BU16':  page3_bu16,
    'Page 3 VSN2':  page3_vsn2,
    'Page 4 VSN1':  page4_vsn1,
    'Page 4 BU16':  page4_bu16,
    'Page 4 VSN2':  page4_vsn2,
}
