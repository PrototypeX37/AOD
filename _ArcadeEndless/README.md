# Arcade Endless: Age of Darkness: Final Stand mod

Survival runs no longer end around day 30. The Final Night moves to **day 181** by default, and the run keeps getting harder the whole way:

- Every normal night brings a bigger pester wave than the last.
- Surge nights hit with double the horde and triple the Crushers.
- Each Death Night is bigger, higher-tier and brings elite bosses.

You choose how hard. In-game days run about 6½ minutes, so day 181 is roughly 20 hours of play. Every day number in this README and the app is what the game's own day counter shows.

The mod has two parts, and you need both:

| Part | What it does |
|---|---|
| `ArcadeEndless_P.pak` in `Paks\~mods` | All the wave data, built from your settings. It doesn't modify any game files. |
| The exe patch | Changes 6 bytes in the game exe. The game only prepares pester waves up to day 45 (its length is hard-coded), and this raises that to day 190. Without it, nights after day 45 have no pester waves. |

Survival and multiplayer both change. The campaign is untouched, because the mod uses its own copies of the curves. It works alongside NightmarePOC.

**Main-menu credit.** The main menu shows "Mod created by Lunar (76561198073513480)" above the news panel at the bottom right, where the game's old Early Access title used to be. Arcade Endless and NightmarePOC both ship this credit, so both mods replace the main menu's file (`Menu_UI`). That's the only file they share. With both installed, the game uses NightmarePOC's copy: it has the same credit plus NightmarePOC's Editor button. Unreal picks the copy from the pak whose name sorts last, so keep both paks in `Paks\~mods`.

## The app: pick your settings and install

Double-click **`ArcadeEndless.exe`**. It's a normal Windows program with Python packed inside, so it needs nothing installed.

