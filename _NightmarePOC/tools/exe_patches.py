"""The game-exe patches, in one place so the two mods never trip over each other. Shared by Arcade Endless and
NightmarePOC: keep both copies (each mod's tools/exe_patches.py) identical. Either works without the other.

  python exe_patches.py status | hotkey-on | hotkey-off | seeds-on | seeds-off | restore

  days    Arcade Endless: pester waves for 190 days instead of 45. 6 bytes, found by pattern.
  hotkey  NightmarePOC: Numpad + gives the player who presses it resources, synced in multiplayer. Four sites, each
          checked byte for byte before anything is written, so another game version is refused.
  seeds   NightmarePOC: any map seed in multiplayer (the host names the game "seed_<text>"). Three sites, checked the
          same way.

Before any patch first changes the exe, a full copy is saved beside it (exe + BACKUP_SUFFIX), and only while the
exe has none of them, so the backup is always the original game. `restore` copies it back.

How the hotkey works (game build 1.0.2.5; addresses are RVAs):
- The developers' debug options survive in the release build as a synced command (input_command___enable_debug_option,
  INPUT_COMMAND_TYPE 14). Every player's simulation runs it in input_command_list::process_commands, whose
  ADD_RESOURCES case (DEBUG_OPTION 13) calls UDebugUI::add_resources(the sending player): 500 of each resource.
- The dead UDebugUI::unlock_all_meta_progression (nothing calls it) becomes a `ret` followed by two new routines:
  RESOURCES  add_resources now jumps here. For the sender's team, world_resources::add fills wood, stone, iron and
             essence to their storage caps (add stops at the cap). Food and villagers are supply the game recomputes
             every tick (world_resources::update, per team block of 63 ints): villagers on hand = the lasting bonus
             (index 56 + type, what the editor's "change resources" trigger adds to) + what houses give - what's in
             use; food on hand = what farms give - what's in use (index 14 + type, which agent_database::
             add_maintenance / remove_maintenance keep up to date), food capacity = farms + the bonus. So both get
             +FOOD/+VILLAGERS on the bonus, and food's in-use count also drops by FOOD (from HOTKEY_VERSION 2; version 1
             only raised food capacity). From HOTKEY_VERSION 4 food and villagers are refilled to FOOD/VILLAGERS rather
             than raised by them every press: villagers' bonus grows by what's missing up to VILLAGERS on hand, food's
             bonus by what capacity lacks up to FOOD, and food in use drops by what's missing up to FOOD on hand (the
             team's current values, index 0 + type, and capacity, index 7 + type, are last tick's, the same on every
             PC). Version 4 also adds GOLD gold through world_resources::add.
  TICK       The player controllers' calls to the base Tick (AAchillesGameplayPlayerControllerBase::Tick) now call
             this: the base Tick, then, if WasInputKeyJustPressed(EKeys::Add), the developers' own create-and-queue
             sequence for CreateEnableDebugOptionsCommand(ADD_RESOURCES). Unreal's input only reports keys while the game
             has focus, and only to the local player's controller (a listen server's copies of remote players' controllers
             have no input). Single player uses AAchillesPlayerController (GamePlayerController); multiplayer uses
             AAchillesMultiplayerController (MpGamePlayerController), so both Ticks are hooked from HOTKEY_VERSION 3
             (versions 1 and 2 hooked only single player's, so the key did nothing in multiplayer). In multiplayer,
             QueuePlayerInputs goes to the local controller's IPlayerInputScheduler, like every other order.

How the seeds patch works:
- Survival generates its map live from any seed. Multiplayer never does: UMapGeneratorSubsystem::GenerateMap loads the
  first, Voronoi stage from Content/VoronoiPreGen/Multiplayer11x11/<seed>.map (301 seeds ship; 15x15 has 4), and the
  host's AAchillesGameSession picks the seed from that list. Everything after the Voronoi stage is generated live in
  both modes, from FAchillesRandom(seed).
- PREGEN  GenerateMap set "use the pre-generated data" to 1 even when UMapPregenSerializer::Deserialize failed (no such
          file). It now stores Deserialize's result, so a seed without a file is generated live, Voronoi stage
          included, with the multiplayer map rules. The game's own seeds still load their files, exactly as before.
          Every player needs this (it runs on every PC), which the match code makes sure of.
- SEED    On the host, AAchillesGameSession::PostLogin copies the session's MapSeed into the game state (replicated to
          every player, with the match settings). A routine in the dead UDebugUI::lock_all_skills runs first: if the
          game name starts with "seed", the rest becomes the MapSeed (see seed_routine).
Live generation means each PC builds the map itself. The developers ship pre-generated maps for multiplayer, so that is
the part to watch: if two PCs ever build different maps, the game's checksum ends the match ("Simulation divergence").
"""
import base64
import os
import struct
import sys
import zlib

