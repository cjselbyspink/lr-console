# Generator

Python that writes Grid Editor profile `.json` files from readable Lua. The board is never edited by hand in the Editor: change the Python, rebuild, import.

**Why it exists:** each event script on a Grid module is limited to 908 characters (as the Editor counts them), so readable Lua doesn't fit. Hand-pasting also drifts: what's on the module stops matching what you think is on it. The generator minifies, swaps long API names for the device's short ones (`package_send` → `gps`), checks every event against the limit, and stamps every build so the Editor can't quietly substitute an older cloud copy.

## Build

Python 3, no dependencies.

```
python3 build_all.py OUT_DIR [STAMP] [LAYOUT]
python3 build_all.py out 1020-1040 flipped     # reproduces ../configs exactly
```

The script writes one profile per module per page and runs the checks: the 908 limit, wrapper shape against the module's Default export, a stable id, lint for known Lua mistakes, and element/event structure. It stops with `CHECKS FAILED` if anything breaks.

Then:
1. Copy the files to `~/Documents/grid-userdata/configs/`, named `LR_r<stamp>_<name>.json`.
2. In Grid Editor, for each page and each module: **Clear**, load the profile, **Store**.
3. Read the code back off the module to confirm it took. Don't trust the My Configs list.

## Files

| File | What it holds |
|---|---|
| `gridgen.py` | Minifier, long → short name table (only names seen in real Editor exports), profile writer |
| `lr_common.py` | Measured mechanisms: module positions and dispatch, the dial model, drain batching, EN16 HSL and presets, BU16 helpers, timer queues, `keystroke()` |
| `lr_v2.py` | The current layout's pieces: the sixteen-key radio across VSN1 + BU16, plugin-reply receivers, mask mirroring, LCD rendering, TEK2 zone dials, VSN2 screens |
| `lr_pages2.py` | Page definitions: which parameter is on which key, colours, steps |
| `lr_pages.py` | Palettes, split-tone presets, the EN16 page, template lookup |
| `build_all.py` | Builds everything and runs the checks |
| `templates/` | Default exports from Grid Editor 1.7.x, one per module type. Every field the generator doesn't own is copied from these verbatim. |

## Adapting it

- **Different parameters on the same hardware:** edit the `P*_KEYS` / `P*_PARAMS` / `P*_SHORT` lists in `lr_pages2.py`. Parameter names are Adobe's `LrDevelopController` names; mask versions are `local_<Name>`.
- **Different arrangement of the same six modules:** add a position table in `lr_common.py` (`POS_FLIPPED` is mine) and pass its name as `LAYOUT`. Check the rotations too (`BU16_ROT`, TEK2 at 180°, EN16s at 270°): Grid Editor doesn't remap elements for a rotated module.
- **Different modules:** export a Default config for each from the Editor, add it to `templates/` and `lr_pages.EXPORTS`, then write a page function. Expect to measure things: element numbering, which callbacks a module type receives, and how its LEDs behave all differ (see ../docs/CODE-REFERENCE.md §2–4, §7).

Some code paths in `lr_common.py` and `lr_pages.py` date from earlier layouts and are no longer used. They are kept because other parts import from them; pruning them is on the to-do list.
