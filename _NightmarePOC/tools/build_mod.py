"""Build dist/NightmarePOC_P.pak from the installed game's own pak (read-only), for any Settings.

  python build_mod.py [settings code]

Changes, all data-only, applied to both Survival and multiplayer constants:
  1. Main menu: re-show the hidden "Editor" button (Menu_UI Tick calls EditorButton.SetVisibility(Visible)),
     and the credit (tools/menu_credit.py) in place of the old Early Access title. Arcade Endless ships the same
     credit; with both installed the game uses this pak's Menu_UI.
  2. The Volatists can train Nightmares, at the costs in Settings.units (by default no population or food):
       - the developers' player-side Volatist Nightmares (PLAYER_AGENT_TYPE_28-31), re-slotted;
       - the horde's Crawler, Axeman, Spearman and Crusher, given to four campaign-only player types
         (Alderin Pikeman/Arbalest, Injured Theda, Crazed Order Aurelia) that Survival/MP never use.
  3. Heroes: Settings.heroes scales each playable hero's health, health regen, damage (melee and special attacks,
     plus the projectiles their ranged attack fires), armour shred, move speed and revive time, and can set their
     armour. By default every hero keeps the game's own stats.
  4. Resource hotkey (Settings.hotkey, off by default): Numpad + tops the presser's food and villagers up to 10,000,
     gives +10,000 gold and fills their wood, stone, iron and essence, synced in multiplayer. That part is an exe patch
     (tools/exe_patches.py, applied when NightmarePOC is installed); the pak only carries HOTKEY_MARKER, so the match
     code tells hotkey and no-hotkey installs apart.
  5. Multiplayer map seeds (Settings.seeds, off by default): the host names the game "seed_<text>" and the map is
     generated live from that seed, like Survival's. Also an exe patch; the pak carries SEEDS_MARKER the same way.

Settings travel as "NP1-" codes: zlib + base64 JSON of what differs from the defaults.

Enemy Nightmare types (ENEMY_AGENT_TYPE_*) stay untouched: agent_database::add sets up any type that has
enemy_constants as horde AI, so a player-trained copy of one crashes on selection. The player versions get
the Nightmare's base/visual/audio/attack data plus player constants and no enemy constants.
"""
import base64
import hashlib
import json
import os
import struct
import sys
import zlib
from dataclasses import dataclass

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import exe_patches  # noqa: E402
import kismet  # noqa: E402
import menu_credit  # noqa: E402
import pak  # noqa: E402
import ue_pkg as ue  # noqa: E402

GAME = os.path.abspath(os.path.join(HERE, "..", ".."))
BASE_PAK = os.path.join(GAME, "Achilles", "Content", "Paks", "Achilles-WindowsNoEditor.pak")
OUT_PAK = os.path.join(HERE, "..", "dist", "NightmarePOC_P.pak")

MODES = ("Survival", "Multiplayer")
MENU_UI = menu_credit.MENU_UI
AGENT_CONSTANTS = {"Survival": "Achilles/Content/Code/AgentConstants_BP",
                   "Multiplayer": "Achilles/Content/Code/MultiplayerConstants/MPAgentConstants_BP"}
PROJECTILE_CONSTANTS = {"Survival": "Achilles/Content/Code/ProjectileConstants_BP",
                        "Multiplayer": "Achilles/Content/Code/MultiplayerConstants/MPProjectileConstants_BP"}
RESEARCH = {"Survival": "Achilles/Content/Code/Research_BP",
            "Multiplayer": "Achilles/Content/Code/MultiplayerConstants/MPResearch_BP"}
VOLATIST_UNIT_LIST = "Achilles/Content/Code/FactionConstants/VolatistsUnitList"
TEMPLATE_PC = "Achilles/Content/DataAssets/PlayerUnits/VolatistNightmares/Volatist_Crusher/Survival/Volatist_CrusherPlayerAgentConstants"
MOD_DIR = "/Game/Mods/NightmarePOC"