EXE_REL = os.path.join("Achilles", "Binaries", "Win64", "Achilles-Win64-Shipping.exe")
GAME_PAK = os.path.join("Achilles", "Content", "Paks", "Achilles-WindowsNoEditor.pak")
BACKUP_SUFFIX = ".arcade-backup"  # the name predates the hotkey; both mods share the one backup


class PatchError(Exception):
    pass


def exe_path(game):
    return os.path.join(game, EXE_REL)


def backup_path(exe):
    return exe + BACKUP_SUFFIX


def sections(data):
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    count = struct.unpack_from("<H", data, pe + 6)[0]
    o = pe + 24 + struct.unpack_from("<H", data, pe + 20)[0]
    out = []
    for i in range(count):
        vsize, va, rsize, raw = struct.unpack_from("<IIII", data, o + 40 * i + 8)
        out.append((va, vsize, raw))
    return out


def offset(data, rva):
    for va, vsize, raw in sections(data):
        if va <= rva < va + vsize:
            return raw + rva - va
    raise PatchError(f"RVA {rva:#x} is outside the exe")


# ---------------------------------------------------------------------------- days (Arcade Endless)
VANILLA_DAYS = 45
DAYS_HEAD = bytes.fromhex("488b49104881")                      # the 6 bytes the patch replaces
DAYS_TAIL = bytes.fromhex("c100010000e9")                      # kept as-is, followed by the jmp rel32
DAYS_TARGET = (bytes.fromhex("f30f2d05"), bytes.fromhex("d1f8c3"))  # cvtss2si eax,[rip+x]; sar eax,1; ret
DAYS_LEN = 16


def days_site(data):
    """(file offset, current days or None if vanilla). PatchError if the exe isn't one this patch knows."""
    sites = []
    i = data.find(DAYS_TAIL)
    while i != -1:
        site = i - 6
        if site >= 0:
            (rel,) = struct.unpack_from("<i", data, site + 12)
            t = site + DAYS_LEN + rel  # same .text section, so file offsets move with RVAs
            if 0 <= t < len(data) - 11 and data[t:t + 4] == DAYS_TARGET[0] and data[t + 8:t + 11] == DAYS_TARGET[1]:
                head = data[site:site + 6]
                if head == DAYS_HEAD:
                    sites.append((site, None))
                elif head[0] == 0xB8 and head[5] == 0xC3:
                    sites.append((site, struct.unpack_from("<I", head, 1)[0]))
        i = data.find(DAYS_TAIL, i + 1)
    if len(sites) != 1:
        raise PatchError(f"the days patch site was found {len(sites)} times; this game version isn't supported")
    return sites[0]


# ---------------------------------------------------------------------------- hotkey (NightmarePOC)
FOOD = 10_000        # food on hand after a press (versions 1-3: food supply added per press)
VILLAGERS = 10_000   # villagers on hand after a press (versions 1-3: villager supply added per press)
GOLD = 10_000        # gold added per press (from version 4)
FILL = 100_000       # wood, stone, iron, essence: more than any storage cap, so add() fills each to its cap
FIXED = 1024         # the simulation's 22.10 fixed point
ADD_RESOURCES = 13   # DEBUG_OPTION
ENABLE_DEBUG_OPTION = 14  # INPUT_COMMAND_TYPE

