"""Generate every defined page, and check what can still be checked.

Checks (none depend on a reference page):

  1. Character budget. Every event minified, shortened, and measured the way the
     device measures it. The 908 limit is the one hard constraint.
  2. Wrapper shape. Everything except the six fields we deliberately set must be
     inherited verbatim from the module's Default export.
  3. Determinism. Building a page twice yields the same id.
  4. Lint. `%%` in emitted Lua is always a bug; so is a single-brace
     led_color (it takes {{r,g,b,a}}) and a cross-element field write.
  5. Structure. Contiguous elements, event 0 on every element, ascending events.

Usage: build_all.py OUT_DIR [REV] [LAYOUT] [PAGES_MODULE]
  LAYOUT       original | swapped | flipped   (default flipped since 27 Sep)
  PAGES_MODULE lr_pages2 (default, the redesign) or lr_pages (the old board)
"""
import datetime, importlib, json, os, re, sys
from gridgen import build_profile, MAX_MINIFIED
import lr_common

OUT = sys.argv[1] if len(sys.argv) > 1 else 'out'
REV = sys.argv[2] if len(sys.argv) > 2 else datetime.datetime.now().strftime('%m%d-%H%M')
LAYOUT = sys.argv[3] if len(sys.argv) > 3 else 'flipped'
PAGES = sys.argv[4] if len(sys.argv) > 4 else 'lr_pages2'
lr_common.set_layout(LAYOUT)
P = importlib.import_module(PAGES)

OWNED = {'id', 'name', 'createdAt', 'modifiedAt', 'virtualPath', 'configs'}
FORBIDDEN = {'cloudId', 'fileName', 'syncStatus'}


def check_lua(prof):
    bad = []
    for c in prof['configs']:
        for e in c['events']:
            cfg = e['config']
            where = 'element %s event %s' % (c['controlElementNumber'], e['event'])
            if '%%' in cfg:
                bad.append('%s: unformatted %%%% in Lua' % where)
            if re.search(r'ele\[[^\]]+\]\.\w+\s*=[^=]', cfg):
                bad.append('%s: cross-element field write' % where)
            # led_color takes a table OF tables: {{r,g,b,a}}. A single-brace
            # call is silently a no-op on the device (shipped 27 Sep in
            # relab(); the keys never changed).
            if re.search(r'glc\(\s*\d+\s*,\s*\{[^{]', cfg):
                bad.append('%s: led_color with single braces' % where)
    return bad


def check_elements(prof):
    problems = []
    els = sorted(c['controlElementNumber'] for c in prof['configs'])
    body = [e for e in els if e != 255]
    missing = [i for i in range(max(body) + 1) if i not in body] if body else []
    if missing:
        problems.append('element numbering has gaps: %s' % missing)
    for c in prof['configs']:
        evs = [e['event'] for e in c['events']]
        if not evs:
            problems.append('element %s has no events' % c['controlElementNumber'])
        elif 0 not in evs:
            problems.append('element %s has no event 0 (Setup): %s'
                            % (c['controlElementNumber'], evs))
        if evs != sorted(evs):
            problems.append('element %s events out of order: %s'
                            % (c['controlElementNumber'], evs))
    return problems


def check_wrapper(prof, template_path):
    tpl = json.load(open(template_path))
    problems = []
    for f in sorted(FORBIDDEN & set(prof)):
        problems.append('%s should have been dropped' % f)
    for f in sorted(set(tpl) - set(prof) - FORBIDDEN):
        problems.append('%s lost from template' % f)
    for f in sorted(set(prof) - OWNED):
        if f in tpl and prof[f] != tpl[f]:
            problems.append('%s diverges from template' % f)
    return problems


def main():
    os.makedirs(OUT, exist_ok=True)
    failed = False
    for name, fn in P.PAGES.items():
        mtype, spec = fn()
        path = os.path.join(OUT, name.replace(' ', '_') + '.json')
        try:
            template = P.TEMPLATES[mtype]
        except (KeyError, FileNotFoundError) as e:
            print('%-16s %-6s SKIPPED — %s' % (name, mtype, e))
            continue
        prof, report = build_profile(template, 'LR Console ' + name, spec, path,
                                     virtual_path='LR Console r%s' % REV, revision=REV)
        longest = max((r['chars'] for r in report.values()), default=0)
        over = [k for k, r in report.items() if r['over']]
        print('%-16s %-6s %2d elements   longest %3d/%d' %
              (name, mtype, len(spec), longest, MAX_MINIFIED))
        for k in over:
            print('                 OVER 908: element %s event %s — %d chars'
                  % (k[0], k[1], report[k]['chars']))
            failed = True
        for p in check_wrapper(prof, template):
            print('                 WRAPPER: %s' % p); failed = True
        for p in check_lua(prof) + check_elements(prof):
            print('                 LUA: %s' % p); failed = True
        again, _ = build_profile(template, 'LR Console ' + name, spec, revision=REV)
        if again['id'] != prof['id']:
            print('                 ID NOT STABLE — rebuild would duplicate'); failed = True
    print('\nbuild stamp: r%s   (prune older generations from My Configs)' % REV)
    print('plate layout: %s   %s' % (LAYOUT, lr_common.M))
    print('written to', OUT)
    if failed:
        print('CHECKS FAILED'); return 1
    print('all checks passed'); return 0


if __name__ == '__main__':
    sys.exit(main())