# Developers' player-side Nightmares: name, component, agent type, building, slot, cost, seconds, upkeep gold
VOLATIST_UNITS = [
    ("Burster", "Volatist_Burster_GEN_VARIABLE", "PLAYER_AGENT_TYPE_30", "BARRACKS_T0", 6, {"gold": 120}, 12, 4),
    ("Wraith", "Volatist_Wraith_GEN_VARIABLE", "PLAYER_AGENT_TYPE_28", "WORKSHOP_T2", 6, {"gold": 350, "iron": 5}, 25, 12),
    ("Spitter", "Volatist_Spitter_GEN_VARIABLE", "PLAYER_AGENT_TYPE_29", "WORKSHOP_T2", 3, {"gold": 600, "stone": 20, "iron": 10}, 30, 15),
    ("VolatistCrusher", "Volatist_Crusher_GEN_VARIABLE", "PLAYER_AGENT_TYPE_31", "WORKSHOP_T2", 4, {"gold": 800, "stone": 25, "iron": 15}, 35, 18),
]
# Command-card slots the Barracks/Workshop bind() code fills with building actions (8 upgrade, 10 sell, 11 repair).
RESERVED_SLOTS = {"8", "10", "11"}
# Horde Nightmares on borrowed player types:
# name, borrowed component, borrowed type, source Nightmare component, building, slot, eco, cost, seconds, upkeep gold
BORROWED_UNITS = [
    ("Crawler", "Player_Pikeman_Alderin_GEN_VARIABLE", "PLAYER_AGENT_TYPE_26", "Nightmare_crawler_const_GEN_VARIABLE",
     "BARRACKS_T0", 3, "Melee", {"gold": 90}, 10, 3),
    ("Axeman", "Player_Arbalest_Alderin_GEN_VARIABLE", "PLAYER_AGENT_TYPE_27", "Nightmare_axeman_const_GEN_VARIABLE",
     "BARRACKS_T0", 7, "Melee", {"gold": 160, "wood": 10}, 15, 6),
    ("Spearman", "Hero_InjuredTheda_GEN_VARIABLE", "PLAYER_AGENT_TYPE_38", "Nightmare_spearman_const_GEN_VARIABLE",
     "BARRACKS_T0", 9, "Ranged", {"gold": 200, "wood": 15}, 18, 8),
    ("Crusher", "Hero_OrderAureliaCrazed_GEN_VARIABLE", "PLAYER_AGENT_TYPE_37", "Nightmare_crusher_const_GEN_VARIABLE",
     "WORKSHOP_T2", 5, "Melee", {"gold": 900, "stone": 30, "iron": 20}, 40, 20),
]

# ---------------------------------------------------------------------------- settings
# ResourceCost fields, in the order costs are written. villagers is population: a unit uses that many villagers.
RESOURCES = ("gold", "wood", "stone", "iron", "food", "villagers")
UNIT_FIELDS = RESOURCES + ("seconds", "upkeep")  # train time; upkeep is gold, the only upkeep the game's units have
UNIT_ORDER = ("Crawler", "Burster", "Axeman", "Spearman", "Wraith", "Spitter", "VolatistCrusher", "Crusher")
UNIT_MAX = {"villagers": 50, "seconds": 3600, "upkeep": 10000}  # every other field: RESOURCE_MAX
RESOURCE_MAX = 100_000


def _unit_defaults(cost, seconds, upkeep):
    return tuple(cost.get(r, 0) for r in RESOURCES) + (seconds, upkeep)


DEFAULT_UNITS = {u[0]: _unit_defaults(*u[5:8]) for u in VOLATIST_UNITS}
DEFAULT_UNITS.update({u[0]: _unit_defaults(*u[7:10]) for u in BORROWED_UNITS})
assert set(DEFAULT_UNITS) == set(UNIT_ORDER)

# The playable heroes (every hero component with hero_constants), by in-game name. Cyrus's assets are named Jasper,
# Edwin's Champion.
HEROES = {"Aelis": "Hero_Aelis_GEN_VARIABLE", "Aurelia": "Hero_Aurelia_GEN_VARIABLE", "Cyrus": "Hero_Cyrus_GEN_VARIABLE",
          "Edwin": "Hero_Edwin_GEN_VARIABLE", "Hector": "Hero_Hector_GEN_VARIABLE", "Merek": "Hero_Merek_GEN_VARIABLE",
          "Order Aurelia": "Hero_OrderAurelia_GEN_VARIABLE", "Theda": "Hero_Theda_GEN_VARIABLE",
          "Vizargo": "Hero_Vizargo_GEN_VARIABLE"}
HERO_FIELDS = ("health", "regen", "armour", "melee", "special", "ranged", "shred", "speed", "revive")
ATTACKS = ("melee_attack_constants", "special_attack_constants")
# stat: (the constants it lives in, its fields there). Armour is set at every level (None keeps the game's); every
# other stat multiplies. Damage over time scales with its attack's damage. ranged scales the projectiles the hero's
# ranged attack fires (see hero_projectile_types), and shred their armour shred too.
HERO_STATS = {"health": (("base_constants",), ("health",)),
              "regen": (("base_constants",), ("health_regen",)),
              "armour": (("base_constants",), ("armour",)),
              "melee": (("melee_attack_constants",), ("damage", "dot_dps")),
              "special": (("special_attack_constants",), ("damage", "dot_dps")),
              "shred": (ATTACKS, ("armour_shred_damage",)),
              "speed": (("base_constants",), ("move_speed",)),
              "revive": (("hero_constants",), ("revive_cooldown_time",))}