CAVE = 0x145BA60     # UDebugUI::unlock_all_meta_progression, 368 bytes, never called
CAVE_LEN = 368
ADD_ENTRY = 0x144CB50  # UDebugUI::add_resources(PLAYER_INDEX)
TICK_CALL = 0x1423579  # in AAchillesPlayerController::Tick: call AAchillesGameplayPlayerControllerBase::Tick
MP_TICK_CALL = 0x1422BA9  # the same call in AAchillesMultiplayerController::Tick (hooked from HOTKEY_VERSION 3)
CALLS = {  # RVA, first bytes (each callee is checked before the patch relies on it)
    "GetAchillesWorld": (0x140AE90, "4883ec28488b0d"),
    "get_team_for_player": (0x15246A0, "0fb6c20fb684c120090000c3"),
    "world_resources_add": (0x155ECB0, "44894c24204c8944241853"),
    "base_tick": (0x1422670, "405553488d6c24b14881ec"),
    "WasInputKeyJustPressed": (0x314DD30, "48895c24184889542410"),
    "CreateEnableDebugOptionsCommand": (0x1181AF0, "48895c241048896c2418"),
    "QueuePlayerInputs": (0x10D6F60, "48895c2408574883ec20"),
}
EKEYS_ADD = 0x54FB778  # EKeys::Add, a static FKey in .data; its first 8 bytes are the key's FName
WORLD_RESOURCES = 0x660  # world_data -> world_resources*
RESOURCE_DATA = 0x68     # world_resources -> int32 table, 63 per team
TEAM_STRIDE = 63 * 4
SUPPLY_FOOD, SUPPLY_VILLAGERS = (56 + 0) * 4, (56 + 4) * 4  # RESOURCE_TYPE FOOD 0, VILLAGER 4
FOOD_IN_USE = (14 + 0) * 4
CURRENT_FOOD, CURRENT_VILLAGERS, MAX_FOOD = 0 * 4, 4 * 4, (7 + 0) * 4
HOTKEY_VERSION = 4  # older versions are recognised so they can be upgraded or removed
ORIGINAL = {
    CAVE: zlib.decompress(base64.b85decode(
        "c-kFMO-lk%6n&!51i`oxf=I!E+C(i{7;X$q&crh$DqOe-CL$<;U<8ARa>i=72rm00(Kad4KImiBGFlWvL~UG{B(L}8Z0_aW!#(#LIA8F`I"
        "z55fh3+ne7z0H?ZSL(E39+bJf8)C+ICTTYgk-c1<~7Db66>vlg`fqUL<bn--kLGRJ=+-Pv{Qg(7Ww8|B_ICCr#rg)%H(ygWE9|S8LN=A45U"
        "m-k7t-3cbS4o`zh1f&Y=0OA^d}MUw4nxynfCG8Eb&zl+)CeVmdc%gYNv@{v-=$jS{ctQYJxzwE~D+oFe&z+6~v|nzIyXI9*{6gJQ7Ss7E}^j"
        "8yF;WvfGSQU0Xku2kXmtWgBLctLsaN6(%G4qHsclJ1wQrgL3UR%**a2$1|8q+F2lL(-W^kN$7$PsSBwpwf`61e_~e-YfhA>s5{_")),
    ADD_ENTRY: bytes.fromhex("48895c2408"),
    TICK_CALL: bytes.fromhex("e8f2f0ffff"),
    MP_TICK_CALL: bytes.fromhex("e8c2faffff"),
}


class Code:
    """x64 machine code assembled at a known RVA, with rel32 calls and jumps resolved."""

    def __init__(self, rva):
        self.rva, self.b, self.fix, self.labels = rva, bytearray(), [], {}

    def raw(self, hexbytes):
        self.b += bytes.fromhex(hexbytes)

    def imm32(self, hexprefix, value):
        self.b += bytes.fromhex(hexprefix) + struct.pack("<i", value)

    def call(self, target):
        self.b += b"\xe8" + struct.pack("<i", target - (self.rva + len(self.b) + 5))

    def rip(self, hexprefix, target):  # an instruction ending in a [rip + disp32] operand
        self.b += bytes.fromhex(hexprefix)
        self.b += struct.pack("<i", target - (self.rva + len(self.b) + 4))

    def jcc(self, op, label, near=False):  # a jcc (short opcode 7x) or jmp (EB) to a label, set before or later
        if near:
            self.b += (b"\xe9" if op == 0xEB else bytes([0x0F, op + 0x10])) + bytes(4)
        else:
            self.b += bytes([op, 0])
        size = 4 if near else 1
        if label in self.labels:
            self.put(len(self.b) - size, size, self.labels[label] - len(self.b), label)
        else:
            self.fix.append((len(self.b) - size, size, label))

    def put(self, pos, size, rel, label):
        assert size == 4 or -128 <= rel <= 127, label
        self.b[pos:pos + size] = struct.pack("<i" if size == 4 else "<b", rel)

    def label(self, name):
        self.labels[name] = len(self.b)
        for pos, size, lab in self.fix:
            if lab == name:
                self.put(pos, size, len(self.b) - (pos + size), name)

    def at(self):
        return self.rva + len(self.b)


