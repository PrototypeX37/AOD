# NightmarePOC: Age of Darkness: Final Stand mod

The mod is one pak file, `NightmarePOC_P.pak`, plus optional exe patches for the resource hotkey and multiplayer map seeds. The pak doesn't modify any game files: the game loads it on top of its own pak, and deleting the file removes it. Every change applies to both Survival and multiplayer. The campaign isn't touched.

**The easy way:** open the app (`_ArcadeEndless\ArcadeEndless.exe`) and use its **NightmarePOC** tab. It explains the mod, sets what every Nightmare costs, every hero's stats, the hotkey and map seeds (see [Settings](#settings)), and installs or removes it all. Arcade Endless isn't needed: it has its own tab, and each mod installs on its own.

## What it does

### 1. Shows the hidden map editor button
The developers' in-game mission and map editor ships with the game, but code hides its main-menu button. The mod shows it again. Look for an **Editor** button near the bottom-left of the main menu, about a quarter of the way across. This is the developers' internal tool, so expect rough edges.

**Main-menu credit.** The main menu shows "Mod created by Lunar (76561198073513480)" above the news panel at the bottom right, where the game's old Early Access title used to be. NightmarePOC and Arcade Endless both ship this credit, so both mods replace the main menu's file (`Menu_UI`). That's the only file they share. With both installed, the game uses NightmarePOC's copy: it has the same credit plus NightmarePOC's Editor button. Unreal picks the copy from the pak whose name sorts last, so keep both paks in `Paks\~mods`.

### 2. The Volatists can train Nightmares
Pick the **Volatists** on the Survival faction screen. No other faction changes. By default Nightmares don't use villagers (population), housing or food. Every cost below is a setting.

| Unit | Trained at (hotkey) | Default cost | Train time | Upkeep |
|---|---|---|---|---|
| Crawler | Barracks (R) | 90 gold | 10 s | 3 gold |
| Burster | Barracks (D) | 120 gold | 12 s | 4 gold |
| Axeman | Barracks (F) | 160 gold, 10 wood | 15 s | 6 gold |
| Spearman (javelins) | Barracks (X) | 200 gold, 15 wood | 18 s | 8 gold |
| Spitter | Siege Workshop (R) | 600 gold, 20 stone, 10 iron | 30 s | 15 gold |
| Volatist Crusher (ranged tank) | Siege Workshop (A) | 800 gold, 25 stone, 15 iron | 35 s | 18 gold |
| Crusher (the horde's big brute) | Siege Workshop (S) | 900 gold, 30 stone, 20 iron | 40 s | 20 gold |
| Wraith | Siege Workshop (D) | 350 gold, 5 iron | 25 s | 12 gold |

The command card is a 4×3 grid (Q W E R / A S D F / Z X C V). The Barracks has only four free slots, so the Wraith goes in the Siege Workshop. The game always uses slot 8 (Z) for the upgrade button, 10 (C) for sell and 11 (V) for repair, so units never go there.

These units come from two sources:
- **Burster, Wraith, Spitter and Volatist Crusher** are the developers' own player-side Volatist units. They were already in the game data but weren't trainable.
- **Crawler, Axeman, Spearman and Crusher** use the horde's models and attacks. The game decides how to set up a unit from its *type*, and any type with enemy data is treated as horde AI; that's what crashed the first version when you selected a unit. So these four are given to four campaign-only unit types that Survival and multiplayer never use: Alderin Pikeman, Alderin Arbalest, Injured Theda and Crazed Order Aurelia. They get the Nightmare's data and no enemy data. The horde's own Nightmares are unchanged.

### 3. Heroes
Every playable hero's stats are settings: Aelis, Aurelia, Cyrus, Edwin, Hector, Merek, Order Aurelia, Theda and Vizargo. By default every hero keeps the game's own stats.

Earlier versions of NightmarePOC always made Vizargo much stronger. To get that back, load this settings code in Customise (or give it to `build_mod.py`):

```
NP1-eNqrVipVsqqu1VHKAFJKYZlViUXp-UpW0UZ6BjogbGhgAGXBsAlIFIJja2sBKj8P1Q
```

| Stat | Change |
|---|---|
| Health and health regen | ×2 |
| Melee, Scythe Blast and Serenity damage, plus their burn damage | ×2 |
| Armour | 100 at every level |
| Armour shred on all his attacks | ×4 |

How armour works in this game: each armour layer cuts incoming damage by 70%, down to a minimum per hit. **At 100 armour Vizargo takes only that minimum until enemies shred his armour off.** Any change to Vizargo's ranged damage also applies to his Clone, because both fire the same Serenity projectiles.

### 4. Numpad + resource hotkey (optional, off by default)
In a match, pressing **Numpad +** gives you, and only you, **+10,000 food and +10,000 villagers** and fills your **wood, stone, iron and essence** to their storage caps. It's sent like any other order, so in multiplayer every player's game applies it at the same moment to the player who pressed it. Everyone in the match needs the same NightmarePOC settings (the match code covers the hotkey and its patch version too).

This is the one part that isn't data: it patches the game exe, because the amounts and the key are compiled code. Installing with the hotkey on applies the patch; installing with it off, or **Remove**, takes it out again. Before the first exe patch, a full copy of the original exe is saved as `Achilles-Win64-Shipping.exe.arcade-backup` (shared with Arcade Endless's own exe patch; it's only ever taken from an exe with neither patch). A Steam update or "Verify integrity of game files" puts the original exe back, so install again afterwards.

The hotkey uses machinery the developers left in the release build. Their debug options still exist as a synced game command, and its "add resources" case runs on every player's PC for the player who sent it. The patch, in `tools\exe_patches.py`, changes four places in `Achilles-Win64-Shipping.exe`, each checked byte for byte first, so another game version is refused:

- A dead developer function (`UDebugUI::unlock_all_meta_progression`, which nothing calls) becomes empty and holds two small new routines.
- `UDebugUI::add_resources` jumps to the first routine. For the sending player's team it fills wood, stone, iron and essence to their storage caps. Food and villagers are supply the game recomputes every tick from per-team totals:
  - villagers on hand = a lasting bonus + what houses give − what's in use;
  - food on hand = what farms give − what's in use, and food capacity = farms + the bonus.

  So it adds 10,000 to both bonuses (as the map editor's "change resources" trigger does) and also takes 10,000 off food in use. "In use" is what units hold, added and removed one unit at a time as they're trained and lost, so the extra stays. Version 1 of the patch only raised food capacity, so the food number didn't move. Version 2 fixes that, and the app upgrades a version 1 patch when you install again.
- The player controllers' Ticks call the second routine. That routine runs the normal Tick, then, if Unreal reports Numpad + was just pressed, queues the developers' own "add resources" command. Unreal only reports keys while the game window has focus, and only to your own controller. Survival and multiplayer use different player controllers (`GamePlayerController` and `MpGamePlayerController`), so both are hooked. Versions 1 and 2 of the patch hooked only Survival's, so the key did nothing in multiplayer. Version 3 fixes that, and installing again upgrades an older patch.

### 5. Multiplayer map seeds (optional, off by default)
Survival lets you type a map seed; multiplayer normally doesn't. With this on, the host names the multiplayer game **`seed_12345`** (or `seed_` followed by any letters and digits) and everyone's game builds the map for that seed. Any other game name keeps the game's usual random pick. The name box only takes letters, digits and `_` (the game's own rule, since it's also the save file's name), so `seed 12345` with a space is refused. The `_` after `seed` is skipped: `seed_12345` and `seed12345` are the same seed. A numeric seed is used as the number, any other text is hashed, exactly as Survival reads its seed box. A multiplayer map isn't the same as the Survival map with the same seed, because multiplayer uses its own map rules (room for every player's keep).