REQUIRED_FIELDS = {"health", "health_regen", "armour", "move_speed", "damage", "revive_cooldown_time"}  # in every hero
GAME_HERO = (1.0, 1.0, None, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0)
DEFAULT_HEROES = {h: GAME_HERO for h in HEROES}
HERO_LEVEL = 10  # the level hero_game_values reads: the top one, where every hero's attacks all exist
MULT_RANGE = (0.05, 20.0)
ARMOUR_MAX = 1000.0
CODE_PREFIX = "NP1-"
HOTKEY_MARKER = "Achilles/Content/Mods/NightmarePOC/ResourceHotkey.txt"
HOTKEY_MARKER_TEXT = (f"NightmarePOC resource hotkey v{exe_patches.HOTKEY_VERSION}: Numpad +. The exe patch is in "
                      "tools/exe_patches.py; its version is here so the match code changes with it.\n").encode()
SEEDS_MARKER = "Achilles/Content/Mods/NightmarePOC/MapSeeds.txt"
SEEDS_MARKER_TEXT = (f"NightmarePOC multiplayer map seeds v{exe_patches.SEEDS_VERSION}: name the game \"seed <text>\". "
                     "The exe patch is in tools/exe_patches.py; every player needs it, so it's in the match code.\n").encode()


@dataclass(frozen=True)
class Settings:
    """units: one UNIT_FIELDS tuple per UNIT_ORDER unit. heroes: one HERO_FIELDS tuple per HEROES hero.
    hotkey: the Numpad + resource hotkey (an exe patch). seeds: multiplayer map seeds (an exe patch)."""
    units: tuple = tuple(DEFAULT_UNITS[u] for u in UNIT_ORDER)
    heroes: tuple = tuple(DEFAULT_HEROES[h] for h in HEROES)
    hotkey: bool = False
    seeds: bool = False

    def unit(self, name):
        return dict(zip(UNIT_FIELDS, self.units[UNIT_ORDER.index(name)]))

    def hero(self, name):
        return dict(zip(HERO_FIELDS, self.heroes[list(HEROES).index(name)]))

    def code(self):
        d = Settings()
        data = {"u": {n: list(v) for n, v, dv in zip(UNIT_ORDER, self.units, d.units) if v != dv},
                "h": {n: list(v) for n, v, dv in zip(HEROES, self.heroes, d.heroes) if v != dv}}
        if self.hotkey:
            data["k"] = True
        if self.seeds:
            data["s"] = True
        raw = zlib.compress(json.dumps(data, separators=(",", ":")).encode(), 9)
        return CODE_PREFIX + base64.urlsafe_b64encode(raw).decode().rstrip("=")

    @classmethod
    def from_code(cls, code):
        code = code.strip()
        if not code.startswith(CODE_PREFIX):
            raise ValueError(f"not a NightmarePOC settings code (they start with {CODE_PREFIX})")
        try:
            raw = code[len(CODE_PREFIX):]
            data = json.loads(zlib.decompress(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))))
            d = cls()
            units = tuple(tuple(data.get("u", {}).get(n, dv)) for n, dv in zip(UNIT_ORDER, d.units))
            heroes = tuple(tuple(data.get("h", {}).get(n, dv)) for n, dv in zip(HEROES, d.heroes))
            hotkey, seeds = data.get("k", False), data.get("s", False)
        except Exception as ex:
            raise ValueError(f"damaged settings code ({ex})") from None
        return cls(units, heroes, hotkey, seeds).checked()

    def checked(self):
        """self, or ValueError naming the first value out of range."""
        if len(self.units) != len(UNIT_ORDER) or len(self.heroes) != len(HEROES):
            raise ValueError("wrong number of units or heroes")
        for name, values in zip(UNIT_ORDER, self.units):
            if len(values) != len(UNIT_FIELDS):
                raise ValueError(f"{name}: wrong number of values")
            for field, x in zip(UNIT_FIELDS, values):
                lo, hi = (1 if field == "seconds" else 0), UNIT_MAX.get(field, RESOURCE_MAX)
                if type(x) is not int or not lo <= x <= hi:
                    raise ValueError(f"{name} {field}: {x!r} isn't a whole number from {lo} to {hi:,}")
        for name, values in zip(HEROES, self.heroes):
            if len(values) != len(HERO_FIELDS):
                raise ValueError(f"{name}: wrong number of values")
            for field, x in zip(HERO_FIELDS, values):
                if field == "armour" and x is None:
                    continue
                lo, hi = (0.0, ARMOUR_MAX) if field == "armour" else MULT_RANGE
                if type(x) not in (int, float) or not lo <= x <= hi:
                    raise ValueError(f"{name} {field}: {x!r} isn't a number from {lo:g} to {hi:g}")
        for name, x in (("hotkey", self.hotkey), ("seeds", self.seeds)):
            if type(x) is not bool:
                raise ValueError(f"{name}: {x!r} isn't true or false")
        return self