def resources_routine(rva, version=HOTKEY_VERSION):
    """UDebugUI::add_resources(this, PLAYER_INDEX player), rewritten. rcx (the debug UI) is unused."""
    c = Code(rva)
    a = {k: v[0] for k, v in CALLS.items()}
    c.raw("53 57 4883ec48")                 # push rbx; push rdi; sub rsp,48h (stack 16-aligned at calls)
    c.raw("0fb6da")                         # movzx ebx,dl              player
    c.call(a["GetAchillesWorld"])
    c.raw("488bf8 488bc8 8bd3")             # mov rdi,rax; mov rcx,rax; mov edx,ebx
    c.call(a["get_team_for_player"])
    c.raw("0fb6d8")                         # movzx ebx,al              team
    # FFixedResourceCost at [rsp+20h]: food, gold, iron, stone, villagers, wood, darkness (int32, 22.10 fixed)
    refill = version >= 4                   # food and villagers are refilled below instead of added here
    c.imm32("c7442420", 0 if refill else FOOD * FIXED)
    c.imm32("c7442424", GOLD * FIXED if refill else 0)  # gold: unchanged before version 4
    c.imm32("b8", FILL * FIXED)             # mov eax,FILL
    c.raw("89442428 8944242c")              # iron, stone
    c.imm32("c7442430", 0 if refill else VILLAGERS * FIXED)
    c.raw("89442434 89442438")              # wood, darkness
    c.imm32("488b8f", WORLD_RESOURCES)      # mov rcx,[rdi+660h]
    c.raw("8bd3 4c8d442420")                # mov edx,ebx; lea r8,[rsp+20h]
    c.imm32("41b9", 1)                      # mov r9d,1
    c.call(a["world_resources_add"])
    c.imm32("488b8f", WORLD_RESOURCES)      # mov rcx,[rdi+660h]
    c.raw("488b41" + f"{RESOURCE_DATA:02x}")  # mov rax,[rcx+68h]
    c.imm32("4869db", TEAM_STRIDE)          # imul rbx,rbx,0FCh          the team's block
    if refill:
        c.raw("488d0418")                   # lea rax,[rax+rbx]
        # (target, the value it's compared with, the slot changed, add 01 or sub 29): edx = target - value; if > 0,
        # slot += edx (or -=)
        for target, value, slot, op, name in ((VILLAGERS, CURRENT_VILLAGERS, SUPPLY_VILLAGERS, "01", "v"),
                                              (FOOD, MAX_FOOD, SUPPLY_FOOD, "01", "cap"),
                                              (FOOD, CURRENT_FOOD, FOOD_IN_USE, "29", "food")):
            c.imm32("ba", target * FIXED)   # mov edx,target
            c.raw(f"2b50{value:02x}")       # sub edx,[rax+value]
            c.jcc(0x7E, name)               # jle: already there
            c.imm32(op + "90", slot)        # add/sub [rax+slot],edx
            c.label(name)
    else:
        changes = [(SUPPLY_FOOD, FOOD), (SUPPLY_VILLAGERS, VILLAGERS)] + ([(FOOD_IN_USE, -FOOD)] if version >= 2 else [])
        for slot, amount in changes:
            c.b += bytes.fromhex("818418") + struct.pack("<ii", slot, amount * FIXED)  # add dword [rax+rbx+slot],amount
    c.raw("4883c448 5f 5b c3")              # add rsp,48h; pop rdi; pop rbx; ret
    return bytes(c.b)


