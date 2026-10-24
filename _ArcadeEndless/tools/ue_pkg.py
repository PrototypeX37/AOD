"""Minimal UE 4.26 cooked package (.uasset/.uexp) reader/writer with tagged-property support.

Scope: cooked, unversioned-header (FileVersionUE4=0), FilterEditorOnly, no gatherable text,
no searchable names / thumbnails / world tile info -- which is what this game ships.
"""
import struct

PACKAGE_FILE_TAG = 0x9E2A83C1


# ---------------------------------------------------------------- binary helpers
class R:
    def __init__(self, b, o=0):
        self.b, self.o = b, o

    def take(self, n):
        v = self.b[self.o:self.o + n]; self.o += n; return v

    def i32(self):
        v = struct.unpack_from("<i", self.b, self.o)[0]; self.o += 4; return v

    def u32(self):
        v = struct.unpack_from("<I", self.b, self.o)[0]; self.o += 4; return v

    def i64(self):
        v = struct.unpack_from("<q", self.b, self.o)[0]; self.o += 8; return v

    def u16(self):
        v = struct.unpack_from("<H", self.b, self.o)[0]; self.o += 2; return v

    def u8(self):
        v = self.b[self.o]; self.o += 1; return v

    def f32(self):
        v = struct.unpack_from("<f", self.b, self.o)[0]; self.o += 4; return v

    def fstr(self):
        n = self.i32()
        if n == 0:
            return ""
        if n > 0:
            s = self.b[self.o:self.o + n - 1].decode("latin-1"); self.o += n
        else:
            s = self.b[self.o:self.o - 2 * n - 2].decode("utf-16-le"); self.o += -2 * n
        return s


