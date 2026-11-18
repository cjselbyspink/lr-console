"""Surviving parts of the pre-redesign lr_pages.py (27 Sep 2026): the template
lookup, the palettes, the split-tone presets and the EN16 page, which the
redesign uses unchanged. The old page 1-4 definitions are in the project's
lr_pages.py and are superseded by lr_pages2.py."""

import os
import lr_common as C

SEARCH_DIRS = [
    os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates'),
    os.path.dirname(os.path.abspath(__file__)),
    '/mnt/project',
    '/mnt/user-data/uploads',
    os.path.expanduser('~/grid-exports'),
]

EXPORTS = {
    'VSN1L':  'Default_VSN1L_Configuration_1.json',
    'EN16-A': 'Default_EN16-A_Configuration_1.json',
    'EN16-B': 'Default_EN16-B_Configuration_1.json',
    'TEK2':   'Default_TEK2_Configuration_2.json',
    'BU16':   'Default_BU16_Configuration_1.json',
    'VSN2':   'Default_VSN2_Configuration_1.json',
}


def export(filename):
    for d in SEARCH_DIRS:
        p = os.path.join(d, filename)
        if os.path.isfile(p):
            return p
    raise FileNotFoundError(
        '%s not found. Export it from Grid Editor and put it in one of:\n  %s'
        % (filename, '\n  '.join(SEARCH_DIRS)))


class _Templates:
    def __getitem__(self, mtype):
        return export(EXPORTS[mtype])

    def get(self, mtype, default=None):
        try:
            return self[mtype]
        except (KeyError, FileNotFoundError):
            return default


TEMPLATES = _Templates()

# ------------------------------------------------------------------- palettes
BANDS = {0: 'Red', 1: 'Orange', 2: 'Yellow', 3: 'Green',
         4: 'Aqua', 5: 'Blue', 6: 'Purple', 7: 'Magenta'}
BAND_RGB = {0: (255, 0, 0), 1: (255, 110, 0), 2: (255, 220, 0), 3: (40, 200, 0),
            4: (0, 200, 180), 5: (0, 90, 255), 6: (140, 0, 255), 7: (255, 0, 180)}

TONE = (255, 190, 90)
COOL = (150, 190, 255)
MASK = (120, 230, 180)
FINE = (200, 200, 210)
CREAM = (245, 235, 205)
WARN = (255, 110, 0)
STAR = (235, 205, 120)
NAV = (170, 190, 210)
CULL_R = (255, 0, 25)
CULL_G = (0, 255, 40)

# (label, led_rgb, shadow_hue, shadow_sat, highlight_hue, highlight_sat)
SPLIT_PRESETS = {
    0: ('Teal/orange',  (0, 200, 180),   210, 20,  45, 20),
    1: ('Warm/violet',  (200, 120, 255), 275, 12,  40, 10),
    2: ('Filmic green', (60, 200, 90),   140, 15,  45, 12),
    3: ('Warm mono',    (230, 180, 90),   30, 22,  45, 15),
    4: ('Clear',        BAND_RGB[1],       0,  0,   0,  0),
}


EN16_IDLE = 0.05   # 28 Sep: CJ wants dimmer still; 0.05 was once measured as off [?]


def en16(which):
    offset = 0 if which == 'EN16-A' else 4
    spec = C.en16_elements()
    presets = {b: v for b, v in SPLIT_PRESETS.items() if offset <= b < offset + 4}
    spec[255] = {0: [('cb', C.en16_system(BANDS, BAND_RGB, alpha=EN16_IDLE,
                                          band_offset=offset,
                                          presets=presets))]}
    spec[255].update(C.SYSTEM_TAIL)
    # The plugin's reply is broadcast to every module; a no-op receiver on
    # element 0 keeps it off the error log here (added 28 Sep).
    spec[0][0] = [('cb', '\n'.join(['LrImportActive = function() end',
                                     C.en16_element0(EN16_IDLE, offset),
                                     spec[0][0][0][1]]))]
    return which, spec
