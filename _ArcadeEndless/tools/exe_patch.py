"""Arcade Endless exe patch: lets the game generate pester waves past day 44.

  python exe_patch.py status | install | remove | restore

__generate_pester_waves() only creates waves for days 1..N-1, where N comes from
world_time_of_day::get_total_game_duration(), a tail call to FLevelData::get_game_duration(), which returns
a hardcoded 45. Nothing else calls get_total_game_duration, so the patch changes only how many days of
pester waves exist; the score keeps using the original 45.

  original  48 8B 49 10 48 81 | C1 00 01 00 00 E9 rel32   mov rcx,[rcx+10h]; add rcx,100h; jmp get_game_duration
  patched   B8 xx xx 00 00 C3 | C1 00 01 00 00 E9 rel32   mov eax,PATCH_DAYS; ret  (the rest is never reached)

The site is found by pattern (the jmp must land on get_game_duration's body), so the script refuses to touch
an exe it doesn't recognise. Only 6 bytes change and `remove` writes the original 6 back. Before patching an exe that
has no patch at all, `install` also saves a full copy next to it (EXE + BACKUP_SUFFIX, refreshed after a game update),
and `restore` copies that back over the exe. The site search and the backup rules live in exe_patches.py, shared with
NightmarePOC, whose resource hotkey and map seeds are the other exe patches: the backup is never a patched exe.

The day/seconds curves the clock runs on cover days 0-199 (and wrap after 198), so PATCH_DAYS stays below that.
Multiplayer runs a lockstep simulation: every player needs the same exe state (all patched, or none).
"""
import hashlib
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import exe_patches as xp  # noqa: E402
import home  # noqa: E402

GAME = home.GAME
EXE = xp.exe_path(GAME)
MOD_PAK = os.path.join(GAME, "Achilles", "Content", "Paks", "~mods", "ArcadeEndless_P.pak")
BACKUP_SUFFIX = xp.BACKUP_SUFFIX  # the original exe is saved as EXE + this by install


def backup_path():
    return xp.backup_path(EXE)

VANILLA_DAYS = xp.VANILLA_DAYS
PATCH_DAYS = 190
MAX_DAYS = 198
SITE_HEAD = xp.DAYS_HEAD  # the 6 bytes the patch replaces


def find_site(data):
    """(file offset, current days or None if vanilla). Raises if the exe isn't one this patch knows."""
    try:
        return xp.days_site(data)
    except xp.PatchError as ex:
        raise SystemExit(f"{EXE}: {ex}. Nothing changed.")


def match_code(path):
    """First 8 hex digits of a pak's SHA-256: multiplayer players compare these to know they have the same pak."""
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:8]


def write_head(site, head):
    try:
        with open(EXE, "r+b") as f:
            f.seek(site)
            f.write(head)
    except PermissionError:
        raise SystemExit("Can't write the exe. Close the game (and anything holding the file) and run this again.")
    with open(EXE, "rb") as f:
        f.seek(site)
        assert f.read(6) == head, "write did not stick"


def backup_state(exe_data=None):
    """'none', 'matches' (the backup is the exe as it is now) or 'other' (an original exe, but not this one)."""
    return xp.backup_state(EXE, exe_data)


def save_backup(data):
    """Keep a full copy of this exe (which has no patch) in backup_path(); replaces a copy of an older game version."""
    try:
        return xp.save_backup(EXE, data)
    except xp.PatchError as ex:
        raise SystemExit(f"{ex}. Nothing changed.")


def restore_backup():
    try:
        xp.restore_backup(EXE)
    except xp.PatchError as ex:
        raise SystemExit(f"{ex}.")


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "status"
    if cmd == "restore":
        if not os.path.exists(backup_path()):
            raise SystemExit(f"No backup at {backup_path()}; nothing to restore. Steam's 'Verify integrity of game files' "
                             "also puts the original exe back.")
        restore_backup()
        print(f"Restored the original exe from {backup_path()}.")
        return 0
    data = open(EXE, "rb").read()
    site, days = find_site(data)
    state = f"vanilla ({VANILLA_DAYS} days of waves)" if days is None else f"patched ({days} days of waves)"
    if cmd == "status":
        print(f"{EXE}\n  {state}, patch site at file offset {site:#x}")
        print(f"  ArcadeEndless_P.pak: {'match code ' + match_code(MOD_PAK) if os.path.exists(MOD_PAK) else 'not in ~mods'}")
        print(f"  NightmarePOC resource hotkey patch: {'on' if xp.hotkey_on(data) else 'off'}")
        print(f"  NightmarePOC map seeds patch: {'on' if xp.seeds_on(data) else 'off'}")
        print(f"  backup: " + {"none": "none yet (install makes one)", "matches": f"{backup_path()} (same as the exe now)",
                               "other": f"{backup_path()}"}[backup_state(data)])
    elif cmd == "install":
        assert VANILLA_DAYS < PATCH_DAYS <= MAX_DAYS
        if days == PATCH_DAYS:
            print(f"Already {state}.")
            return 0
        if xp.is_original(data) and save_backup(data):
            print(f"Saved a backup of the original exe: {backup_path()}")
        write_head(site, b"\xB8" + struct.pack("<I", PATCH_DAYS) + b"\xC3")
        print(f"Patched: {state} -> patched ({PATCH_DAYS} days of waves).")
    elif cmd == "remove":
        if days is None:
            print(f"Already {state}.")
            return 0
        write_head(site, SITE_HEAD)
        print(f"Restored: {state} -> vanilla ({VANILLA_DAYS} days of waves).")
        now = open(EXE, "rb").read()
        if xp.hotkey_on(now) or xp.seeds_on(now):
            print("  NightmarePOC's own exe patches are still on; NightmarePOC's own Remove takes them out.")
        elif backup_state(now) == "other":
            print(f"  Note: the exe isn't identical to {backup_path()} (that backup may be from an older game version).")
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