def tick_routine(rva):
    """Replaces the base-Tick call in the controllers' Ticks (rcx = the controller, xmm1 = DeltaSeconds)."""
    c = Code(rva)
    a = {k: v[0] for k, v in CALLS.items()}
    c.raw("53 4883ec40 488bd9")             # push rbx; sub rsp,40h; mov rbx,rcx
    c.call(a["base_tick"])                  # the original call, arguments untouched
    c.rip("488b05", EKEYS_ADD)              # mov rax,[EKeys::Add]       the key's FName
    c.raw("4889442420 33c0 4889442428 4889442430")  # a temporary FKey {name, null KeyDetails} for the callee to destroy
    c.raw("488d542420 488bcb")              # lea rdx,[rsp+20h]; mov rcx,rbx
    c.call(a["WasInputKeyJustPressed"])
    c.raw("84c0") ; c.jcc(0x74, "done")     # test al,al; jz done
    c.raw("488d4c2420")                     # lea rcx,[rsp+20h]          TSharedPtr<input_command> result
    c.imm32("ba", ADD_RESOURCES)            # mov edx,ADD_RESOURCES
    c.imm32("41b8", 1)                      # mov r8d,1
    c.raw("4533c9")                         # xor r9d,r9d
    c.call(a["CreateEnableDebugOptionsCommand"])
    c.raw("488b542420 b1" + f"{ENABLE_DEBUG_OPTION:02x}")  # mov rdx,[rsp+20h]; mov cl,14
    c.call(a["QueuePlayerInputs"])
    # release the shared pointer, exactly as UDebugUI::embolden_all_units does
    c.raw("488b5c2428 4885db") ; c.jcc(0x74, "done")
    c.raw("836b0801") ; c.jcc(0x75, "done")
    c.raw("488b03 488bcb ff10 836b0c01") ; c.jcc(0x75, "done")
    c.raw("488b03 ba01000000 488bcb ff5008")
    c.label("done")
    c.raw("4883c440 5b c3")                 # add rsp,40h; pop rbx; ret
    return bytes(c.b)


def hotkey_code(version=HOTKEY_VERSION):
    """{RVA: patched bytes} for the hotkey sites (before version 3 the multiplayer Tick keeps its original call)."""
    resources_at, tick_at = CAVE + 16, None
    resources = resources_routine(resources_at, version)
    tick_at = (resources_at + len(resources) + 15) // 16 * 16
    tick = tick_routine(tick_at)
    cave = bytearray(b"\xcc" * CAVE_LEN)
    cave[0] = 0xC3  # unlock_all_meta_progression itself does nothing now
    cave[16:16 + len(resources)] = resources
    cave[tick_at - CAVE:tick_at - CAVE + len(tick)] = tick
    assert tick_at - CAVE + len(tick) <= CAVE_LEN
    jmp = b"\xe9" + struct.pack("<i", resources_at - (ADD_ENTRY + 5))
    call = b"\xe8" + struct.pack("<i", tick_at - (TICK_CALL + 5))
    mp_call = b"\xe8" + struct.pack("<i", tick_at - (MP_TICK_CALL + 5)) if version >= 3 else ORIGINAL[MP_TICK_CALL]
    return {CAVE: bytes(cave), ADD_ENTRY: jmp, TICK_CALL: call, MP_TICK_CALL: mp_call}


def hotkey_version(data):
    """0 if the hotkey patch is off, else the version applied. None if the sites hold anything else."""
    for version in [0] + list(range(1, HOTKEY_VERSION + 1)):
        code = ORIGINAL if version == 0 else hotkey_code(version)
        if all(data[offset(data, rva):offset(data, rva) + len(b)] == b for rva, b in code.items()):
            return version
    return None


def hotkey_state(data):
    """'off', 'on' or 'old' (an earlier version of the patch). PatchError if the exe isn't the game version the hotkey
    was made for."""
    for name, (rva, prefix) in CALLS.items():
        if data[offset(data, rva):offset(data, rva) + len(prefix) // 2] != bytes.fromhex(prefix):
            raise PatchError(f"{name} isn't where the hotkey patch expects it; this game version isn't supported")
    version = hotkey_version(data)
    if version is None:
        raise PatchError("the hotkey patch sites hold unexpected bytes; this game version isn't supported")
    return "off" if version == 0 else "on" if version == HOTKEY_VERSION else "old"


def hotkey_on(data):
    """True if any version of the hotkey patch is in the exe; never raises (an exe from another game version: False)."""
    try:
        return bool(hotkey_version(data))
    except PatchError:
        return False


def is_original(data):
    """True if the exe has none of the patches."""
    return days_site(data)[1] is None and not hotkey_on(data) and not seeds_on(data)


# ---------------------------------------------------------------------------- backup
def backup_state(exe, data=None):
    """'none', 'matches' (the backup is the exe as it is now) or 'other' (an original exe, but not this one)."""
    if not os.path.exists(backup_path(exe)):
        return "none"
    with open(backup_path(exe), "rb") as f:
        saved = f.read()
    return "matches" if data is not None and saved == data else "other"


def save_backup(exe, data):
    """Keep a full copy of this exe, which must have neither patch. Replaces a copy of an older game version."""
    if not is_original(data):
        raise PatchError("refusing to back up an exe that's already patched")
    if backup_state(exe, data) == "matches":
        return False
    tmp = backup_path(exe) + ".tmp"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, backup_path(exe))
    return True