- **Location:** it has to sit inside the game folder. `_ArcadeEndless\` is where it lives, but it also works dropped straight into `...\steamapps\common\Age of Darkness - Final Stand\`. Anywhere else, it says it can't find the game.
- **Windows warning:** the exe isn't code-signed, so the first time you run it Windows SmartScreen may say "Windows protected your PC". Click **More info**, then **Run anyway**. Some antivirus programs are also wary of unsigned packed Python programs.
- **Running from Python:** `ArcadeEndless.pyw` is the same app as Python source. Double-click it instead if you have Python 3 installed.

The app is dressed in the game's own look. The logo, the Nightmare horde banner and the Cinzel/Jost fonts are read from your installed game when it starts. Nothing is downloaded, and none of the game's art is packed into the mod or the exe; the exe's own icon is drawn by the build script. When running from Python without the Pillow library, the app skips the pictures but still works.

1. **Choose how hard it is:** pick a preset, or change the sliders on the **Difficulty**, **Unit mix** and **Limits** tabs (the preset switches to *Custom*).
2. **Look at the "Every night" table.** It shows every night from day 1 to the Final Night for the mode and difficulty you pick, using the game's own difficulty names:
   - whether it's a pester night, a surge, a Death Night or the quiet night after one;
   - how many of each unit come;
   - the tier, and which elite bosses.

   It updates as you change anything. The numbers are exactly what the game will spawn at that difficulty, including its pester multiplier (see "How the game scales pester waves" below). That's checked by rerunning the game's own wave maths.
3. **Edit any night (optional).** Double-click a unit's count and type a new number, as described below.
4. **Close the game and press "Build & install".** The app:
   - builds the pak and runs every validation check, installing nothing if one fails;
   - copies the pak into `Paks\~mods`;
   - saves a **full backup of the original exe** (the first time), then patches the exe;
   - shows a **match code**.
5. **"Remove"** deletes the pak and puts the original 6 bytes back in the exe. If that ever fails (for example, after a game update changed the exe), it offers to copy the full backup back instead.
6. **NightmarePOC tab (optional).** NightmarePOC is a second mod by the same author:
   - the Volatists can train Nightmares;
   - heroes can be tuned;
   - the hidden map-editor button comes back.

   The tab explains it and installs or removes it on its own, separate from Arcade Endless. **Customise** sets each Nightmare's cost (gold, wood, stone, iron, food, population, train time, upkeep) and each hero's stats, shown as the hero's real values. It's built from your game's files like Arcade's pak, and its status shows in the banner. Details in `_NightmarePOC\README.md`.

The banner and the bottom line show what's installed, whether it matches the settings on screen, and whether an exe backup exists. When you reopen the app, it loads the settings you installed.

### Presets

| Preset | Pester waves | Unit mix: Festerlings, Wraiths, Spitters, Crushers | Surge nights | Death Night growth | Higher tiers | Elites | Biggest pester night (Normal / Veteran) |
|---|---|---|---|---|---|---|---|
| Tough | ×0.6 | ×0.6 | every 7th night, ×1.5 | ×0.5 | off | ×0.5 | about 1,700 / 2,100 |
| **Hard** (default) | ×1 | ×1 | every 5th night, ×2 | ×1 | on | ×1 | about 4,000 / 5,000 |
| Brutal | ×1.5 | ×1.5 | every 4th night, ×2.5 | ×1.5 | on | ×2 | about 4,800 / 6,000 (the cap) |
| Apocalypse | ×2 | ×2.5 | every 3rd night, ×3 | ×2 | on | ×3 | about 4,800 / 6,000; late normal nights hit the cap too |

### Settings

| Setting | Range | What it does |
|---|---|---|
| Final Night on day | 61-186 | When the run ends. Death Nights stay on the days below. |
| Pester wave size | ×0.25-4 | Every pester night's unit count |
| Surge night size | ×1-5 | Surge nights' size. Crushers get 1.5× this. |
| Surge night every N nights | 0-10 | Surges from day 21 on; 0 turns them off |
| Death Night growth | ×0-3 | How much bigger later Death Nights get. 0 keeps base-game sizes; 1 is ×1 to ×2 across Death Nights 1-5. |
| Higher tiers on later Death Nights | on/off | Off keeps the base game's tiers |
| Elite bosses on Death Nights | ×0-5 | 0 means no added elites |
| **Unit mix** tab | ×0-5 per unit | How many Crawlers, Axemen, Spearmen, Festerlings, Wraiths, Spitters and Crushers come on pester and surge nights. 0 means none of that unit. "All x1" resets it. |
| **Limits** tab: Death Night cap | 1,000-100,000 | Most units in one Death Night or the Final Night. Default 21,951, the game's own biggest night. |
| **Limits** tab: pester night cap | 100-100,000 | Most units in one pester or surge night. Default 6,000, because pester waves seem to spawn all at once. |

A night over its cap is scaled down to fit, edits included, and the table marks it "(capped)".

**Above the game's limits.** You can raise both caps past their defaults. A big red warning bar then appears across the app, because the game has never been run with nights that big: expect heavy lag, and it may freeze or crash. "Build & install" asks you to confirm first. Raised caps are untested, so use them at your own risk.

The game's own difficulty choices still apply on top of these settings: Custom difficulty's Duration, Death Night and Enemy Density, and the Hardships.

### How the game scales pester waves

The game multiplies every pester night by a difficulty multiplier and **rounds each unit's count down**. The multiplier comes from your **Death Night** difficulty; in a normal (non-custom) game that's just the difficulty you pick:

| Difficulty | Forgiving | Easy | Normal | Veteran | Horrific | Nightmare |
|---|---|---|---|---|---|---|
| Pester multiplier | 0.2× | 0.5× | 0.8× | 1× | 1.2× | 1.5× |

So small numbers can vanish. On Forgiving, anything below 5 of a unit rounds to 0; on Normal, a single unit does. The app's table already includes this, so pick the difficulty you'll play.

### Editing a single night

Double-click any unit's count in the "Every night" table, type a number and press Enter:

- **Edited cells** show a `*`. Clear the box and press Enter to undo one edit.
- **Right-click** a row to reset that cell, that night, or all edits. The button above the table also resets them all.
- **Pester and surge nights:** an edit sets how many of that unit spawn that day at the difficulty shown. The app stores what the game needs before its multiplier: 1 Crusher on Forgiving is stored as 5, because 5 × 0.2 = 1. The same edit gives proportionally more or fewer units on other difficulties, and applies to Survival and multiplayer alike. On Nightmare (1.5×) a few exact counts can't happen, and the table then shows the nearest one above.
- **Death Nights and the Final Night:** an edit sets that unit's total for the mode and difficulty shown in the table. You can add a unit a night doesn't normally have; Crushers on Death Night 1 get their own spawn entry, at that night's tier. If a unit has several spawn entries (Festerlings often do), your number is spread across them.
- **Quiet nights** can't be edited. The game sends no wave the night after a Death Night.
- **Settings code:** every edit is saved in it, so a friend who loads your code gets exactly the same nights.

## What the Hard preset does

### Pester waves grow every day, with surge nights
Pester waves come on every night except the first day, a Death Night or the Final Night, and the night after one. Each unit type starts on its own day, then grows every night and never shrinks. The numbers below are for Veteran (1×); Normal gets 80% of them, rounded down:

| Day | 2 | 12 | 22 | 42 | 62 | 82 | 102 | 127 | 152 | 177 |
|---|---|---|---|---|---|---|---|---|---|---|
| Nightmares on a normal night | 8 | 52 | 111 | 258 | 454 | 695 | 983 | 1,410 | 1,909 | 2,481 |
| Of which Crushers | 0 | 0 | 2 | 5 | 11 | 18 | 28 | 43 | 60 | 81 |

- **Unit types:** Crawlers come from day 2, Axemen from day 4, Spearmen from day 5, Festerlings from day 9, Wraiths from day 11, and Spitters and Crushers from day 13. Over time the mix shifts toward the heavy units.
- **Surge nights:** every 5th night from day 21 (days 21, 26, 31 and so on) brings 2× the horde and 3× the Crushers. By about day 176 that's around 5,000 Nightmares on Veteran (4,000 on Normal), including about 240 Crushers. A surge doesn't happen if a Death Night falls on that night or the night before.
- **For comparison:** in the base game, pester nights stay under about 100 units before the run ends.

Pester waves always spawn the basic (tier 1) versions of these seven units. That's hard-coded in the game, so the elites and higher tiers come from the Death Nights.

### Death Nights come later and hit much harder
| Difficulty | Survival Death Nights | Multiplayer Death Nights | Final Night |
|---|---|---|---|
| Forgiving | 8, 17, 28, 41, 56 | 9, 20, 36 | 181 |
| Easy | 8, 17, 28, 41, 56 | 8, 19, 34 | 181 |
| Normal | 7, 15, 25, 37, 51 | 7, 17, 31 | 181 |
| Veteran | 7, 15, 25, 37, 51 | 7, 16, 30 | 181 |
| Horrific | 6, 13, 22, 33, 46 | 7, 16, 29 | 181 |
| Nightmare | 6, 13, 22, 33, 46 | 6, 15, 28 | 181 |

For comparison, the base Final Night falls on day 24-34 in Survival and day 16-24 in multiplayer.

Each Death Night gets three upgrades:

1. **More units.** In Survival the five Death Nights get ×1, ×1.25, ×1.5, ×1.75 and ×2; in multiplayer the three get ×1, ×1.5 and ×2. The Final Night gets ×2 in Survival and ×4 in multiplayer.
2. **Stronger tiers.** Horde units come in tiers with more health, armour and speed. Tier 3 Crushers have 3,200 health and 1,150 armour, compared with 1,200 and 340 at tier 1. Survival Death Night 2 uses at least tier 2, and Death Nights 3-5 and the Final Night use tier 3. The base game holds tier 3 back for Death Night 5. Tier 3 is the top, because normal horde units have no stats above tier 4 and the game never uses tier 4.
3. **Elite bosses for everyone.** In the base game, elites only appear with the Hardship option. Now they join the regular waves:

| Survival night | Elites added (Normal; fewer on easier difficulties, more on harder ones) |
|---|---|
| Death Night 2 | 1 elite Crawler |
| Death Night 3 | 2 elite Axemen, 1 elite Crusher |
| Death Night 4 | 3 elite Crushers, 2 elite Spitters, 2 elite Wraiths |
| Death Night 5 | 5 elite Crushers, 3 elite Spitters, 3 elite Wraiths, 3 elite Spearmen |
| Final Night | 10 elite Crushers, 6 elite Spitters, 6 elite Wraiths, 6 elite Axemen, 3 elite Festerlings |

Multiplayer's three Death Nights get the elites of Survival's Death Nights 1, 3 and 5, and its Final Night gets the same elites as Survival's. An elite Crusher has 5,000 health, 1,500 armour and 175 damage. Hardship's own bosses are unchanged.

## Multiplayer

The game runs a lockstep simulation, so every player needs **the same pak and the exe patch**. There are two ways to get there.

**Easiest: everyone uses the app.**

1. The host picks settings, installs, and copies the **settings code**.
2. Friends drop `ArcadeEndless.exe` into their game folder, paste the code, press **Load**, then **Build & install**.
3. The same code builds a byte-identical pak, so every player's **match code** comes out the same.

**Without the app:**

1. The host installs and notes the match code.
2. The host sends friends their `Achilles\Content\Paks\~mods\ArcadeEndless_P.pak`.
3. Each friend copies it into their own `Paks\~mods` and patches the exe with the PowerShell script:

```powershell
powershell -ExecutionPolicy Bypass -File "_ArcadeEndless\tools\exe_patch.ps1" install
powershell -ExecutionPolicy Bypass -File "_ArcadeEndless\tools\exe_patch.ps1" status
```

`status` prints the installed pak's match code, and it must be the same as the host's. `install` also saves each friend a backup of their original exe first.

The exe patch changes how many waves the game prepares at the start of every match, even without the pak. A patched player and an unpatched player will most likely desync even in a vanilla match. **Remove the patch before playing vanilla multiplayer with unpatched friends.**

## Install or remove without the app

Use these if you'd rather not use the app. Run them in PowerShell from the game folder (`...\steamapps\common\Age of Darkness - Final Stand`), with the game closed.

Install. This uses the pak in `dist`, the last one built:

```powershell
New-Item -ItemType Directory -Force "Achilles\Content\Paks\~mods" | Out-Null
Copy-Item "_ArcadeEndless\dist\ArcadeEndless_P.pak" "Achilles\Content\Paks\~mods\"
powershell -ExecutionPolicy Bypass -File "_ArcadeEndless\tools\exe_patch.ps1" install
```

Remove:

```powershell
Remove-Item "Achilles\Content\Paks\~mods\ArcadeEndless_P.pak"
powershell -ExecutionPolicy Bypass -File "_ArcadeEndless\tools\exe_patch.ps1" remove
```

Both patch scripts (`exe_patch.ps1`, and `exe_patch.py` for Python) look for the exact code they patch and refuse to touch an exe they don't recognise.

- **`install`:** before patching an unpatched exe, saves a full copy next to it as `Achilles\Binaries\Win64\Achilles-Win64-Shipping.exe.arcade-backup` (about 90 MB). After a game update it saves a fresh one.
- **`remove`:** writes the original 6 bytes back, leaving the exe byte-identical to the original.
- **`restore`:** copies the full backup back over the exe. It first checks that the backup is an unpatched game exe. Use it if `remove` ever can't recognise the exe:

```powershell
powershell -ExecutionPolicy Bypass -File "_ArcadeEndless\tools\exe_patch.ps1" restore
```

Remove the mod between runs, not in the middle of a saved game.

**Game updates:** a Steam update or "Verify integrity of game files" puts the original exe back. Run `status` after an update, and install again if needed.

## Status

- **Validation:** `tools\validate_endless.py` passes for every preset, and for settings at both ends of every slider. The log for Hard is in `dist\validate.log`. It checks:
  - pak structure, and that every asset round-trips;
  - that only the intended parts of the two wave-constant assets change;
  - that the campaign's assets aren't in the pak;
  - that it shares only the main menu with NightmarePOC, that NightmarePOC's copy has the same credit, and that NightmarePOC's copy wins;
  - that the main menu changes only the credit;
  - the Death Night days on every difficulty;
  - every Death Night and Final Night count, tier and elite against the settings, under the cap;
  - every edit, which must be exact unless its night is capped, plus the new spawn entries edits add;
  - for every day 1-189, the game's own pester-curve maths, rerun (its 8-samples-per-key fixed-point sampling and looping lookup), so each night's count matches the table exactly.

  It also passed for a test build with many edits, including one that pushes Death Night 5 on Nightmare difficulty over the cap.
- **The app:** its self-test (`ArcadeEndless.exe --selftest`, or the `.pyw`) fills the table for every preset, mode and difficulty, and checks that edits and the unit mix show up in the right cells. Double-click editing was also driven through the real editor.
- **The packed exe:**
  - it passes the same self-test;
  - its window was opened, screenshotted and closed;
  - it finds the game from `_ArcadeEndless\`, from the game folder, and from two folders deep, and correctly says it can't find the game anywhere else.
- **Exe backup:** tested on copies of the exe with both scripts and through the app:
  - install saved a backup identical to the original;
  - a second install left the backup alone;
  - with the patch site deliberately corrupted, `remove` refused and `restore` brought back an exact original.
- **Raised caps:** a 60,000/20,000 build with a 90,000-Crawler edit passes validation, with warnings (that night lands at 59,996, under its cap). "Build & install", reopening and "Remove" were tested end to end against a copy of the exe and a scratch `~mods` folder. Remove restored the exe exactly.
- **Not yet tested in-game.** Things to watch:
  - frame rate on big pester nights, especially surges near the 6,000 cap;
  - elite bosses in the regular Death Night waves, which the base game only spawns through Hardship;
  - that the Final Night still ends the run with a win;
  - in multiplayer, the map entries for Death Nights 4 and 5. They have no waves and sit 4 and 2 days before the Final Night, where the base game also puts them.

  If something breaks, press Remove. The game's log is at `%LOCALAPPDATA%\Achilles\Saved\Logs\Achilles.log`.

## How it works (for tinkering)

The settings scale the Hard tables at the top of `tools\build_endless.py`:

| Table | Controls |
|---|---|
| `PESTER` | Start day plus base, linear and quadratic growth per unit type |
| `DEATH_NIGHT_DAYS` | Death Night days per difficulty |
| `HARD_DEATH_NIGHT_MULT`, `HARD_FINAL_NIGHT_MULT` | Death Night and Final Night size multipliers |
| `HARD_DEATH_NIGHT_TIER`, `HARD_FINAL_NIGHT_TIER` | Minimum horde tier per night |
| `HARD_ELITES`, `HARD_FINAL_ELITES` | Elite bosses added to each night |
| `PRESETS` | The four presets, as `Settings` (which also hold the unit mix and edits) |
| `PESTER_NIGHT_CAP`, `BASE_NIGHT_CAP` | The default caps (the app's Limits tab can raise them) |

Each command line tool takes a preset name or a settings code. Run them from the game folder:

```powershell
python _ArcadeEndless\tools\build_endless.py Brutal
python _ArcadeEndless\tools\validate_endless.py Brutal
python _ArcadeEndless\tools\schedule.py Brutal Survival medium > nights.csv
```

After changing the app or the tools, rebuild the exe (this needs `pip install pyinstaller pillow`):

```powershell
python _ArcadeEndless\tools\make_exe.py
python _ArcadeEndless\tools\make_release.py
```

`make_release.py` packs the zip players get, `release\ArcadeEndless-<version>.zip`. It holds only `ArcadeEndless.exe` and the player guide (`README_PLAYERS.txt`, as `README.txt`), in an `_ArcadeEndless` folder so it extracts straight into the game folder. No pak goes in: the exe builds both mods from each player's own game files. It refuses an exe older than the code.

Limits found in the exe:

- **Day limit.** The day clock runs on day/seconds curves that cover the game's days 0-199 (counter Day 1-200) and wrap after that. So the patch prepares 190 days, and the Final Night can be at most day 186.
- **Day numbers.** Internally the game counts days from 0; its day counter shows that number + 1. The game never makes a pester wave for its first day.
- **Pester multiplier.** When you press Play, the game looks your Death Night difficulty up in `DifficultyModifierConstants.spawn_multipliers_for_density_setting` and stores it as `harassment_wave_multiplier`. Every pester count is multiplied by it and rounded down; the builder reads the table from the game, and the validator checks the app's numbers against that maths for every difficulty.
- **Death Night count.** Death Nights are a fixed list: 5 in Survival, 3 in multiplayer, plus the Final Night. More than that would need code changes, which is why surge nights carry the late game.
- **Pester waves.** They only spawn the seven basic unit types at tier 1; `__generate_pester_waves` hard-codes the tier.
- **Tiers.** Normal horde units define stats for tiers 1-4 only; tier 5 and up have 0 health.
- **Death Night days.** The game normally rebuilds the Death Night days from `DT_WaveDays` when it loads. That table always puts the Final Night 2 days after Death Night 5, so the mod clears the wave constants' link to the table and stores the days directly.
- **Settings menu.** The game reads its difficulty settings in native code, so a pak can't add new options to the in-game menu. That's why the settings live in the app.

## Files

| File | Purpose |
|---|---|
| `ArcadeEndless.exe` | The app, packed into one program |
| `ArcadeEndless.pyw` | The same app as Python source |
| `tools\make_exe.py` | Builds `ArcadeEndless.exe` with PyInstaller. It draws the icon and writes the credit into the exe's file details (Properties > Details). It works while the app is open: the open copy is renamed `ArcadeEndless.exe.old`, which you can delete once the app is closed. |
| `tools\make_release.py`, `README_PLAYERS.txt` | The players' zip, `release\ArcadeEndless-<version>.zip`, and the guide inside it |
| `tools\menu_credit.py` | The main-menu credit; the same file as NightmarePOC's |
| `tools\nightmare.py` | The NightmarePOC tab's link to NightmarePOC's own builder and validator (`_NightmarePOC\tools`, packed into the exe) |
| `dist\NightmarePOC_P.pak`, `dist\nightmare_settings.txt` | The last NightmarePOC the app built, and the settings and match code it installed |
| `tools\home.py` | Finds the game folder and the mod's folder, from source or from the exe |
| `tools\look.py`, `tools\game_art.py` | The app's look; reads the logo, banner art and fonts from the installed game |
| `dist\cache\` | The game's fonts, extracted for the app (rebuilt if deleted) |
| `dist\ArcadeEndless_P.pak` | The last pak built |
| `dist\validate.log` | Output of the last command-line validation run |
| `dist\installed_settings.txt` | Written by the app: the installed settings code and match code |
| `tools\exe_patch.py` / `tools\exe_patch.ps1` | The exe patch: `status`, `install` (with backup), `remove`, `restore` |
| `...\Win64\Achilles-Win64-Shipping.exe.arcade-backup` | The original exe, saved by the first install |
| `tools\build_endless.py` | Builds the pak from the game's own pak (read-only), for any settings |
| `tools\validate_endless.py` | Checks on a built pak |
| `tools\schedule.py` | What every night brings (the app's table, or CSV, with edited and capped markers) |
| `tools\ue_pkg.py`, `tools\pak.py` | UE 4.26 asset and pak reader/writer (same as NightmarePOC's) |