def unit_costs(s, name):
    """(purchase cost without the zero resources, train seconds, upkeep gold) of one Nightmare under settings s."""
    u = s.unit(name)
    return {r: u[r] for r in RESOURCES if u[r]}, u["seconds"], u["upkeep"]


def hero_edits(h):
    """{constants key: {field: (multiplier, value)}} for one hero's settings, leaving out what stays the game's."""
    edits = {}
    for stat, (keys, names) in HERO_STATS.items():
        x = h[stat]
        if x is None or (stat != "armour" and x == 1):
            continue
        for key in keys:
            for name in names:
                edits.setdefault(key, {})[name] = (None, float(x)) if stat == "armour" else (float(x), None)
    return edits

ESLATEVISIBILITY_VISIBLE = 0
VARIENT_ARRAY_LEN = 10


def game_to_pak(path):
    return "Achilles/Content/" + path[len("/Game/"):]


class Builder:
    def __init__(self, base_pak=BASE_PAK):
        self.base = pak.PakReader(base_pak)
        self.out = {}

    def load_base(self, path):
        return ue.Package(self.base.read(path + ".uasset"), self.base.read(path + ".uexp"))

    def load(self, path):
        """A fresh copy of the latest version: already patched in this build, else the base game's."""
        if path + ".uasset" in self.out:
            return ue.Package(self.out[path + ".uasset"], self.out[path + ".uexp"])
        return self.load_base(path)

    def save(self, path, pkg):
        uasset, uexp = pkg.write()
        again = ue.Package(uasset, uexp)              # must re-parse...
        assert again.write() == (uasset, uexp), path   # ...and round-trip exactly
        self.out[path + ".uasset"] = uasset
        self.out[path + ".uexp"] = uexp
        return again


def find_export(pkg, name):
    for i, e in enumerate(pkg.exports):
        if pkg.name(e.object_name) == name:
            return i, e
    raise KeyError(name)


def component_props(pkg, comp):
    props, _ = ue.read_props(pkg, find_export(pkg, comp)[1].data)
    return {pkg.name(x.name): ue.describe(pkg, x) for x in props}


def soft_path(b, mode, comp, key):
    return game_to_pak(component_props(b.load(AGENT_CONSTANTS[mode]), comp)[key].split(".")[0])


def float_struct(pkg, values):
    sub = [ue.make_prop(pkg, k, "FloatProperty", struct.pack("<f", float(v))) for k, v in values.items()]
    return ue.write_props(pkg, sub)


def edit_export(b, path, export_name, fn):
    """Load, let fn(pkg, props) mutate the export's tagged properties, save."""
    pkg = b.load(path)
    e = pkg.exports[0] if export_name is None else find_export(pkg, export_name)[1]
    props, end = ue.read_props(pkg, e.data)
    props = fn(pkg, props) or props
    e.data = ue.write_props(pkg, props) + e.data[end:]
    b.save(path, pkg)


# ---------------------------------------------------------------------------- 1. main menu
def patch_menu_ui(b):
    pkg = b.load(MENU_UI)
    _, tick = find_export(pkg, "Tick")
    pre, mem, script, suf = kismet.split_function(pkg, tick.data)
    owner = pkg.find_import("MainMenuUI", "Class")
    assert owner is not None
    # Context(self.EditorButton) :: VirtualFunction SetVisibility(ByteConst Visible)
    call = b"\x1b" + struct.pack("<ii", *pkg.name_ref("SetVisibility")) + bytes([0x24, ESLATEVISIBILITY_VISIBLE]) + b"\x16"
    call_mem = 1 + 12 + 2 + 1
    ctx = b"\x19" + b"\x01" + struct.pack("<i", 1) + struct.pack("<ii", *pkg.name_ref("EditorButton", add=False)) \
        + struct.pack("<i", owner) + struct.pack("<I", call_mem) + struct.pack("<ii", 0, 0) + call
    ctx_mem = 1 + (1 + 8) + 4 + 8 + call_mem
    tick.data = pre + struct.pack("<ii", mem + ctx_mem, len(script) + len(ctx)) + ctx + script + suf
    menu_credit.add_credit(pkg)
    pkg = b.save(MENU_UI, pkg)
    lines = kismet.disasm_function(pkg, find_export(pkg, "Tick")[1].data)  # asserts in-memory size matches
    print("  Menu_UI Tick[0]:", lines[0][2])
    print(f"  Menu_UI {menu_credit.LABEL}: {menu_credit.CREDIT!r}")


