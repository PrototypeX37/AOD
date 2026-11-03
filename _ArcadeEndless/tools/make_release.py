"""Pack what players need into two zips in _ArcadeEndless\\release\\:

  ArcadeEndless-<version>.zip         ArcadeEndless.exe + README.txt (README_PLAYERS.txt)
  ArcadeEndless-<version>-python.zip  the same app as Python source (ArcadeEndless.pyw, both mods' tools) + README.txt
                                      (README_PLAYERS_PYTHON.txt, then README_PLAYERS.txt), for players who won't run an exe

  python make_release.py

  python make_release.py friends [settings code...]
      PlayWithLunar-<match codes>.zip: ArcadeEndless.exe + "READ ME FIRST.txt", a step-by-step guide carrying the
      settings codes and match codes of the mods this PC has installed through the app (or of the AE2-/NP1- codes
      given, built here to get their match codes), so the people you play with install exactly the same thing and
      remove whichever mod isn't in it.

All extract straight into the game folder. None holds a pak (game data): the app builds both mods from each
player's own game files. Run make_exe.py first; this refuses an exe older than the code it's built from.
"""
import os
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import home  # noqa: E402
import make_exe  # noqa: E402

VERSION = "1.1"
GUIDE = os.path.join(home.MOD, "README_PLAYERS.txt")
PYTHON_GUIDE = os.path.join(home.MOD, "README_PLAYERS_PYTHON.txt")
RELEASE = os.path.join(home.MOD, "release")
EXE_ZIP = os.path.join(RELEASE, f"ArcadeEndless-{VERSION}.zip")
PYTHON_ZIP = os.path.join(RELEASE, f"ArcadeEndless-{VERSION}-python.zip")
BUILD_SCRIPTS = ("make_exe.py", "make_release.py")  # not part of the app


def sources():
    """{path in the zip: file} for the app's code: the .pyw, Arcade's tools and NightmarePOC's tools."""
    files = {"_ArcadeEndless/ArcadeEndless.pyw": make_exe.APP}
    for folder, prefix in ((HERE, "_ArcadeEndless/tools/"), (make_exe.NIGHTMARE_TOOLS, "_NightmarePOC/tools/")):
        for n in sorted(os.listdir(folder)):
            if n.endswith(".py") and n not in BUILD_SCRIPTS:
                files[prefix + n] = os.path.join(folder, n)
    return files


def text(*paths):
    """The files' text joined, with Notepad-friendly line endings."""
    out = ""
    for p in paths:
        with open(p, encoding="utf-8") as f:
            out += f.read()
    return out.replace("\r\n", "\n").replace("\n", "\r\n")


def write_zip(path, files, readme, readme_name="README.txt"):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name, src in files.items():
            z.write(src, name)
        z.writestr("_ArcadeEndless/" + readme_name, readme)
    with zipfile.ZipFile(path) as z:
        assert z.testzip() is None
        for i in z.infolist():
            print(f"  {i.filename:40} {i.file_size:>12,} bytes")
    print(f"Wrote {path} ({os.path.getsize(path) / 1e6:.2f} MB)\n")


HERO_WORDS = {"health": "health", "regen": "health regen", "armour": "armour", "melee": "melee damage",
              "special": "special damage", "ranged": "ranged damage", "shred": "armour shred", "speed": "move speed",
              "revive": "revive time"}


def installed():
    """(Arcade Endless, NightmarePOC) as installed on this PC through the app: each (settings, match code) or None."""
    import build_endless as be
    import exe_patch
    import nightmare
    arcade = None
    record = os.path.join(home.DIST, "installed_settings.txt")
    if os.path.exists(exe_patch.MOD_PAK):
        try:
            code, match = open(record).read().split()
            assert exe_patch.match_code(exe_patch.MOD_PAK) == match
            arcade = (be.Settings.from_code(code), match)
        except (OSError, ValueError, AssertionError):
            sys.exit("Arcade Endless is in ~mods, but not as the app installed it: install it from the app first.")
    nm = None
    if os.path.exists(nightmare.INSTALLED):
        s = nightmare.installed_settings()
        if s is None:
            sys.exit("NightmarePOC is in ~mods, but not as the app installed it: install it from the app first.")
        nm = (s, exe_patch.match_code(nightmare.INSTALLED))
    return arcade, nm


def from_codes(codes):
    """(Arcade Endless, NightmarePOC) for the settings codes given: each (settings, match code) or None. Each pak is
    built and validated here, as a player's app would, to get its match code."""
    import contextlib
    import io
    import shutil
    import build_endless as be
    import exe_patch
    import nightmare
    import validate_endless as ve
    arcade = nm = None
    folder = os.path.join(home.DIST, "friends")
    for code in codes:
        log = io.StringIO()
        if code.startswith(nightmare.build_mod.CODE_PREFIX):
            s, out = nightmare.build_mod.Settings.from_code(code), os.path.join(folder, "NightmarePOC_P.pak")
            with contextlib.redirect_stdout(log):
                nightmare.build(s, out)
                ok = nightmare.check(s, out) == 0
            nm = (s, exe_patch.match_code(out))
        elif code.startswith("AE2-"):
            s, out = be.Settings.from_code(code), os.path.join(folder, "ArcadeEndless_P.pak")
            with contextlib.redirect_stdout(log):
                be.main(s, out)
                ok = ve.main(out) == 0
            arcade = (s, exe_patch.match_code(out))
        else:
            sys.exit(f"Not a settings code: {code[:20]}... (Arcade Endless codes start with AE2-, NightmarePOC's with NP1-)")
        if not ok:
            sys.exit("Validation failed:\n" + "\n".join(line for line in log.getvalue().splitlines() if "FAIL" in line))
    shutil.rmtree(folder, ignore_errors=True)
    return arcade, nm