def restore_backup(exe):
    with open(backup_path(exe), "rb") as f:
        saved = f.read()
    try:
        ok = is_original(saved)
    except PatchError:
        ok = False
    if not ok:
        raise PatchError(f"{backup_path(exe)} isn't an unpatched game exe; not restoring it")
    write(exe, {0: saved}, whole=True)


def write(exe, changes, whole=False):
    """Write {file offset: bytes} into the exe (or replace it whole), then read them back."""
    try:
        if whole:
            with open(exe, "wb") as f:
                f.write(changes[0])
        else:
            with open(exe, "r+b") as f:
                for off, b in changes.items():
                    f.seek(off)
                    f.write(b)
    except PermissionError:
        raise PatchError("can't write the exe: close the game (and anything holding the file) and try again")
    with open(exe, "rb") as f:
        data = f.read()
    for off, b in changes.items():
        if data[off:off + len(b)] != b:
            raise PatchError("the write to the exe did not stick")


def set_hotkey(exe, on):
    """Turn the hotkey patch on or off. Returns a list of what was done (empty if nothing needed doing)."""
    with open(exe, "rb") as f:
        data = f.read()
    state = hotkey_state(data)
    if state == ("on" if on else "off"):
        return []
    done = []
    if on and is_original(data) and save_backup(exe, data):
        done.append(f"saved a backup of the original exe: {backup_path(exe)}")
    code = hotkey_code() if on else ORIGINAL
    write(exe, {offset(data, rva): b for rva, b in code.items()})
    done.append(f"hotkey patch v{HOTKEY_VERSION} installed (replacing an older version)" if on and state == "old"
                else f"hotkey patch v{HOTKEY_VERSION} installed" if on else "hotkey patch removed")
    return done


# ---------------------------------------------------------------------------- seeds (NightmarePOC)
SEED_CAVE = 0x144F2B0  # UDebugUI::lock_all_skills, 1456 bytes; only its debug option calls it, and nothing sends that
SEED_CAVE_LEN = 256
SEED_SITE = 0x141993E  # in AAchillesGameSession::PostLogin: mov esi,[rdi+258h], the seed it gives the game state
PREGEN_SITE = 0x11CEC6C  # in UMapGeneratorSubsystem::GenerateMap, after Deserialize: mov byte [rdi+4D0h],1
SEED_CALLS = {  # RVA, first bytes
    "IsNumeric": (0x160AAC0, "4883ec28837908017f07"),        # FString::IsNumeric
    "Strihash": (0x832CE0, "4883ec0833c04c8bd285c97e"),     # FCrc::Strihash_DEPRECATED<wchar_t>(len, text)
    "wtoi64_call": (0x14DDC68, "ff150a5b9302"),             # Survival's own call through __imp__wtoi64
}
WTOI64_IMPORT = 0x14DDC6E + 0x2935B0A  # the import slot that call reads
SESSION_MATCH = 0x250  # AAchillesGameSession -> FAchillesMatchSettings (from the travel URL)
SESSION_SEED = SESSION_MATCH + 0x08       # MapSeed
SESSION_NAME = SESSION_MATCH + 0x20       # ChosenGameName (FString: data, Num with the terminator, Max)
SESSION_LOAD_FILE = SESSION_MATCH + 0x40  # LoadFileName, set when a saved game is loaded
SEEDS_VERSION = 1
SEEDS_ORIGINAL = {
    SEED_CAVE: zlib.decompress(base64.b85decode(
        "c-r&mj8WkT4GVV+aSU|~a}4+B%~84O(fH;70|Ubg`!~n`w;bSa$zla^HtqiX->3VBM>lUo;6G-MPTz8mUf=Q;+6qAo9^D-`m>3v58V|l;0"
        "jiV$3H25jcyyM&H$K_vyZ*TAW=5cS9=&k_9-Xn<kGt;w4+KCX4!as3aOn<~aBaO*lJC*&Ea209+N1S=55MaP$6lxZGn*gDGaowmgVnKHu=P"
        "@@I=?)FNAku02Z2U9HXl%M>2y7AeWBLKu{&fU3)E1cL3et+{wtp{KGo^F*@O9{NApQW5B|L;|DSYZJ^{4R(fU*!i%VzdVW8{U`2_&{?{Wq")),
    SEED_SITE: bytes.fromhex("8bb758020000"),
    PREGEN_SITE: bytes.fromhex("c687d004000001"),
}