# ---------------------------------------------------------------------------- 2. Nightmares
def set_player_constants(pkg, props, building, slot, cost, seconds, upkeep):
    assert str(slot) not in RESERVED_SLOTS and set(cost) <= set(RESOURCES), (slot, cost)
    by = {pkg.name(p.name): p for p in props}
    guid = by["purchase_cost"].struct_guid
    for name in ("build_location", "build_action_mapping"):
        if name in by:
            props.remove(by[name])
    values = [ue.make_prop(pkg, "build_location", "EnumProperty",
                           struct.pack("<ii", *pkg.name_ref("BUILDING_TYPE::" + building)), enum_name="BUILDING_TYPE"),
              ue.make_prop(pkg, "button_index", "IntProperty", struct.pack("<i", slot)),
              ue.make_prop(pkg, "build_time_in_seconds", "IntProperty", struct.pack("<i", seconds)),
              ue.make_prop(pkg, "purchase_cost", "StructProperty", float_struct(pkg, cost),
                           struct_name="ResourceCost", struct_guid=guid),
              ue.make_prop(pkg, "maintenance_cost", "StructProperty", float_struct(pkg, {"gold": upkeep} if upkeep else {}),
                           struct_name="ResourceCost", struct_guid=guid)]
    keep = [p for p in props if pkg.name(p.name) not in {pkg.name(v.name) for v in values}]
    return keep[:1] + values + keep[1:]


def patch_volatist_units(b, s):
    for unit, comp, agent_type, building, slot, *_ in VOLATIST_UNITS:
        cost, seconds, upkeep = unit_costs(s, unit)
        for mode in MODES:
            d = component_props(b.load(AGENT_CONSTANTS[mode]), comp)
            assert d["type"] == "AGENT_TYPE::" + agent_type and "enemy_constants" not in d, comp
            path = soft_path(b, mode, comp, "player_agent_constants")
            edit_export(b, path, None, lambda pkg, props: set_player_constants(pkg, props, building, slot, cost, seconds, upkeep))
            print(f"  {mode:11} {unit:15} {building} slot {slot:2} {cost} {seconds}s, upkeep {upkeep}")


def pc_package_path(unit):
    return f"{MOD_DIR}/NM_{unit}PlayerConstants"


def make_player_constants(b, unit, building, slot, eco, cost, seconds, upkeep):
    pkg = b.load_base(TEMPLATE_PC)
    new_path = pc_package_path(unit)

    def rename(old, new):
        i = pkg.names.index(old)
        pkg.names[i] = new
        pkg.name_hashes[i] = ue.name_hashes(new)
    rename("/" + TEMPLATE_PC.replace("Achilles/Content/", "Game/"), new_path)
    rename("Volatist_CrusherPlayerAgentConstants", f"NM_{unit}PlayerConstants")
    if eco != "Melee":
        rename("/Game/Code/FactionConstants/FactionEcoModifiers/AgentEco_Melee", f"/Game/Code/FactionConstants/FactionEcoModifiers/AgentEco_{eco}")
        rename("AgentEco_Melee_C", f"AgentEco_{eco}_C")
        rename("Default__AgentEco_Melee_C", f"Default__AgentEco_{eco}_C")
    pkg.s["guid"] = hashlib.md5(new_path.encode()).digest()
    e = pkg.exports[0]
    props, end = ue.read_props(pkg, e.data)
    e.data = ue.write_props(pkg, set_player_constants(pkg, props, building, slot, cost, seconds, upkeep)) + e.data[end:]
    b.save(game_to_pak(new_path), pkg)


def add_training_ui(b, path):
    """Nightmare visual constants lack the training-button fields; point them at the already-imported portrait."""
    def fn(pkg, props):
        by = {pkg.name(p.name): p for p in props}
        for name in ("display_training_icon", "action_mapping_icon", "multiple_selection_icon"):
            if name not in by:
                props.append(ue.make_prop(pkg, name, "ObjectProperty", by["display_portrait_icon"].value))
        for name in ("display_train_text", "display_training_text"):
            if name not in by:
                props.append(ue.make_prop(pkg, name, "TextProperty", by["display_name"].value))
    edit_export(b, path, None, fn)