def w_fstr(s):
    if s == "":
        return struct.pack("<i", 0)
    try:
        e = s.encode("latin-1") + b"\0"
        return struct.pack("<i", len(e)) + e
    except UnicodeEncodeError:
        e = s.encode("utf-16-le") + b"\0\0"
        return struct.pack("<i", -(len(e) // 2)) + e


# ---------------------------------------------------------------- FName hashes (verified against shipped name maps)
def _crc_table():
    t = []
    for i in range(256):
        c = i
        for _ in range(8):
            c = (c >> 1) ^ 0xEDB88320 if c & 1 else c >> 1
        t.append(c)
    return t


CRC = _crc_table()


def _crc_table_deprecated():  # MSB-first poly 0x04C11DB7, as FCrc::CRCTable_DEPRECATED
    t = []
    for i in range(256):
        c = i << 24
        for _ in range(8):
            c = ((c << 1) ^ 0x04C11DB7) & 0xFFFFFFFF if c & 0x80000000 else (c << 1) & 0xFFFFFFFF
        t.append(c)
    return t


CRC_DEPRECATED = _crc_table_deprecated()


def strihash_deprecated(s):
    h = 0
    for ch in s.upper().encode("latin-1"):
        h = ((h >> 8) & 0x00FFFFFF) ^ CRC_DEPRECATED[(h ^ ch) & 0xFF]
    return h


def strcrc32(s):
    c = 0xFFFFFFFF
    for ch in s:
        v = ord(ch)
        for _ in range(4):
            c = (c >> 8) ^ CRC[(c ^ v) & 0xFF]; v >>= 8
    return c ^ 0xFFFFFFFF


def name_hashes(s):
    return strihash_deprecated(s) & 0xFFFF, strcrc32(s) & 0xFFFF


# ---------------------------------------------------------------- package
class Import:
    __slots__ = ("class_package", "class_name", "outer", "object_name")

    def __init__(self, cp, cn, outer, on):
        self.class_package, self.class_name, self.outer, self.object_name = cp, cn, outer, on


class Export:
    FIELDS = ("class_index", "super_index", "template_index", "outer_index", "object_name", "object_flags",
              "serial_size", "serial_offset", "forced", "not_client", "not_server", "package_guid",
              "package_flags", "not_always_loaded_editor_game", "is_asset", "first_export_dep",
              "s_before_s", "c_before_s", "s_before_c", "c_before_c")

    def __init__(self, **kw):
        for k in self.FIELDS:
            setattr(self, k, kw.get(k))
        self.data = b""


class Package:
    def __init__(self, uasset: bytes, uexp: bytes):
        self.raw_uasset, self.raw_uexp = uasset, uexp
        r = R(uasset)
        s = self.s = {}
        s["tag"] = r.u32(); s["legacy"] = r.i32(); s["ue3"] = r.i32(); s["ue4"] = r.i32(); s["lic"] = r.i32()
        assert s["tag"] == PACKAGE_FILE_TAG and s["legacy"] == -7
        ncv = r.i32(); assert ncv == 0, "custom versions not supported"
        s["total_header"] = r.i32(); s["folder"] = r.fstr(); s["flags"] = r.u32()
        ncount, noff = r.i32(), r.i32()
        gcount, goff = r.i32(), r.i32(); assert gcount == 0
        ecount, eoff = r.i32(), r.i32()
        icount, ioff = r.i32(), r.i32()
        doff = r.i32()
        srcount, sroff = r.i32(), r.i32()
        snoff = r.i32(); thoff = r.i32(); assert snoff == 0 and thoff == 0
        s["guid"] = r.take(16)
        gens = r.i32(); s["generations"] = [(r.i32(), r.i32()) for _ in range(gens)]
        s["saved_ver"] = r.take(10); s["saved_branch"] = r.fstr()
        s["compat_ver"] = r.take(10); s["compat_branch"] = r.fstr()
        s["compression_flags"] = r.u32(); assert r.i32() == 0
        s["package_source"] = r.u32()
        s["additional"] = [r.fstr() for _ in range(r.i32())]
        aroff = r.i32(); s["bulk_start"] = r.i64(); wtoff = r.i32(); assert wtoff == 0
        s["chunk_ids"] = [r.i32() for _ in range(r.i32())]
        pcount, poff = r.i32(), r.i32()
        assert r.o == noff, (r.o, noff)

        self.names, self.name_hashes = [], []
        for _ in range(ncount):
            self.names.append(r.fstr()); self.name_hashes.append((r.u16(), r.u16()))
        assert r.o == ioff
        self.imports = []
        for _ in range(icount):
            cp = (r.i32(), r.i32()); cn = (r.i32(), r.i32()); outer = r.i32(); on = (r.i32(), r.i32())
            self.imports.append(Import(cp, cn, outer, on))
        assert r.o == eoff
        self.exports = []
        for _ in range(ecount):
            e = Export(class_index=r.i32(), super_index=r.i32(), template_index=r.i32(), outer_index=r.i32(),
                       object_name=(r.i32(), r.i32()), object_flags=r.u32(), serial_size=r.i64(),
                       serial_offset=r.i64(), forced=r.i32(), not_client=r.i32(), not_server=r.i32(),
                       package_guid=r.take(16), package_flags=r.u32(), not_always_loaded_editor_game=r.i32(),
                       is_asset=r.i32(), first_export_dep=r.i32(), s_before_s=r.i32(), c_before_s=r.i32(),
                       s_before_c=r.i32(), c_before_c=r.i32())
            self.exports.append(e)
        assert r.o == doff
        self.depends = [[r.i32() for _ in range(r.i32())] for _ in range(ecount)]
        if srcount:
            assert r.o == sroff
            self.soft_refs = [(r.i32(), r.i32()) for _ in range(srcount)]
        else:
            self.soft_refs = []
        assert r.o == aroff, (r.o, aroff)
        self.asset_registry = uasset[aroff:poff] if pcount else uasset[aroff:s["total_header"]]
        r.o = poff if pcount else s["total_header"]
        self.preload = [r.i32() for _ in range(pcount)]
        assert r.o == s["total_header"] == len(uasset), (r.o, s["total_header"], len(uasset))

        full = uasset + uexp
        for e in self.exports:
            e.data = full[e.serial_offset:e.serial_offset + e.serial_size]
        last = max(e.serial_offset + e.serial_size for e in self.exports)
        self.uexp_tail = full[last:]  # normally just PACKAGE_FILE_TAG
        assert self.uexp_tail[-4:] == struct.pack("<I", PACKAGE_FILE_TAG)
        assert sorted(e.serial_offset for e in self.exports) == [e.serial_offset for e in self.exports], "exports not in order"

    # ------------------------------------------------------------ names
    def name(self, fn):
        idx, num = fn
        s = self.names[idx]
        return s if num == 0 else f"{s}_{num - 1}"

    def name_ref(self, s, add=True):
        """Return (index, number) for a plain name string (no _N suffix handling)."""
        if s in self.names:
            return (self.names.index(s), 0)
        if not add:
            raise KeyError(s)
        self.names.append(s); self.name_hashes.append(name_hashes(s))
        return (len(self.names) - 1, 0)

    def obj_name(self, pidx):
        if pidx == 0:
            return "null"
        if pidx < 0:
            return self.name(self.imports[-pidx - 1].object_name)
        return self.name(self.exports[pidx - 1].object_name)

    def obj_path(self, pidx):
        parts = []
        while pidx:
            parts.append(self.obj_name(pidx))
            pidx = self.imports[-pidx - 1].outer if pidx < 0 else self.exports[pidx - 1].outer_index
        return ".".join(reversed(parts))

    def find_import(self, object_name, class_name=None):
        for i, im in enumerate(self.imports):
            if self.name(im.object_name) == object_name and (class_name is None or self.name(im.class_name) == class_name):
                return -(i + 1)
        return None

    def add_import(self, class_package, class_name, outer, object_name):
        im = Import(self.name_ref(class_package), self.name_ref(class_name), outer, self.name_ref(object_name))
        self.imports.append(im)
        return -len(self.imports)

    # ------------------------------------------------------------ write
    def write(self):
        s = self.s
        names_b = b"".join(w_fstr(n) + struct.pack("<HH", *h) for n, h in zip(self.names, self.name_hashes))
        imports_b = b"".join(struct.pack("<iiiiiii", *im.class_package, *im.class_name, im.outer, *im.object_name)
                             for im in self.imports)
        depends_b = b"".join(struct.pack("<i", len(d)) + struct.pack(f"<{len(d)}i", *d) for d in self.depends)
        soft_b = b"".join(struct.pack("<ii", *x) for x in self.soft_refs)
        preload_b = struct.pack(f"<{len(self.preload)}i", *self.preload)

        def summary(noff, ioff, eoff, doff, sroff, aroff, poff, total, bulk):
            gens = [(len(self.exports), len(self.names))] + s["generations"][1:]
            b = struct.pack("<Iiiiii", s["tag"], s["legacy"], s["ue3"], s["ue4"], s["lic"], 0)
            b += struct.pack("<i", total) + w_fstr(s["folder"]) + struct.pack("<I", s["flags"])
            b += struct.pack("<ii", len(self.names), noff) + struct.pack("<ii", 0, 0)
            b += struct.pack("<ii", len(self.exports), eoff) + struct.pack("<ii", len(self.imports), ioff)
            b += struct.pack("<i", doff) + struct.pack("<ii", len(self.soft_refs), sroff if self.soft_refs else 0)
            b += struct.pack("<ii", 0, 0) + s["guid"]
            b += struct.pack("<i", len(gens)) + b"".join(struct.pack("<ii", *g) for g in gens)
            b += s["saved_ver"] + w_fstr(s["saved_branch"]) + s["compat_ver"] + w_fstr(s["compat_branch"])
            b += struct.pack("<IiI", s["compression_flags"], 0, s["package_source"])
            b += struct.pack("<i", len(s["additional"])) + b"".join(w_fstr(x) for x in s["additional"])
            b += struct.pack("<iqi", aroff, bulk, 0)
            b += struct.pack("<i", len(s["chunk_ids"])) + b"".join(struct.pack("<i", c) for c in s["chunk_ids"])
            b += struct.pack("<ii", len(self.preload), poff if self.preload else 0)
            return b

        sum_len = len(summary(0, 0, 0, 0, 0, 0, 0, 0, 0))
        noff = sum_len
        ioff = noff + len(names_b)
        eoff = ioff + len(imports_b)
        doff = eoff + 104 * len(self.exports)
        sroff = doff + len(depends_b)
        aroff = sroff + len(soft_b)
        poff = aroff + len(self.asset_registry)
        total = poff + len(preload_b)
        off = total
        for e in self.exports:
            e.serial_offset, e.serial_size = off, len(e.data)
            off += len(e.data)
        uexp = b"".join(e.data for e in self.exports) + self.uexp_tail
        bulk = total + len(uexp) - 4
        exports_b = b""
        for e in self.exports:
            exports_b += struct.pack("<iiiiiiIqqiii", e.class_index, e.super_index, e.template_index, e.outer_index,
                                     *e.object_name, e.object_flags, e.serial_size, e.serial_offset,
                                     e.forced, e.not_client, e.not_server)
            exports_b += e.package_guid + struct.pack("<Iiiiiiii", e.package_flags, e.not_always_loaded_editor_game,
                                                      e.is_asset, e.first_export_dep, e.s_before_s, e.c_before_s,
                                                      e.s_before_c, e.c_before_c)
        uasset = summary(noff, ioff, eoff, doff, sroff, aroff, poff, total, bulk) + names_b + imports_b + exports_b \
            + depends_b + soft_b + self.asset_registry + preload_b
        assert len(uasset) == total
        return uasset, uexp


# ---------------------------------------------------------------- tagged properties
class Prop:
    """One FPropertyTag + raw value bytes. Header fields kept as FName refs into the owning package."""

    def __init__(self):
        self.name = self.type = None
        self.array_index = 0
        self.struct_name = self.enum_name = self.inner_type = self.value_type = None
        self.struct_guid = b"\0" * 16
        self.bool_val = 0
        self.prop_guid = None
        self.value = b""

    def encode(self):
        b = struct.pack("<iiii", *self.name, *self.type) + struct.pack("<ii", len(self.value), self.array_index)
        t = self.type_str
        if t == "StructProperty":
            b += struct.pack("<ii", *self.struct_name) + self.struct_guid
        elif t == "BoolProperty":
            b += bytes([self.bool_val])
        elif t in ("ByteProperty", "EnumProperty"):
            b += struct.pack("<ii", *self.enum_name)
        elif t in ("ArrayProperty", "SetProperty"):
            b += struct.pack("<ii", *self.inner_type)
        elif t == "MapProperty":
            b += struct.pack("<iiii", *self.inner_type, *self.value_type)
        if self.prop_guid is None:
            b += b"\0"
        else:
            b += b"\1" + self.prop_guid
        return b + self.value


def read_props(pkg, data, o=0):
    """Parse a tagged property stream; returns (props, offset_after_None)."""
    r = R(data, o)
    props = []
    while True:
        nm = (r.i32(), r.i32())
        if pkg.name(nm) == "None":
            return props, r.o
        p = Prop(); p.name = nm; p.type = (r.i32(), r.i32())
        p.type_str = pkg.name(p.type)
        size = r.i32(); p.array_index = r.i32()
        t = p.type_str
        if t == "StructProperty":
            p.struct_name = (r.i32(), r.i32()); p.struct_guid = r.take(16)
        elif t == "BoolProperty":
            p.bool_val = r.u8()
        elif t in ("ByteProperty", "EnumProperty"):
            p.enum_name = (r.i32(), r.i32())
        elif t in ("ArrayProperty", "SetProperty"):
            p.inner_type = (r.i32(), r.i32())
        elif t == "MapProperty":
            p.inner_type = (r.i32(), r.i32()); p.value_type = (r.i32(), r.i32())
        if r.u8():
            p.prop_guid = r.take(16)
        p.value = r.take(size)
        props.append(p)


def write_props(pkg, props):
    return b"".join(p.encode() for p in props) + struct.pack("<ii", *pkg.name_ref("None"), )


def make_prop(pkg, name, type_, value, **hdr):
    p = Prop(); p.name = pkg.name_ref(name); p.type = pkg.name_ref(type_); p.type_str = type_
    for k, v in hdr.items():
        setattr(p, k, pkg.name_ref(v) if k in ("struct_name", "enum_name", "inner_type", "value_type") else v)
    p.value = value
    return p


NATIVE_STRUCTS = {"Vector": 12, "Rotator": 12, "Vector2D": 8, "LinearColor": 16, "Color": 4, "Guid": 16,
                  "IntPoint": 8, "Quat": 16, "Vector4": 16, "Box": 25, "IntVector": 12}


def describe(pkg, p, depth=0):
    """Human-readable value for dumping."""
    t, v = p.type_str, p.value
    try:
        if t == "IntProperty": return str(struct.unpack("<i", v)[0])
        if t == "FloatProperty": return f"{struct.unpack('<f', v)[0]:g}"
        if t == "BoolProperty": return str(bool(p.bool_val))
        if t in ("NameProperty", "EnumProperty"): return pkg.name(struct.unpack("<ii", v))
        if t == "ByteProperty":
            return pkg.name(struct.unpack("<ii", v)) if len(v) == 8 else str(v[0])
        if t == "ObjectProperty": return f"{struct.unpack('<i', v)[0]} -> {pkg.obj_path(struct.unpack('<i', v)[0])}"
        if t == "StrProperty": return repr(R(v).fstr())
        if t == "SoftObjectProperty":
            r = R(v); nm = pkg.name((r.i32(), r.i32())); sub = r.fstr()
            return nm + (f":{sub}" if sub else "")
        if t == "StructProperty":
            sn = pkg.name(p.struct_name)
            if sn in NATIVE_STRUCTS: return f"{sn}({v.hex()})"
            sub, _ = read_props(pkg, v)
            return "{" + ", ".join(f"{pkg.name(s.name)}={describe(pkg, s, depth + 1)}" for s in sub) + "}"
        if t in ("ArrayProperty", "SetProperty"):
            inner = pkg.name(p.inner_type)
            r = R(v)
            if t == "SetProperty":
                assert r.i32() == 0
            n = r.i32()
            items = []
            if inner in ("EnumProperty", "NameProperty", "ByteProperty") and len(v) - r.o == 8 * n:
                items = [pkg.name((r.i32(), r.i32())) for _ in range(n)]
            elif inner == "ObjectProperty":
                items = [pkg.obj_path(r.i32()) for _ in range(n)]
            elif inner in ("IntProperty",):
                items = [str(r.i32()) for _ in range(n)]
            elif inner == "FloatProperty":
                items = [f"{r.f32():g}" for _ in range(n)]
            else:
                return f"[{inner} x{n}, {len(v)}B]"
            return "[" + ", ".join(items) + "]"
    except Exception as ex:  # noqa
        return f"<{t} {len(v)}B err {ex}>"
    return f"<{t} {len(v)}B>"


def load(path_noext):
    return Package(open(path_noext + ".uasset", "rb").read(), open(path_noext + ".uexp", "rb").read())


def dump(pkg, only=None, maxlen=400):
    print(f"names={len(pkg.names)} imports={len(pkg.imports)} exports={len(pkg.exports)} preload={len(pkg.preload)}")
    for i, e in enumerate(pkg.exports, 1):
        nm = pkg.name(e.object_name)
        if only and not any(o in nm for o in only):
            continue
        print(f"[{i}] {nm}  class={pkg.obj_name(e.class_index)} outer={pkg.obj_name(e.outer_index)} "
              f"tmpl={pkg.obj_name(e.template_index)} flags={e.object_flags:#x} size={len(e.data)}")
        try:
            props, end = read_props(pkg, e.data)
            for p in props:
                d = describe(pkg, p)
                print(f"      {pkg.name(p.name)}[{p.array_index}] : {p.type_str} = {d[:maxlen]}")
            print(f"      (+{len(e.data) - end} trailing bytes: {e.data[end:end + 16].hex()})")
        except Exception as ex:
            print(f"      <props unparsed: {ex}>")