def nightmare_lines(s):
    """What NightmarePOC settings change, for people who'll install them."""
    import nightmare
    bm = nightmare.build_mod
    d = bm.Settings()
    costs = [nightmare.unit_label(n) for n, a, b in zip(bm.UNIT_ORDER, s.units, d.units) if a != b]
    lines = ["Volatists can train Nightmares, " + (f"with custom costs for {', '.join(costs)}" if costs else "at the default costs")]
    for hero in bm.HEROES:
        h = s.hero(hero)
        changes = [f"armour {h[f]:g}" if f == "armour" else f"{HERO_WORDS[f]} x{h[f]:g}"
                   for f in bm.HERO_FIELDS if (h[f] is not None if f == "armour" else h[f] != 1)]
        if changes:
            lines.append(f"{hero}: {', '.join(changes)}")
    lines.append("Numpad + resource hotkey: " + ("ON. In a match, Numpad + gives the player who presses it (only them) "
                                                 "10,000 food and villagers and fills their wood, stone, iron and essence."
                                                 if s.hotkey else "off"))
    lines.append("Multiplayer map seeds: " + ("ON. The host names the game \"seed_12345\" (letters, digits and _ only) "
                                              "and everyone's game builds that map. Experimental: of the first two test "
                                              "matches, one crashed and one froze." if s.seeds else "off"))
    return lines


def friends_guide(arcade, nm):
    out = ["PLAYING WITH LUNAR'S MODS", "=" * 70, "",
           "Every player in a multiplayer match needs exactly the same mods and settings,",
           "or the match falls out of sync. This sets your game up to match.", "",
           "Mods for these games:"]
    if nm:
        out.append(f"  NightmarePOC: ON (match code {nm[1]})")
        out += [f"    - {line}" for line in nightmare_lines(nm[0])]
    else:
        out.append("  NightmarePOC: OFF")
    out.append(f"  Arcade Endless: ON (match code {arcade[1]})" if arcade else "  Arcade Endless: OFF")
    out += ["", "", "SET UP (once)", "",
            "1. Close the game.",
            "2. In Steam, right-click Age of Darkness: Final Stand > Manage > Browse local",
            "   files.",
            "3. Extract this zip into that folder. You should end up with",
            "      ...\\Age of Darkness - Final Stand\\_ArcadeEndless\\ArcadeEndless.exe",
            "   (It must be inside the game folder, or it can't find the game.)",
            "4. Run ArcadeEndless.exe. It isn't code-signed, so Windows may say \"Windows",
            "   protected your PC\": click More info, then Run anyway."]
    step = 5
    for name, tab, mod, install in (("NightmarePOC", "NightmarePOC", nm, "Install NightmarePOC"),
                                    ("Arcade Endless", "Arcade Endless", arcade, "Build & install Arcade Endless")):
        if mod:
            out += [f"{step}. Open the {tab} tab. Paste this into the empty box next to the Load",
                    "   button and press Load:", "", f"      {mod[0].code()}", "",
                    f"   Then press {install}."]
        else:
            out += [f"{step}. {name} isn't used: if its tab says it's installed, press that",
                    "   tab's Remove."]
        step += 1
    out += [f"{step}. Check the top right of the app. It must show:",
            f"      ARCADE ENDLESS  {'match ' + arcade[1] if arcade else 'not installed'}",
            f"      NIGHTMAREPOC    {'match ' + nm[1] if nm else 'not installed'}",
            "   If a match code is different, your game version or settings differ: don't",
            "   play together until it matches.", "", "",
            "GOOD TO KNOW", "",
            "- Everyone needs the same game version (let Steam update the game).",
            "- A Steam update puts the original game exe back: run the app and install",
            "  again afterwards.",
            "- Start a new game for new settings to apply.",
            "- To take it all off: each tab's Remove. Do it between matches, not in the",
            "  middle of a saved game.",
            "- Created by Lunar (76561198073513480)."]
    return "\n".join(out).replace("\n", "\r\n") + "\r\n"


def friends(codes=()):
    arcade, nm = from_codes(codes) if codes else installed()
    if not arcade and not nm:
        sys.exit("Neither mod is installed on this PC (give settings codes instead), so there's nothing to match.")
    os.makedirs(RELEASE, exist_ok=True)
    tag = "-".join(([f"NightmarePOC-{nm[1]}"] if nm else []) + ([f"ArcadeEndless-{arcade[1]}"] if arcade else []))
    path = os.path.join(RELEASE, f"PlayWithLunar-{tag}.zip")
    guide = friends_guide(arcade, nm)
    write_zip(path, {"_ArcadeEndless/ArcadeEndless.exe": make_exe.EXE}, guide, "READ ME FIRST.txt")
    print(guide.replace("\r\n", "\n"))


def main(argv):
    code = sources()
    newest = max(code.values(), key=os.path.getmtime)
    if not os.path.exists(make_exe.EXE) or os.path.getmtime(make_exe.EXE) < os.path.getmtime(newest):
        sys.exit(f"{make_exe.EXE} is older than {newest}: run make_exe.py first.")
    if argv[1:2] == ["friends"]:
        return friends(argv[2:])
    os.makedirs(RELEASE, exist_ok=True)
    write_zip(EXE_ZIP, {"_ArcadeEndless/ArcadeEndless.exe": make_exe.EXE}, text(GUIDE))
    write_zip(PYTHON_ZIP, code, text(PYTHON_GUIDE, GUIDE))


if __name__ == "__main__":
    main(sys.argv)