def patch_borrowed_units(b, s):
    for mode in MODES:
        ac_path = AGENT_CONSTANTS[mode]
        pkg = b.load(ac_path)
        for unit, comp, agent_type, source, *_ in BORROWED_UNITS:
            _, target = find_export(pkg, comp)
            tprops, tend = ue.read_props(pkg, target.data)
            type_prop = [p for p in tprops if pkg.name(p.name) == "type"][0]
            assert ue.describe(pkg, type_prop) == "AGENT_TYPE::" + agent_type, comp
            sprops, _ = ue.read_props(pkg, find_export(pkg, source)[1].data)
            new = [type_prop]
            for p in sprops:
                n = pkg.name(p.name)
                if n in ("type", "enemy_constants"):
                    continue
                new.append(p)
                if n == "base_constants":
                    soft = pc_package_path(unit) + f".NM_{unit}PlayerConstants"
                    new.append(ue.make_prop(pkg, "player_agent_constants", "SoftObjectProperty",
                                            struct.pack("<ii", *pkg.name_ref(soft)) + struct.pack("<i", 0)))
            target.data = ue.write_props(pkg, new) + target.data[tend:]
        b.save(ac_path, pkg)
        for unit, comp, agent_type, source, *_ in BORROWED_UNITS:
            add_training_ui(b, soft_path(b, mode, source, "visual_constants"))
            print(f"  {mode:11} {unit:15} -> {agent_type} (was {comp.replace('_GEN_VARIABLE', '')})")
    for unit, _, _, _, building, slot, eco, *_ in BORROWED_UNITS:
        cost, seconds, upkeep = unit_costs(s, unit)
        make_player_constants(b, unit, building, slot, eco, cost, seconds, upkeep)
        print(f"  NM_{unit}PlayerConstants: {building} slot {slot}, {cost}, {seconds}s, upkeep {upkeep}")


def patch_unit_list(b):
    def fn(pkg, props):
        (p,) = [x for x in props if pkg.name(x.name) == "enabled_unit_types"]
        r = ue.R(p.value)
        assert r.i32() == 0
        n = r.i32()
        entries = [(r.i32(), r.i32()) for _ in range(n)]
        for agent_type in [u[2] for u in VOLATIST_UNITS + BORROWED_UNITS]:
            ref = pkg.name_ref("AGENT_TYPE::" + agent_type)
            if ref not in entries:
                entries.append(ref)
        p.value = struct.pack("<ii", 0, len(entries)) + b"".join(struct.pack("<ii", *x) for x in entries)
        print(f"  VolatistsUnitList: {n} -> {len(entries)} unit types")
    edit_export(b, VOLATIST_UNIT_LIST, None, fn)


# ---------------------------------------------------------------------------- 3. heroes
def rewrite_varient(pkg, prop, mult=None, value=None):
    """Scale (mult) or set (value) a UFloatVarientValue so the result holds in SAME, INCREASE and ARRAY modes."""
    sub, _ = ue.read_props(pkg, prop.value)
    get = lambda name, i=0: next((s for s in sub if pkg.name(s.name) == name and s.array_index == i), None)
    mode = get("edit_mode")
    mode = ue.describe(pkg, mode).split("::")[-1] if mode else "SAME"
    f = lambda p: struct.unpack("<f", p.value)[0]
    start = get("start_value")
    base = f(start) if start else None
    new = [s for s in sub if pkg.name(s.name) not in ("start_value", "increase_value", "value_array")]
    if value is not None:
        new.append(ue.make_prop(pkg, "start_value", "FloatProperty", struct.pack("<f", value)))
        new.append(ue.make_prop(pkg, "increase_value", "FloatProperty", struct.pack("<f", 0.0)))
    else:
        if start:
            new.append(ue.make_prop(pkg, "start_value", "FloatProperty", struct.pack("<f", base * mult)))
        inc = get("increase_value")
        if inc:
            new.append(ue.make_prop(pkg, "increase_value", "FloatProperty",
                                    struct.pack("<f", f(inc) * mult if mode == "INCREASE" else f(inc))))
    for i in range(VARIENT_ARRAY_LEN):
        old = get("value_array", i)
        v = value if value is not None else ((f(old) if old else base) * mult if (old or base is not None) else None)
        if v is None:
            continue
        p = ue.make_prop(pkg, "value_array", "FloatProperty", struct.pack("<f", v))
        p.array_index = i
        new.append(p)
    prop.value = ue.write_props(pkg, new)