Why it needs an exe patch: multiplayer never builds maps from a seed. Its first, Voronoi stage comes from one of 301 pre-generated files that ship with the game (`Content/VoronoiPreGen/Multiplayer11x11/<seed>.map`), and the host's game picks a seed from that list. Survival runs that stage live, and everything after it is built live in both modes. The patch, also in `tools\exe_patches.py`, changes three places:

- **Every PC:** `UMapGeneratorSubsystem::GenerateMap` marked the pre-generated data as loaded even when there was no file for the seed. It now keeps the loader's answer, so a seed without a file is generated live (Voronoi stage included), with the multiplayer map rules. The game's own seeds still load their files, exactly as before.
- **The host:** just before `AAchillesGameSession::PostLogin` hands the seed to the game state (which sends it to every player), a routine reads the game name. If it starts with `seed`, the rest becomes the seed. A loaded save keeps its own seed. The routine lives in `UDebugUI::lock_all_skills`, a developer function only a debug command nobody sends ever reaches.

Everyone in the match needs it, so the switch is part of the settings code and the match code. **Experimental.** In the first two test matches with a live seed (`seed6833` and `seed_6833`, two players), the map was built and the match started both times. But one game crashed about 18 seconds in ("Ran out of memory allocating 67108864 bytes") and the other froze about 80 seconds in, waiting on the other player. The cause isn't known yet. Every PC builds the map itself, and the developers pre-generate multiplayer maps, perhaps for speed, perhaps because the generator isn't guaranteed to give identical results on different PCs. If two PCs ever build different maps, the game's own checksum ends the match ("Simulation divergence" in the log). If that happens, use the game's own seeds (any name not starting with `seed`).

## Settings

The app's **NightmarePOC** tab has two tables and two switches (the hotkey and map seeds):

- **Nightmare units:** each unit's gold, wood, stone, iron, food, population (villagers it uses), train time and gold upkeep.
- **Heroes:** each hero's health, health regen, armour, melee damage, special-attack damage, ranged damage per shot, armour shred, move speed and revive time. The boxes show the hero's real stats at level 10, the top level. Changing one changes every level in proportion; armour is set to the same value at every level. Damage over time scales with its attack. Shred shows the hero's main armour shred, and their other attacks' shred scales with it. A greyed-out box means the hero has no such attack (Cyrus has only a ranged attack, for example). Other abilities keep the game's numbers.