def seed_routine(rva):
    """Replaces `mov esi,[rdi+258h]` in AAchillesGameSession::PostLogin (rdi = the session). If the game name is
    "seed" + text, the seed becomes that text as Survival reads its seed box: a number if it's numeric (_wtoi64),
    otherwise FCrc::Strihash_DEPRECATED of it. Leading space : - _ and trailing spaces are skipped. A loaded save keeps
    its own seed."""
    c = Code(rva)
    a = {k: v[0] for k, v in SEED_CALLS.items()}
    c.raw("4883ec38")                               # sub rsp,38h (stack 16-aligned at calls)
    c.imm32("8bb7", SESSION_SEED)                   # mov esi,[rdi+258h]       the game's pick, as before
    c.imm32("83bf", SESSION_LOAD_FILE + 8)          # cmp dword [rdi+298h],1   LoadFileName.Num
    c.raw("01") ; c.jcc(0x7F, "done", near=True)    # jg done                  loading a save
    c.imm32("8b97", SESSION_NAME + 8)               # mov edx,[rdi+278h]       ChosenGameName.Num
    c.raw("83ea05") ; c.jcc(0x7E, "done", near=True)  # sub edx,5; jle done    characters after "seed"
    c.imm32("488b8f", SESSION_NAME)                 # mov rcx,[rdi+270h]
    c.raw("488b01")                                 # mov rax,[rcx]            the first 4 characters
    c.raw("49b8" + "2000" * 4 + "4c09c0")           # mov r8,0020002000200020h; or rax,r8   lower case
    c.raw("49b8" + "seed".encode("utf-16-le").hex() + "4c39c0")  # mov r8,"seed"; cmp rax,r8
    c.jcc(0x75, "done", near=True)
    c.raw("4883c108")                               # add rcx,8
    c.label("skip")
    c.raw("0fb701")                                 # movzx eax,word [rcx]
    for ch in " :-_":
        c.raw(f"83f8{ord(ch):02x}") ; c.jcc(0x74, "next")
    c.jcc(0xEB, "trim")
    c.label("next")
    c.raw("4883c102 ffca") ; c.jcc(0x7F, "skip")    # add rcx,2; dec edx; jg skip
    c.jcc(0xEB, "done")
    c.label("trim")
    c.raw("66837c51fe20") ; c.jcc(0x75, "parse")    # cmp word [rcx+rdx*2-2],' '; jne parse
    c.raw("ffca") ; c.jcc(0x75, "trim")             # dec edx; jnz trim
    c.jcc(0xEB, "done")
    c.label("parse")                                # an FString view of the rest at [rsp+20h] (IsNumeric only reads)
    c.raw("48894c2420 89542430")                    # mov [rsp+20h],rcx; mov [rsp+30h],edx   text, length
    c.raw("8d4201 89442428 8944242c")               # lea eax,[rdx+1]; Num and Max
    c.raw("488d4c2420")                             # lea rcx,[rsp+20h]
    c.call(a["IsNumeric"])
    c.raw("84c0") ; c.jcc(0x74, "text")             # test al,al; jz text
    c.raw("488b4c2420")                             # mov rcx,[rsp+20h]
    c.rip("ff15", WTOI64_IMPORT)                    # call [__imp__wtoi64]
    c.jcc(0xEB, "got")
    c.label("text")
    c.raw("8b4c2430 488b542420")                    # mov ecx,[rsp+30h]; mov rdx,[rsp+20h]
    c.call(a["Strihash"])
    c.label("got")
    c.raw("89c6")                                   # mov esi,eax
    c.imm32("8987", SESSION_SEED)                   # mov [rdi+258h],eax       so the match settings carry it too
    c.label("done")
    c.raw("4883c438 c3")                            # add rsp,38h; ret
    return bytes(c.b)