def scale_number(prop, mult):
    if prop.type_str == "FloatProperty":
        prop.value = struct.pack("<f", struct.unpack("<f", prop.value)[0] * mult)
    elif prop.type_str == "IntProperty":
        prop.value = struct.pack("<i", round(struct.unpack("<i", prop.value)[0] * mult))
    else:
        raise TypeError(prop.type_str)


def set_number(pkg, prop, mult=None, value=None):
    """Scale or set a stat, stored as a per-level UFloatVarientValue or a plain number."""
    if prop.type_str == "StructProperty":
        rewrite_varient(pkg, prop, mult=mult, value=value)
    elif value is not None:
        prop.value = struct.pack("<f", value) if prop.type_str == "FloatProperty" else struct.pack("<i", round(value))
    else:
        scale_number(prop, mult)


def hero_assets(b, mode, comp):
    """{constants key: pak path} of the hero's constants that HERO_STATS can touch."""
    d = component_props(b.load(AGENT_CONSTANTS[mode]), comp)
    keys = sorted({k for ks, _ in HERO_STATS.values() for k in ks})
    return {k: game_to_pak(d[k].split(".")[0]) for k in keys if k in d}


def asset_fields(b, path):
    pkg = b.load(path)
    props, _ = ue.read_props(pkg, pkg.exports[0].data)
    return {pkg.name(p.name) for p in props}


def level_value(pkg, prop, level=HERO_LEVEL):
    """A stat at one hero level, as the game reads it: a plain number, or a UFloatVarientValue (edit mode SAME, the
    default, uses start_value; INCREASE adds increase_value per level; ARRAY reads value_array)."""
    if prop.type_str in ("FloatProperty", "IntProperty"):
        return float(struct.unpack("<f" if prop.type_str == "FloatProperty" else "<i", prop.value)[0])
    sub, _ = ue.read_props(pkg, prop.value)

    def get(name, i=0):
        return next((struct.unpack("<f", s.value)[0] for s in sub if pkg.name(s.name) == name and s.array_index == i), None)
    mode = next((ue.describe(pkg, s).split("::")[-1] for s in sub if pkg.name(s.name) == "edit_mode"), "SAME")
    if mode == "SAME":
        return get("start_value") or 0.0
    if mode == "INCREASE":
        return (get("start_value") or 0.0) + (get("increase_value") or 0.0) * (level - 1)
    return get("value_array", level - 1) or 0.0


def hero_game_values(base_pak=BASE_PAK, mode=MODES[0]):
    """{hero: {HERO_FIELDS field: the game's value at HERO_LEVEL}}, None where the hero has no such stat (or it's 0,
    so a multiplier can't change it; armour excepted). shred is the first armour shred of the melee, special and
    ranged attacks; the hero's other shred scales with it."""
    b = Builder(base_pak)
    pc = b.load(PROJECTILE_CONSTANTS[mode])
    projectiles = {}
    for e in pc.exports:
        props, _ = ue.read_props(pc, e.data)
        d = {pc.name(p.name): p for p in props}
        if "type" in d:
            projectiles[ue.describe(pc, d["type"])] = d
    out = {}
    for hero, comp in HEROES.items():
        d = component_props(b.load(AGENT_CONSTANTS[mode]), comp)
        assets = {}
        for key in ("base_constants", "ranged_attack_constants", "hero_constants") + ATTACKS:
            if key in d:
                pkg = b.load(game_to_pak(d[key].split(".")[0]))
                props, _ = ue.read_props(pkg, pkg.exports[0].data)
                assets[key] = (pkg, props, {pkg.name(p.name): p for p in props})

        def value(key, name):
            if key not in assets or name not in assets[key][2]:
                return None
            return level_value(assets[key][0], assets[key][2][name])
        shot = None
        if "ranged_attack_constants" in assets:
            pkg, props, _ = assets["ranged_attack_constants"]
            levels = [p for p in props if pkg.name(p.name) == "projectile" and p.array_index < HERO_LEVEL]
            if levels:
                shot = projectiles.get(ue.describe(pkg, max(levels, key=lambda p: p.array_index)))
        number = lambda p: float(struct.unpack("<f", p.value)[0])  # projectile damage/shred are plain floats
        v = {"health": value("base_constants", "health"), "regen": value("base_constants", "health_regen"),
             "armour": value("base_constants", "armour"), "melee": value("melee_attack_constants", "damage"),
             "special": value("special_attack_constants", "damage"),
             "ranged": number(shot["damage"]) if shot and "damage" in shot else None,
             "speed": value("base_constants", "move_speed"),
             "revive": value("hero_constants", "revive_cooldown_time")}
        shreds = [value(k, "armour_shred_damage") for k in ATTACKS]
        shreds.append(number(shot["armour_shred_damage"]) if shot and "armour_shred_damage" in shot else None)
        v["shred"] = next((x for x in shreds if x), None)
        out[hero] = {f: (x if f == "armour" or x else None) for f, x in v.items()}
    return out


