"""Where things are. MOD is the mod's folder (dist\\ lives in it); GAME is the game's install folder.

Run from source, MOD is this file's parent folder. Packed into ArcadeEndless.exe (PyInstaller unpacks the code to a
temp folder), MOD is the exe's folder. Either way GAME is the nearest folder at or above MOD that holds the game's
pak, so the app works in _ArcadeEndless\\, dropped straight into the game folder, or a level or two deeper.
NIGHTMARE_TOOLS is NightmarePOC's tools folder beside MOD (run from source; the exe has them packed in).
"""
import os
import sys

GAME_PAK = os.path.join("Achilles", "Content", "Paks", "Achilles-WindowsNoEditor.pak")
FROZEN = getattr(sys, "frozen", False)


def _find_game(start):
    folder = start
    for _ in range(4):
        if os.path.exists(os.path.join(folder, GAME_PAK)):
            return folder
        folder = os.path.dirname(folder)
    return os.path.dirname(start)  # not found: where it would be for the usual layout; callers report the missing pak


if FROZEN:
    MOD = os.path.dirname(os.path.abspath(sys.executable))
else:
    MOD = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
GAME = _find_game(MOD)
FOUND = os.path.exists(os.path.join(GAME, GAME_PAK))
NIGHTMARE_TOOLS = os.path.join(os.path.dirname(MOD), "_NightmarePOC", "tools")
# built paks, font cache, installed settings: never loose in the game folder itself
DIST = os.path.join(os.path.join(GAME, "_ArcadeEndless") if MOD == GAME else MOD, "dist")