def seeds_code():
    """{RVA: patched bytes} for the seeds sites."""
    routine_at = SEED_CAVE + 16
    routine = seed_routine(routine_at)
    cave = bytearray(b"\xcc" * SEED_CAVE_LEN)
    cave[0] = 0xC3  # lock_all_skills itself does nothing now
    cave[16:16 + len(routine)] = routine
    assert 16 + len(routine) <= SEED_CAVE_LEN
    call = b"\xe8" + struct.pack("<i", routine_at - (SEED_SITE + 5)) + b"\x90"
    return {SEED_CAVE: bytes(cave), SEED_SITE: call, PREGEN_SITE: bytes.fromhex("8887d004000090")}  # mov [rdi+4D0h],al


def seeds_version(data):
    """0 if the seeds patch is off, else the version applied. None if the sites hold anything else."""
    for version, code in ((0, SEEDS_ORIGINAL), (SEEDS_VERSION, seeds_code())):
        if all(data[offset(data, rva):offset(data, rva) + len(b)] == b for rva, b in code.items()):
            return version
    return None


def seeds_state(data):
    """'off' or 'on'. PatchError if the exe isn't the game version the seeds patch was made for."""
    for name, (rva, prefix) in SEED_CALLS.items():
        if data[offset(data, rva):offset(data, rva) + len(prefix) // 2] != bytes.fromhex(prefix):
            raise PatchError(f"{name} isn't where the seeds patch expects it; this game version isn't supported")
    version = seeds_version(data)
    if version is None:
        raise PatchError("the seeds patch sites hold unexpected bytes; this game version isn't supported")
    return "on" if version else "off"


def seeds_on(data):
    """True if the seeds patch is in the exe; never raises (an exe from another game version: False)."""
    try:
        return bool(seeds_version(data))
    except PatchError:
        return False


def set_seeds(exe, on):
    """Turn the seeds patch on or off. Returns a list of what was done (empty if nothing needed doing)."""
    with open(exe, "rb") as f:
        data = f.read()
    if seeds_state(data) == ("on" if on else "off"):
        return []
    done = []
    if on and is_original(data) and save_backup(exe, data):
        done.append(f"saved a backup of the original exe: {backup_path(exe)}")
    code = seeds_code() if on else SEEDS_ORIGINAL
    write(exe, {offset(data, rva): b for rva, b in code.items()})
    done.append("multiplayer seeds patch installed" if on else "multiplayer seeds patch removed")
    return done


def find_game(start):
    folder = start
    for _ in range(5):
        if os.path.exists(os.path.join(folder, GAME_PAK)):
            return folder
        folder = os.path.dirname(folder)
    raise PatchError("can't find the game folder above " + start)


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "status"
    exe = exe_path(argv[2] if len(argv) > 2 else find_game(os.path.dirname(os.path.abspath(__file__))))
    try:
        if cmd == "restore":
            restore_backup(exe)
            print(f"Restored the original exe from {backup_path(exe)}.")
        elif cmd in ("hotkey-on", "hotkey-off"):
            for line in set_hotkey(exe, cmd == "hotkey-on") or ["nothing to do"]:
                print(line)
        elif cmd in ("seeds-on", "seeds-off"):
            for line in set_seeds(exe, cmd == "seeds-on") or ["nothing to do"]:
                print(line)
        elif cmd == "status":
            data = open(exe, "rb").read()
            days = days_site(data)[1]
            print(exe)
            print(f"  days patch:   {'off' if days is None else f'on ({days} days of waves)'}")
            print(f"  hotkey patch: {hotkey_state(data)}")
            print(f"  seeds patch:  {seeds_state(data)}")
            print(f"  backup:       {backup_state(exe, data)}")
        else:
            print(__doc__)
            return 2
    except PatchError as ex:
        print(f"Nothing changed: {ex}.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