Settings travel as a code starting `NP1-`, shown under the tables; it includes both switches. **Multiplayer:** every player must install the same settings. Send the code; each player loads it on the tab and installs, then everyone compares match codes. The build is deterministic, so the same code and the same game version always make the same pak.

## Install

1. Close the game.
2. In the game folder, create `Achilles\Content\Paks\~mods\`.
3. Copy `_NightmarePOC\dist\NightmarePOC_P.pak` into that folder.

Or run these two commands in PowerShell from the game folder (`...\steamapps\common\Age of Darkness - Final Stand`):

```powershell
New-Item -ItemType Directory -Force "Achilles\Content\Paks\~mods" | Out-Null
Copy-Item "_NightmarePOC\dist\NightmarePOC_P.pak" "Achilles\Content\Paks\~mods\"
```

**Multiplayer:** every player needs the identical `NightmarePOC_P.pak`. The game runs a lockstep simulation, so if one player's unit data differs, the match will desync. Copy the same file to each player. If anyone still has an older version, replace it.

If the Editor button doesn't appear, move the pak up one level, directly into `Achilles\Content\Paks\` next to `Achilles-WindowsNoEditor.pak`. Do this only without Arcade Endless installed: with Arcade's pak in `~mods`, a NightmarePOC pak one level up loses the main menu to Arcade's, and the Editor button disappears.

## Remove

Delete the pak. The game is then vanilla again.

```powershell
Remove-Item "Achilles\Content\Paks\~mods\NightmarePOC_P.pak"
```

Remove it between matches, not in the middle of a saved game. A save that contains Nightmares you trained hasn't been tested without the mod installed.

## Status

- `tools\validate.py` checks:
  - pak structure and every asset round-tripping;
  - a diff against the base game, showing only the intended pieces change;
  - the main menu: the Editor button call at the start of `Tick`, and the credit;
  - every trainable type spawns as a normal player unit (it has player data and no enemy data);
  - no command-card slot is shared with another Volatist unit, with research the Volatists can see, or with the sell/repair/upgrade buttons, in both modes;
  - each Nightmare's costs, train time and upkeep match the settings;
  - every hero's stats at all 10 levels compared with the base game: scaled or set as the settings say, every other stat byte-for-byte the game's;
  - the projectiles each hero's ranged attack fires take its ranged damage and shred settings, and no other projectile changes;
  - the hotkey and map seeds marker files are in the pak exactly when the settings turn those on.

  The hotkey's exe patch was checked by assembling it, disassembling it with every call target confirmed, and applying and removing it on a copy of the exe (removing gives back the exact original bytes). It hasn't been tried in a match yet. The map seeds patch was checked the same way, its routine traced by hand for the names `seed 12345`, `SEED hello world ` (trailing space), `seed`, `seed ` and `Multiplayer`. In two test matches it built the map, then one game crashed and one froze (see section 5).

  The Vizargo code above rebuilds the exact same pak as before heroes were settings (same match code).
- **Not yet tested in-game.** The Volatist units took the crash fix from v2. The four horde-model units on borrowed types are the newest part, so test those first. If anything misbehaves, delete the pak and the log at `%LOCALAPPDATA%\Achilles\Saved\Logs\Achilles.log` will show what happened.
- Still unknown until someone plays with it:
  - how the borrowed-type units behave and are balanced, since they use horde stats;
  - how well the developers' editor works in the retail build.

## Rebuilding (after a game update, or to change numbers)

You need Python 3. Run these from the game folder:

```powershell
python _NightmarePOC\tools\build_mod.py [settings code]
python _NightmarePOC\tools\validate.py [settings code]
```

`build_mod.py` only reads the game's own pak and writes a new `dist\NightmarePOC_P.pak`, with the default settings or the `NP1-` code given. The defaults are in tables at the top of the script: `VOLATIST_UNITS`, `BORROWED_UNITS` and `DEFAULT_HEROES`. Give `validate.py` the same code. `validate.py` fails if two command-card buttons collide or a stat change doesn't land. If a game update changes the shape of an asset the script patches, the build stops with an error instead of writing a broken pak.

## Files

| File | Purpose |
|---|---|
| `dist\NightmarePOC_P.pak` | The mod |
| `dist\validate.log` | Output of the last validation run |
| `tools\build_mod.py` | All the changes, in one script |
| `tools\validate.py` | Checks on the built pak |
| `tools\ue_pkg.py` | UE 4.26 cooked-asset reader/writer |
| `tools\kismet.py` | Blueprint bytecode disassembler |
| `tools\menu_credit.py` | The main-menu credit; the same file as Arcade Endless's |
| `tools\pak.py` | Pak (v11) reader/writer |
| `tools\exe_patches.py` | The resource hotkey's and map seeds' exe patches (`python exe_patches.py status`, `hotkey-on`, `hotkey-off`, `seeds-on`, `seeds-off`, `restore`), and Arcade Endless's; the same file as Arcade Endless's |
