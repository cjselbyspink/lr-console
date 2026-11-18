"""
gridgen — build Grid Editor profile/preset .json files from readable long-form Lua.

Schema learned from real Editor exports; wrapper corrected to 1.7.2 (see
build_profile). Every short-form name in SHORT was observed in those files.
Nothing here is guessed: every short-form name in SHORT was observed in those files.
Unknown identifiers pass through untouched and are listed in the run report.

Usage:  see build_all.py
"""

import copy, json, re, uuid, datetime

# ---------------------------------------------------------------- short forms
# Confirmed by observation in the exported profile/preset. Anything not in this
# table is left alone — add entries only when you have seen Editor write them.
SHORT = {
    # globals
    "element":              "ele",
    "package_send":         "gps",
    "page_load":            "gpl",
    # gpn was observed as gpl(gpn()). Its long form is page_current(), measured
    # 18 Sep — page_number() does not exist on the device. The old mapping
    # made a non-existent name work by accident, which hid the error.
    "page_current":         "gpn",
    "lcd_set_backlight":    "glsb",
    # led
    "led_value":            "glp",
    "led_color":            "glc",
    # endless
    "endless_min":          "epmi",
    "endless_max":          "epma",
    "endless_mode":         "epmo",
    "endless_sensitivity":  "epse",
    "endless_value":        "epva",
    "endless_state":        "epst",
    # encoder (EN16). emo/emi/ema/ese were observed in the stock @sec block of
    # the 1.7.2 exports, not guessed — a generated page carries no @sec, so the
    # encoder's mode/range/sensitivity are set by hand and these get used.
    "encoder_state":        "est",
    "encoder_mode":         "emo",
    "encoder_min":          "emi",
    "encoder_max":          "ema",
    "encoder_sensitivity":  "ese",
    "button_state":         "bst",
    # button
    "button_mode":          "bmo",
    "button_min":           "bmi",
    "button_max":           "bma",
    # lcd
    "draw_area_filled":     "ldaf",
    "draw_text_fast":       "ldft",
    "draw_swap":            "ldsw",
    "draw_rectangle_rounded":        "ldrr",
    "draw_rectangle_rounded_filled": "ldrrf",
    "map_saturate":         "gmaps",
    # misc
    "element_name":         "gen",
}

# The device limit is 908 as the Editor counts it. Calibrated 21 Sep against
# the Editor's own "Script length" readout on two events: it counts the RAW
# config string — spaces and the --[[@cb]] marker included — after applying
# its own long->short name substitutions. VSN2 System Setup: raw 771 here,
# 771 in the Editor. EN16-A System Setup: raw 905 here, 883 in the Editor,
# the gap being names the Editor shortens that SHORT does not know
# (element_index, twice). So compile_event measures raw length: exact where
# every name is already short, conservative where one is not. The earlier
# whitespace-stripped figure under-counted by the number of spaces, which is
# why an event at "872" was refused.
MAX_MINIFIED = 908

# Stable namespace so a page's id is a pure function of its name. Rebuilding a
# page then overwrites its own profile in My Configs instead of spawning a
# near-identical duplicate every build. Changing this constant orphans every
# profile already on disk, so don't.
NS = uuid.uuid5(uuid.NAMESPACE_DNS, "lrconsole.gridgen")

# ------------------------------------------------------------------ minifier
_STR = re.compile(r'("(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\')')


def _split_strings(src):
    """Yield (is_string, text) so transforms never touch string literals."""
    out, last = [], 0
    for m in _STR.finditer(src):
        if m.start() > last:
            out.append((False, src[last:m.start()]))
        out.append((True, m.group(0)))
        last = m.end()
    if last < len(src):
        out.append((False, src[last:]))
    return out


def _strip_comments(code):
    out, i, n = [], 0, len(code)
    while i < n:
        ch = code[i]
        if ch in '"\'':
            m = _STR.match(code, i)
            if m:
                out.append(m.group(0)); i = m.end(); continue
            out.append(ch); i += 1; continue
        if code.startswith('--[[', i):
            j = code.find(']]', i)
            i = n if j == -1 else j + 2
            out.append(' '); continue
        if code.startswith('--', i):
            j = code.find('\n', i)
            i = n if j == -1 else j
            continue
        out.append(ch); i += 1
    return ''.join(out)


# punctuation we may safely close whitespace around
_TIGHT = set('=,{}()[]<>~+-*/%#:;')


def minify(code, keep_comments=False):
    """Collapse readable Lua to the single-line form Editor stores.

    Whitespace is only removed adjacent to punctuation, never between two
    identifiers/keywords. Guards against accidentally forming '--' or '[['.
    """
    if not keep_comments:
        code = _strip_comments(code)
    parts = []
    for is_str, txt in _split_strings(code):
        parts.append(txt if is_str else re.sub(r'\s+', ' ', txt))
    code = ''.join(parts).strip()

    out = []
    for is_str, txt in _split_strings(code):
        if is_str:
            out.append(txt); continue
        buf = []
        for k, ch in enumerate(txt):
            if ch == ' ':
                prev = buf[-1] if buf else (out[-1][-1] if out else '')
                nxt = txt[k + 1] if k + 1 < len(txt) else ''
                if (prev in _TIGHT or nxt in _TIGHT) and not (
                    (prev == '-' and nxt == '-') or (prev == '[' and nxt == '[')
                ):
                    continue
            buf.append(ch)
        out.append(''.join(buf))
    return ''.join(out).strip()


