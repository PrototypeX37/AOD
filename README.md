# Arcade Endless + NightmarePOC

Two mods for **Age of Darkness: Final Stand**, created by Lunar (76561198073513480), installed and removed from one Windows app, `ArcadeEndless.exe`. Each mod is optional and works without the other.

**[Download the latest release](https://github.com/PrototypeX37/AOD/releases/latest)** · Windows only · mostly untested: back up your saves.

## Arcade Endless

Survival and multiplayer runs that don't stop at day 45. By default a run lasts until a Final Night on day 181, and every night gets harder.

- Presets (Tough, Hard, Brutal, Apocalypse), or your own settings: how fast waves grow, Death Night days, surge nights, the Final Night.
- A table of every night: see and edit exactly which units each night brings before you play.
- Custom settings travel as a short code (`AE2-...`), so friends can install the same run.

More: [`_ArcadeEndless/README.md`](_ArcadeEndless/README.md).

## NightmarePOC

- **The Volatists can train 8 Nightmares**, from Crawlers to Crushers, at the Barracks and Siege Workshop. Set each one's gold, wood, stone, iron, food, population, train time and upkeep.
- **Heroes can be retuned**, using their real in-game stats: health, regen, armour, melee, special and ranged damage, armour shred, move speed, revive time.
- **Numpad + resource hotkey** (optional): in a match, gives the player who presses it (only them) +10,000 food and villagers and fills their wood, stone, iron and essence. Synced in multiplayer.
- **Multiplayer map seeds** (optional, experimental): the host names the game `seed_12345` and everyone's game builds that seed's map, like Survival's seed box. In the first test matches one game crashed and one froze, so treat it as unfinished.
- The main menu's hidden map editor button comes back.
- Out of the box every setting is the game's own (heroes keep their vanilla stats). Custom settings travel as a code (`NP1-...`).

More: [`_NightmarePOC/README.md`](_NightmarePOC/README.md).

## Install

1. Close the game.
2. In Steam, right-click **Age of Darkness: Final Stand** > **Manage** > **Browse local files**.
3. Extract the release zip into that folder, so you end up with `...\Age of Darkness - Final Stand\_ArcadeEndless\ArcadeEndless.exe`.
4. Run `ArcadeEndless.exe`. It isn't code-signed, so Windows may say "Windows protected your PC": click **More info**, then **Run anyway**.
5. Use the **Arcade Endless** tab, the **NightmarePOC** tab, or both, and press Install. No code needed: by default every setting is the game's own.
6. Start a new game.

To take it all off, press each tab's **Remove**. Steam's "Verify integrity of game files" also puts the original game back. A game update replaces the patched exe, so run the app and install again afterwards.

Step-by-step player guide: [`_ArcadeEndless/README_PLAYERS.txt`](_ArcadeEndless/README_PLAYERS.txt).

## Multiplayer

The game runs every player's simulation in lockstep, so **everyone in a match needs exactly the same mods and settings**. If everyone keeps the defaults, everyone just presses Install. If the host changes settings, they share the settings code, and each player pastes it, presses **Load**, then installs. Either way, compare the **match codes** in the top right of the app. Matching codes mean matching mods. Different codes mean the match will fall out of sync and end.

## What's in this repository

Only source code and docs. No game files: the app reads the player's installed game at runtime and builds the mods from it.

| Path | What |
|---|---|
| `_ArcadeEndless/ArcadeEndless.pyw` | The app (tkinter) |
| `_ArcadeEndless/tools/` | Arcade Endless's builder, validator, exe patch, and the app's helpers |
| `_NightmarePOC/tools/` | NightmarePOC's builder and validator (the app imports them) |
| `*/tools/exe_patches.py` | Every game-exe patch and the backup rule (an identical copy in each mod) |
| `_ArcadeEndless/tools/make_exe.py` | Builds `ArcadeEndless.exe` with PyInstaller |
| `_ArcadeEndless/tools/make_release.py` | Packs the release zips (the exe, a no-exe Python edition, and "play with me" packs) |

## What the app does on a player's PC

- **Reads** the game's own pak, `Achilles/Content/Paks/Achilles-WindowsNoEditor.pak`. It never writes to it.
- **Writes** the mod paks it builds (`ArcadeEndless_P.pak`, `NightmarePOC_P.pak`) into `Achilles/Content/Paks/~mods/`, after checking each one with the validators in `tools/`.
- **Arcade Endless:** changes 6 bytes in `Achilles/Binaries/Win64/Achilles-Win64-Shipping.exe` (one function that returns the game's 45-day length now returns 190), so the game prepares waves for the longer run. **Remove** puts the original bytes back.
- **NightmarePOC, only with its resource hotkey on:** patches the same exe in four verified places, so Numpad + sends the developers' own synced "add resources" debug command and that command gives the sender 10,000 food and villagers and full wood, stone, iron and essence. A dead developer function holds the new code. **Remove** puts the original bytes back. See `_NightmarePOC/README.md`.
- **NightmarePOC, only with multiplayer map seeds on:** patches the exe in three more verified places, so a multiplayer game named `seed_<text>` builds that seed's map live (normally multiplayer only loads pre-generated maps). Experimental: early test matches crashed or froze. **Remove** puts the original bytes back.
- Before the first exe patch, either mod saves a full copy of the original exe beside it as `Achilles-Win64-Shipping.exe.arcade-backup`, and only from an unpatched exe. All the patches and that rule live in `tools/exe_patches.py` (an identical copy in each mod's tools).
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

## Credits

Created by Lunar (76561198073513480). Age of Darkness: Final Stand belongs to PlaySide Studios; these are unofficial fan mods, not affiliated with or endorsed by them.
