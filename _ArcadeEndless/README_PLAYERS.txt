ARCADE ENDLESS + NIGHTMAREPOC
Mods for Age of Darkness: Final Stand, created by Lunar (76561198073513480)
======================================================================

WHAT YOU GET

Arcade Endless
  Survival and multiplayer runs go on far longer: the Final Night moves to
  day 181 by default, and every night gets harder. Pester waves grow each
  night, surge nights bring double the horde, and Death Nights are bigger,
  higher-tier and bring elite bosses. You pick how hard it is and can see
  (and edit) what every single night will bring before you play.

NightmarePOC (optional, separate)
  - The Volatists can train 8 Nightmares (Crawlers up to Crushers) at the
    Barracks and Siege Workshop.
  - Customise what each Nightmare costs, and each hero's stats.
  - The main menu's hidden map/mission Editor button comes back (the
    developers' own tool, rough edges included).
  This one is experimental: it hasn't had much play yet.

Both are installed, changed and removed from one program, ArcadeEndless.exe.
It builds the mods from your own game files, so nothing is downloaded. The
campaign isn't touched.


INSTALL

1. Close the game.
2. Open the game folder: in Steam, right-click Age of Darkness: Final Stand
   > Manage > Browse local files.
3. Extract this zip into that folder. You should end up with:
      ...\Age of Darkness - Final Stand\_ArcadeEndless\ArcadeEndless.exe
   (It must be inside the game folder, or it can't find the game.)
4. Run ArcadeEndless.exe. It isn't code-signed, so Windows may say "Windows
   protected your PC": click More info, then Run anyway.
5. Pick a preset (or your own settings) and press Build & install.
6. Optional: open the NightmarePOC tab, press Customise... if you want to
   change costs or hero stats, then Install NightmarePOC.
7. Start a NEW game. Settings apply to new games only; a save keeps the
   waves it started with.

The app puts its mod files in Achilles\Content\Paks\~mods. Arcade Endless
also changes 6 bytes in the game exe (so the game prepares waves for the
longer run). Before changing it, the app saves a full copy of the original
exe next to it, as Achilles-Win64-Shipping.exe.arcade-backup.


MULTIPLAYER

Every player needs the same mods with the same settings, or the match will
fall out of sync.
1. The host picks settings, installs, and copies the settings code
   (Arcade Endless: on the left, starts with AE2-. NightmarePOC: in its
   Customise window, starts with NP1-).
2. Each friend installs the app the same way, pastes the code, presses
   Load, then installs.
3. Compare the match codes at the top right of the app: they must be the
   same for everyone.

The exe patch alone can desync a normal (unmodded) multiplayer match with
players who don't have it. Press Remove before playing vanilla multiplayer.


REMOVE

Use the app: Remove (Arcade Endless) and the NightmarePOC tab's Remove.
That deletes the mod files and puts the original exe back. Remove mods
between matches, not in the middle of a saved game.
Without the app: delete the two _P.pak files in Achilles\Content\Paks\~mods,
then in Steam use Properties > Installed Files > Verify integrity of game
files to restore the exe.


AFTER A GAME UPDATE

A Steam update puts the original game exe back. Run ArcadeEndless.exe and
press Build & install again (and Install NightmarePOC, if you use it). If an
update changed the game's data too much, the app's checks stop and it
installs nothing rather than a broken mod.
