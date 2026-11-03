"""NightmarePOC, the optional extra mod the app can install, built from the installed game like Arcade's own pak.

The builder and validator are NightmarePOC's own (_NightmarePOC\\tools); make_exe.py packs them into
ArcadeEndless.exe. Run from source, they're imported from that folder, and without it AVAILABLE is False. The
modules both mods share (pak, ue_pkg, menu_credit) are identical copies, so Arcade's are used.
"""
import functools
import os
import sys

import exe_patch
import exe_patches
import home

TOOLS = home.NIGHTMARE_TOOLS
if not home.FROZEN and os.path.isdir(TOOLS):
    sys.path.append(TOOLS)
try:
    import build_mod
    import validate
    AVAILABLE = True
except ImportError:
    AVAILABLE = False

BASE_PAK = os.path.join(home.GAME, home.GAME_PAK)
OUT_PAK = os.path.join(home.DIST, "NightmarePOC_P.pak")
INSTALLED = os.path.join(os.path.dirname(exe_patch.MOD_PAK), "NightmarePOC_P.pak")
INSTALLED_SETTINGS = os.path.join(home.DIST, "nightmare_settings.txt")  # "<settings code> <match code>"
LAST_SETTINGS = os.path.join(home.DIST, "nightmare_last_settings.txt")  # the last code installed; Remove keeps it
BUILDINGS = {"BARRACKS_T0": "Barracks", "WORKSHOP_T2": "Siege Workshop"}
HOTKEYS = "QWERASDFZXCV"  # the command card's 4x3 grid, by button_index


def build(settings, out=OUT_PAK):
    build_mod.main(out, BASE_PAK, settings)


def check(settings, path=OUT_PAK):
    """0 if every check passes."""
    return validate.main(path, BASE_PAK, settings)


def set_hotkey(on):
    """Turn the Numpad + resource hotkey exe patch on or off (exe_patches.PatchError if it can't)."""
    return exe_patches.set_hotkey(exe_patch.EXE, on)


def set_seeds(on):
    """Turn the multiplayer map seeds exe patch on or off (exe_patches.PatchError if it can't)."""
    return exe_patches.set_seeds(exe_patch.EXE, on)


def defaults():
    return build_mod.Settings() if AVAILABLE else None


def installed_settings():
    """The settings of the NightmarePOC pak in ~mods, if this app installed it."""
    try:
        code, match = open(INSTALLED_SETTINGS).read().split()
        if os.path.exists(INSTALLED) and exe_patch.match_code(INSTALLED) == match:
            return build_mod.Settings.from_code(code)
    except (OSError, ValueError, NameError):
        pass
    return None


def last_settings():
    """The settings last installed through this app, even if NightmarePOC has since been removed or deleted, so a
    fresh install starts from them rather than the defaults."""
    try:
        return build_mod.Settings.from_code(open(LAST_SETTINGS).read().strip())
    except (OSError, ValueError, NameError):
        return None


def unit_label(unit):
    return "Volatist Crusher" if unit == "VolatistCrusher" else unit


def trained_at(unit):
    for u in build_mod.VOLATIST_UNITS + build_mod.BORROWED_UNITS:
        if u[0] == unit:
            building, slot = (u[3], u[4]) if u in build_mod.VOLATIST_UNITS else (u[4], u[5])
            return f"{BUILDINGS[building]} ({HOTKEYS[slot]})"
    raise KeyError(unit)


@functools.lru_cache(maxsize=1)
def game_values():
    """{hero: {stat: the game's value at build_mod.HERO_LEVEL, or None}}, read from the game once."""
    return build_mod.hero_game_values(BASE_PAK)


def shown(hero, field, x):
    """The value the window shows for a hero stat whose setting is x (a multiplier; armour: a value or None)."""
    game = game_values()[hero][field]
    if game is None:
        return ""
    return f"{(game if x is None else x) if field == 'armour' else game * x:.6g}"


def setting(hero, field, text):
    """The setting for a hero stat the window shows as text: the inverse of shown(). ValueError if it isn't a number."""
    game = game_values()[hero][field]
    if game is None:
        return None if field == "armour" else 1.0
    value = float(text)
    if field == "armour":
        return None if abs(value - game) < 1e-6 * max(1.0, game) else value
    return float(f"{value / game:.6g}")


def describe(s):
    """A short line on how settings s differ from the defaults."""
    d = build_mod.Settings()
    units = [unit_label(n) for n, a, b in zip(build_mod.UNIT_ORDER, s.units, d.units) if a != b]
    heroes = [n for n, a, b in zip(build_mod.HEROES, s.heroes, d.heroes) if a != b]
    parts = ([f"costs for {', '.join(units)}"] if units else []) + ([f"stats for {', '.join(heroes)}"] if heroes else [])
    extras = "".join(text for on, text in ((s.hotkey, " and the resource hotkey"), (s.seeds, " and multiplayer map seeds"))
                     if on)
    return ("custom " + " and ".join(parts) if parts else "the defaults") + extras