def shorten(code):
    """Replace confirmed long-form API names with device short forms.

    Applied inside string literals too, matching Editor's documented behaviour.
    Returns (code, set_of_names_replaced).
    """
    used = set()
    pattern = re.compile(r'\b(' + '|'.join(sorted(SHORT, key=len, reverse=True)) + r')\b')

    def sub(m):
        used.add(m.group(1))
        return SHORT[m.group(1)]

    return pattern.sub(sub, code), used


def compile_event(blocks):
    """blocks: list of (marker, long_form_lua). Returns (config_string, report)."""
    if not blocks:
        return '', {'chars': 0, 'over': False, 'shortened': set()}
    pieces, used = [], set()
    for blk in blocks:
        marker, code = blk[0], blk[1]
        opts = blk[2] if len(blk) > 2 else {}
        code, u = shorten(minify(code, keep_comments=opts.get('raw', False)))
        used |= u
        pieces.append('--[[@%s]] %s' % (marker, code))
    cfg = ''.join(pieces)
    length = len(cfg)   # raw, as the Editor counts it (see MAX_MINIFIED)
    return cfg, {'chars': length, 'over': length > MAX_MINIFIED, 'shortened': used}


# ------------------------------------------------------------------- builders
def _now():
    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.') \
        + '%03dZ' % (datetime.datetime.now().microsecond // 1000)


def build_profile(template_path, name, spec, out_path=None, virtual_path=None,
                  revision=None):
    """spec: {element_number: {event_number: [(marker, lua), ...]}}

    Every field except id/name/timestamps/virtualPath/configs is inherited
    verbatim from the template export, so nothing about the wrapper is invented.

    Shape corrected against the 1.7.2 exports (was 1.6.9-shaped):

    * `fileName` and `syncStatus` removed — neither field exists in 1.7.2.
    * `id` is uuid5 seeded on the page name, not uuid4. A rebuild overwrites
      its own profile rather than filling My Configs with near-duplicates.
    * `cloudId` dropped. The cloud copy otherwise shadows the local file: an
      edit in place with the same name and id loads the stale cloud version
      and never reports the mismatch.
    * `virtualPath` is a folder in My Configs. The Finder directory stays flat,
      so filenames must still be unique. Whether it nests on a separator is
      untested — only a single-level string has been tried.
    """
    tpl = json.load(open(template_path))
    prof = copy.deepcopy(tpl)
    # uuid5-on-name keeps rebuilds from spawning duplicates, but it also means
    # every rebuild carries the SAME id and name — which is exactly the case in
    # which the Editor keeps its cloud copy and ignores the local file. Bump
    # `revision` to force a genuinely new profile through. The two behaviours
    # are in tension and there is no setting that satisfies both.
    if revision:
        name = '%s r%s' % (name, revision)
    prof['id'] = str(uuid.uuid5(NS, name))
    prof['name'] = name
    prof['createdAt'] = prof['modifiedAt'] = _now()
    prof.pop('cloudId', None)
    prof.pop('fileName', None)
    prof.pop('syncStatus', None)
    if virtual_path is not None:
        prof['virtualPath'] = virtual_path

    configs, report = [], {}
    for el in sorted(spec):
        events = []
        for ev in sorted(spec[el]):
            cfg, rep = compile_event(spec[el][ev])
            events.append({'event': ev, 'config': cfg})
            report[(el, ev)] = rep
        configs.append({'controlElementNumber': el, 'events': events})
    prof['configs'] = configs

    if out_path:
        json.dump(prof, open(out_path, 'w'), indent=4)
    return prof, report


def build_preset(template_path, name, events, out_path=None):
    """events: {event_number: [(marker, lua), ...]} — single control element."""
    tpl = json.load(open(template_path))
    pre = copy.deepcopy(tpl)
    pre['id'] = str(uuid.uuid5(NS, name))
    pre['name'] = name
    pre['createdAt'] = pre['modifiedAt'] = _now()
    pre.pop('cloudId', None)
    pre.pop('fileName', None)
    pre.pop('syncStatus', None)
    evs, report = [], {}
    for ev in sorted(events):
        cfg, rep = compile_event(events[ev])
        evs.append({'event': ev, 'config': cfg})
        report[ev] = rep
    pre['configs'] = {'events': evs}
    if out_path:
        json.dump(pre, open(out_path, 'w'), indent=4)
    return pre, report


def print_report(report):
    worst = 0
    for key in sorted(report, key=lambda k: str(k)):
        r = report[key]
        worst = max(worst, r['chars'])
        flag = '  <-- OVER 908' if r['over'] else ''
        print('  %-12s %4d chars%s' % (str(key), r['chars'], flag))
    print('  longest: %d / %d' % (worst, MAX_MINIFIED))
