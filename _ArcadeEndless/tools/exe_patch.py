"""Arcade Endless exe patch: lets the game generate pester waves past day 44.

  python exe_patch.py status | install | remove | restore

__generate_pester_waves() only creates waves for days 1..N-1, where N comes from
world_time_of_day::get_total_game_duration(), a tail call to FLevelData::get_game_duration(), which returns
a hardcoded 45. Nothing else calls get_total_game_duration, so the patch changes only how many days of
pester waves exist; the score keeps using the original 45.

  original  48 8B 49 10 48 81 | C1 00 01 00 00 E9 rel32   mov rcx,[rcx+10h]; add rcx,100h; jmp get_game_duration
  patched   B8 xx xx 00 00 C3 | C1 00 01 00 00 E9 rel32   mov eax,PATCH_DAYS; ret  (the rest is never reached)

The site is found by pattern (the jmp must land on get_game_duration's body), so the script refuses to touch
an exe it doesn't recognise. Only 6 bytes change and `remove` writes the original 6 back. Before patching an
unpatched exe, `install` also saves a full copy next to it (EXE + BACKUP_SUFFIX, refreshed after a game update), and
`restore` copies that back over the exe.

The day/seconds curves the clock runs on cover days 0-199 (and wrap after 198), so PATCH_DAYS stays below that.
Multiplayer runs a lockstep simulation: every player needs the same exe state (all patched, or none).
"""
import hashlib
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import home  # noqa: E402

GAME = home.GAME
EXE = os.path.join(GAME, "Achilles", "Binaries", "Win64", "Achilles-Win64-Shipping.exe")
MOD_PAK = os.path.join(GAME, "Achilles", "Content", "Paks", "~mods", "ArcadeEndless_P.pak")
BACKUP_SUFFIX = ".arcade-backup"  # the unpatched exe is saved as EXE + this by install


def backup_path():
    return EXE + BACKUP_SUFFIX

VANILLA_DAYS = 45
PATCH_DAYS = 190
MAX_DAYS = 198

SITE_HEAD = bytes.fromhex("488b49104881")                      # the 6 bytes the patch replaces
SITE_TAIL = bytes.fromhex("c100010000e9")                      # kept as-is, followed by the jmp rel32
TARGET = (bytes.fromhex("f30f2d05"), bytes.fromhex("d1f8c3"))  # cvtss2si eax,[rip+x]; sar eax,1; ret
SITE_LEN = 16


def _jmp_lands_on_target(data, site):
    (rel,) = struct.unpack_from("<i", data, site + 12)
    t = site + SITE_LEN + rel  # same .text section, so file offsets move with RVAs
    return 0 <= t < len(data) - 11 and data[t:t + 4] == TARGET[0] and data[t + 8:t + 11] == TARGET[1]


def find_site(data):
    """(file offset, current days or None if vanilla). Raises if the exe isn't one this patch knows."""
    sites = []
    i = data.find(SITE_TAIL)
    while i != -1:
        site = i - 6
        if site >= 0 and _jmp_lands_on_target(data, site):
            head = data[site:site + 6]
            if head == SITE_HEAD:
                sites.append((site, None))
            elif head[0] == 0xB8 and head[5] == 0xC3:
                sites.append((site, struct.unpack_from("<I", head, 1)[0]))
        i = data.find(SITE_TAIL, i + 1)
    if len(sites) != 1:
        raise SystemExit(f"Patch site found {len(sites)} times in {EXE}; this game version isn't supported. Nothing changed.")
    return sites[0]


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
    """'none', 'matches' (the backup is the exe as it is now) or 'other' (an unpatched exe, but not this one)."""
    if not os.path.exists(backup_path()):
        return "none"
    with open(backup_path(), "rb") as f:
        saved = f.read()
    return "matches" if exe_data is not None and saved == exe_data else "other"


def save_backup(data):
    """Keep a full copy of this (unpatched) exe in backup_path(); replaces a copy of an older game version."""
    if backup_state(data) == "matches":
        return False
    tmp = backup_path() + ".tmp"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, backup_path())
    return True


def restore_backup():
    with open(backup_path(), "rb") as f:
        saved = f.read()
    try:
        _, days = find_site(saved)
    except SystemExit:
        days = "unknown"
    if days is not None:
        raise SystemExit(f"{backup_path()} isn't an unpatched game exe; not restoring it.")
    try:
        with open(EXE, "wb") as f:
            f.write(saved)
    except PermissionError:
        raise SystemExit("Can't write the exe. Close the game (and anything holding the file) and run this again.")


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
        print(f"  backup: " + {"none": "none yet (install makes one)", "matches": f"{backup_path()} (same as the exe now)",
                               "other": f"{backup_path()}"}[backup_state(data)])
    elif cmd == "install":
        assert VANILLA_DAYS < PATCH_DAYS <= MAX_DAYS
        if days == PATCH_DAYS:
            print(f"Already {state}.")
            return 0
        if days is None and save_backup(data):
            print(f"Saved a backup of the original exe: {backup_path()}")
        write_head(site, b"\xB8" + struct.pack("<I", PATCH_DAYS) + b"\xC3")
        print(f"Patched: {state} -> patched ({PATCH_DAYS} days of waves).")
    elif cmd == "remove":
        if days is None:
            print(f"Already {state}.")
            return 0
        write_head(site, SITE_HEAD)
        print(f"Restored: {state} -> vanilla ({VANILLA_DAYS} days of waves).")
        if backup_state(open(EXE, "rb").read()) == "other":
            print(f"  Note: the exe isn't identical to {backup_path()} (that backup may be from an older game version).")
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