def hero_projectile_types(b, mode, comp):
    """The PROJECTILE_TYPE values the hero's ranged attack fires, at any level (Vizargo: his Serenity bolts)."""
    d = component_props(b.load(AGENT_CONSTANTS[mode]), comp)
    if "ranged_attack_constants" not in d:
        return set()
    pkg = b.load(game_to_pak(d["ranged_attack_constants"].split(".")[0]))
    props, _ = ue.read_props(pkg, pkg.exports[0].data)
    return {ue.describe(pkg, p) for p in props if pkg.name(p.name) in ("projectile", "siege_projectile")}


def patch_heroes(b, s):
    for mode in MODES:
        owners = {}
        for hero, comp in HEROES.items():
            paths = hero_assets(b, mode, comp)
            for key, fields in hero_edits(s.hero(hero)).items():
                if key not in paths:  # Cyrus has no melee or special attack
                    continue
                path = paths[key]
                have = asset_fields(b, path)
                assert not (set(fields) & REQUIRED_FIELDS) - have, (path, set(fields) - have)
                fields = {n: v for n, v in fields.items() if n in have}  # e.g. shred, for attacks that don't shred
                if not fields:
                    continue
                assert owners.setdefault(path, hero) == hero, (path, owners[path], hero)

                def fn(pkg, props, fields=fields):
                    for p in props:
                        if pkg.name(p.name) in fields:
                            set_number(pkg, p, *fields[pkg.name(p.name)])
                edit_export(b, path, None, fn)
                print(f"  {mode:11} {hero:13} {path.split('/')[-1]}: {sorted(fields)}")
        mults = {}  # projectile type: (damage, shred) multipliers
        for hero, comp in HEROES.items():
            h = s.hero(hero)
            if h["ranged"] == 1 and h["shred"] == 1:
                continue
            for t in hero_projectile_types(b, mode, comp):
                assert mults.setdefault(t, (h["ranged"], h["shred"])) == (h["ranged"], h["shred"]), t
        if not mults:
            continue
        pc = PROJECTILE_CONSTANTS[mode]
        pkg = b.load(pc)
        count = 0
        for e in pkg.exports:
            props, end = ue.read_props(pkg, e.data)
            t = next((ue.describe(pkg, p) for p in props if pkg.name(p.name) == "type"), None)
            if t not in mults:
                continue
            damage, shred = mults[t]
            for p in props:
                n = pkg.name(p.name)
                if n == "damage" and damage != 1:
                    scale_number(p, damage)
                elif n == "armour_shred_damage" and shred != 1:
                    scale_number(p, shred)
            e.data = ue.write_props(pkg, props) + e.data[end:]
            count += 1
        if count:
            b.save(pc, pkg)
        print(f"  {mode:11} hero projectiles: {count}")


def main(out=OUT_PAK, base_pak=BASE_PAK, settings=None):
    """Build the pak for settings (default: Settings()) from base_pak (the game's own, read-only) into out. The
    Arcade Endless app calls this too."""
    s = (settings or Settings()).checked()
    print(f"Settings {s.code()}")
    b = Builder(base_pak)
    print("Main menu:")
    patch_menu_ui(b)
    print("Volatist Nightmares:")
    patch_volatist_units(b, s)
    print("Horde Nightmares on borrowed player types:")
    patch_borrowed_units(b, s)
    patch_unit_list(b)
    print("Heroes:")
    patch_heroes(b, s)
    if s.hotkey:
        b.out[HOTKEY_MARKER] = HOTKEY_MARKER_TEXT
        print(f"Resource hotkey: on ({HOTKEY_MARKER}; the exe patch is applied on install)")
    if s.seeds:
        b.out[SEEDS_MARKER] = SEEDS_MARKER_TEXT
        print(f"Multiplayer map seeds: on ({SEEDS_MARKER}; the exe patch is applied on install)")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    pak.write_pak(out, sorted(b.out.items()), seed=pak.path_hash("nightmarepoc_p.pak", 0) & 0xFFFFFFFF)
    print(f"Wrote {os.path.abspath(out)} ({len(b.out)} files, {os.path.getsize(out)} bytes)")


if __name__ == "__main__":
    main(settings=Settings.from_code(sys.argv[1]) if len(sys.argv) > 1 else None)
