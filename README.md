# Arcade Endless + NightmarePOC

Two mods for **Age of Darkness: Final Stand**, created by Lunar (76561198073513480), installed from one Windows app, `ArcadeEndless.exe`.

- **Arcade Endless:** Survival and multiplayer runs last until a Final Night on day 181 (by default), and every night gets harder. See [`_ArcadeEndless/README.md`](_ArcadeEndless/README.md).
- **NightmarePOC** (optional): the Volatists can train Nightmares, with costs you set; heroes can be retuned; the hidden Editor button comes back. See [`_NightmarePOC/README.md`](_NightmarePOC/README.md).

Players: download the release from Nexus Mods and follow [`_ArcadeEndless/README_PLAYERS.txt`](_ArcadeEndless/README_PLAYERS.txt).

## What's in this repository

Only source code and docs. No game files: the app reads the player's installed game at runtime and builds the mods from it.

| Path | What |
|---|---|
| `_ArcadeEndless/ArcadeEndless.pyw` | The app (tkinter) |
| `_ArcadeEndless/tools/` | Arcade Endless's builder, validator, exe patch, and the app's helpers |
| `_NightmarePOC/tools/` | NightmarePOC's builder and validator (the app imports them) |
| `_ArcadeEndless/tools/make_exe.py` | Builds `ArcadeEndless.exe` with PyInstaller |
| `_ArcadeEndless/tools/make_release.py` | Packs the two release zips (the exe, and a no-exe Python edition) |

## What the app does on a player's PC

- **Reads** the game's own pak, `Achilles/Content/Paks/Achilles-WindowsNoEditor.pak`. It never writes to it.
- **Writes** the mod paks it builds (`ArcadeEndless_P.pak`, `NightmarePOC_P.pak`) into `Achilles/Content/Paks/~mods/`, after checking each one with the validators in `tools/`.
- **Arcade Endless only:** changes 6 bytes in `Achilles/Binaries/Win64/Achilles-Win64-Shipping.exe` (one function that returns the game's 45-day length now returns 190), so the game prepares waves for the longer run. Before the first change it saves a full copy of the original exe beside it as `Achilles-Win64-Shipping.exe.arcade-backup`. **Remove** puts the original bytes back. See `_ArcadeEndless/tools/exe_patch.py`.
- Keeps its own working files (built paks, the game fonts it extracts for its look, the installed settings) in `_ArcadeEndless/dist/`.
- **No network access**: nothing is downloaded or sent.

## Building the exe

Needs Windows and Python 3 (made with 3.13).

```powershell
pip install pyinstaller pillow
python _ArcadeEndless/tools/make_exe.py
python _ArcadeEndless/tools/make_release.py
```

`make_exe.py` writes `_ArcadeEndless/ArcadeEndless.exe` (PyInstaller one-file, windowed). It works from a fresh clone anywhere; with the game installed next to it, the icon uses the game's Cinzel font, otherwise Georgia. `make_release.py` writes `_ArcadeEndless/release/ArcadeEndless-<version>.zip` and `...-python.zip`.

## Running from source

Put `_ArcadeEndless` and `_NightmarePOC` in the game folder and double-click `_ArcadeEndless/ArcadeEndless.pyw` (Pillow is optional, for the artwork). `python _ArcadeEndless/ArcadeEndless.pyw --selftest` checks the app, and builds and validates NightmarePOC, without installing anything.
