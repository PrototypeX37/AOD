"""UE 4.26 Kismet bytecode (serialized/on-disk form) disassembler + UFunction export splitter.

On disk: object refs = 4 bytes (FPackageIndex), FName = 8, FField* = FFieldPath (int32 n, n*FName, int32 owner).
In memory (what jump/skip offsets are measured in): object refs = 8, FName = 12, FField* = 8.
"""
import struct

T = {0x00: "LocalVariable", 0x01: "InstanceVariable", 0x02: "DefaultVariable", 0x04: "Return", 0x06: "Jump",
     0x07: "JumpIfNot", 0x09: "Assert", 0x0B: "Nothing", 0x0F: "Let", 0x12: "ClassContext", 0x13: "MetaCast",
     0x14: "LetBool", 0x15: "EndParmValue", 0x16: "EndFunctionParms", 0x17: "Self", 0x18: "Skip", 0x19: "Context",
     0x1A: "Context_FailSilent", 0x1B: "VirtualFunction", 0x1C: "FinalFunction", 0x1D: "IntConst", 0x1E: "FloatConst",
     0x1F: "StringConst", 0x20: "ObjectConst", 0x21: "NameConst", 0x22: "RotationConst", 0x23: "VectorConst",
     0x24: "ByteConst", 0x25: "IntZero", 0x26: "IntOne", 0x27: "True", 0x28: "False", 0x29: "TextConst",
     0x2A: "NoObject", 0x2B: "TransformConst", 0x2C: "IntConstByte", 0x2D: "NoInterface", 0x2E: "DynamicCast",
     0x2F: "StructConst", 0x30: "EndStructConst", 0x31: "SetArray", 0x32: "EndArray", 0x33: "PropertyConst",
     0x34: "UnicodeStringConst", 0x35: "Int64Const", 0x36: "UInt64Const", 0x38: "PrimitiveCast", 0x39: "SetSet",
     0x3A: "EndSet", 0x3B: "SetMap", 0x3C: "EndMap", 0x3D: "SetConst", 0x3E: "EndSetConst", 0x3F: "MapConst",
     0x40: "EndMapConst", 0x42: "StructMemberContext", 0x43: "LetMulticastDelegate", 0x44: "LetDelegate",
     0x45: "LocalVirtualFunction", 0x46: "LocalFinalFunction", 0x48: "LocalOutVariable", 0x4B: "InstanceDelegate",
     0x4C: "PushExecutionFlow", 0x4D: "PopExecutionFlow", 0x4E: "ComputedJump", 0x4F: "PopExecutionFlowIfNot",
     0x50: "Breakpoint", 0x51: "InterfaceContext", 0x52: "ObjToInterfaceCast", 0x53: "EndOfScript",
     0x54: "CrossInterfaceCast", 0x55: "InterfaceToObjCast", 0x5A: "WireTracepoint", 0x5B: "SkipOffsetConst",
     0x5C: "AddMulticastDelegate", 0x5D: "ClearMulticastDelegate", 0x5E: "Tracepoint", 0x5F: "LetObj",
     0x60: "LetWeakObjPtr", 0x61: "BindDelegate", 0x62: "RemoveMulticastDelegate", 0x63: "CallMulticastDelegate",
     0x64: "LetValueOnPersistentFrame", 0x65: "ArrayConst", 0x66: "EndArrayConst", 0x67: "SoftObjectConst",
     0x68: "CallMath", 0x69: "SwitchValue", 0x6A: "InstrumentationEvent", 0x6B: "ArrayGetByRef",
     0x6C: "ClassSparseDataVariable", 0x6D: "FieldPathConst"}
INV = {v: k for k, v in T.items()}


class Dis:
    def __init__(self, pkg, script):
        self.p, self.b, self.o, self.mem = pkg, script, 0, 0
        self.lines = []

    def u8(self):
        v = self.b[self.o]; self.o += 1; self.mem += 1; return v

    def u16(self):
        v = struct.unpack_from("<H", self.b, self.o)[0]; self.o += 2; self.mem += 2; return v

    def u32(self):
        v = struct.unpack_from("<I", self.b, self.o)[0]; self.o += 4; self.mem += 4; return v

    def i32(self):
        v = struct.unpack_from("<i", self.b, self.o)[0]; self.o += 4; self.mem += 4; return v

    def f32(self):
        v = struct.unpack_from("<f", self.b, self.o)[0]; self.o += 4; self.mem += 4; return v

    def obj(self):
        v = struct.unpack_from("<i", self.b, self.o)[0]; self.o += 4; self.mem += 8
        return self.p.obj_path(v) if v else "null"

    def name(self):
        i, n = struct.unpack_from("<ii", self.b, self.o); self.o += 8; self.mem += 12
        return self.p.name((i, n))

    def prop(self):
        n = struct.unpack_from("<i", self.b, self.o)[0]; self.o += 4
        path = []
        for _ in range(n):
            path.append(self.p.name(struct.unpack_from("<ii", self.b, self.o))); self.o += 8
        owner = struct.unpack_from("<i", self.b, self.o)[0]; self.o += 4
        self.mem += 8
        return f"{'.'.join(path) or 'null'}@{self.p.obj_name(owner) if owner else '-'}"

    def expr(self, d=0):
        start_mem = self.mem
        t = self.u8()
        nm = T.get(t, f"?{t:#x}")
        a = ""
        if t in (0x00, 0x01, 0x02, 0x48, 0x33, 0x6C):
            a = self.prop()
        elif t in (0x04,):
            a = self.sub(d)
        elif t == 0x06:
            a = f"-> {self.u32():#x}"
        elif t == 0x07:
            a = f"-> {self.u32():#x} if not " + self.sub(d)
        elif t == 0x09:
            self.u16(); self.u8(); a = self.sub(d)
        elif t in (0x0F,):
            a = self.prop() + " := " + self.sub(d) + " , " + self.sub(d)
        elif t in (0x14, 0x5F, 0x60, 0x43, 0x44, 0x5C, 0x62, 0x6B):
            a = self.sub(d) + " := " + self.sub(d)
        elif t in (0x12, 0x19, 0x1A):
            ob = self.sub(d); skip = self.u32(); rv = self.prop(); ce = self.sub(d)
            a = f"[{ob}] skip={skip:#x} rv={rv} :: {ce}"
        elif t in (0x13, 0x2E, 0x52, 0x54, 0x55):
            a = self.obj() + " (" + self.sub(d) + ")"
        elif t == 0x18:
            a = f"skip {self.u32():#x} " + self.sub(d)
        elif t in (0x1B, 0x45):
            a = self.name() + "(" + self.params(d) + ")"
        elif t in (0x1C, 0x46, 0x63, 0x68):
            a = self.obj() + "(" + self.params(d) + ")"
        elif t == 0x1D:
            a = str(self.i32())
        elif t == 0x1E:
            a = f"{self.f32():g}"
        elif t == 0x1F:
            e = self.b.index(b"\0", self.o); s = self.b[self.o:e]; self.mem += e + 1 - self.o; self.o = e + 1
            a = repr(s.decode("latin-1"))
        elif t == 0x34:
            e = self.o
            while self.b[e:e + 2] != b"\0\0": e += 2
            s = self.b[self.o:e].decode("utf-16-le"); self.mem += e + 2 - self.o; self.o = e + 2; a = repr(s)
        elif t == 0x20:
            a = self.obj()
        elif t in (0x21, 0x4B):
            a = self.name()
        elif t in (0x22, 0x23):
            a = ",".join(f"{self.f32():g}" for _ in range(3))
        elif t == 0x2B:
            a = ",".join(f"{self.f32():g}" for _ in range(10))
        elif t in (0x24, 0x2C):
            a = str(self.u8())
        elif t == 0x2F:
            a = self.obj() + f" sz={self.i32()} {{" + self.list_until(0x30, d) + "}"
        elif t == 0x31:
            a = self.sub(d) + " = [" + self.list_until(0x32, d) + "]"
        elif t in (0x39, 0x3B):
            a = self.sub(d); self.i32(); a += " = {" + self.list_until(0x3A if t == 0x39 else 0x3C, d) + "}"
        elif t == 0x3D:
            a = self.prop(); self.i32(); a += " {" + self.list_until(0x3E, d) + "}"
        elif t == 0x3F:
            a = self.prop() + "," + self.prop(); self.i32(); a += " {" + self.list_until(0x40, d) + "}"
        elif t == 0x65:
            a = self.prop(); self.i32(); a += " [" + self.list_until(0x66, d) + "]"
        elif t == 0x35 or t == 0x36:
            self.o += 8; self.mem += 8
        elif t == 0x38:
            a = f"type={self.u8()} " + self.sub(d)
        elif t == 0x42:
            a = self.prop() + " of " + self.sub(d)
        elif t == 0x4C:
            a = f"{self.u32():#x}"
        elif t in (0x4E, 0x4F, 0x51, 0x5D, 0x67, 0x6D):
            a = self.sub(d)
        elif t == 0x61:
            a = self.name() + " " + self.sub(d) + " " + self.sub(d)
        elif t == 0x64:
            a = self.prop() + " := " + self.sub(d)
        elif t == 0x5B:
            a = f"{self.u32():#x}"
        elif t == 0x69:
            n = self.u16(); end = self.u32(); a = f"end={end:#x} idx=" + self.sub(d)
            for _ in range(n):
                a += " case " + self.sub(d); self.u32(); a += " -> " + self.sub(d)
            a += " default " + self.sub(d)
        elif t == 0x6A:
            et = self.u8()
            if et == 4: a = self.name()
        elif t == 0x29:
            kind = self.u8(); a = f"text kind={kind}"
            if kind == 0: pass
            elif kind == 1: a += " " + self.sub(d) + self.sub(d) + self.sub(d)
            elif kind == 2: a += " " + self.sub(d)
            elif kind == 3: a += " " + self.obj() + self.sub(d) + self.sub(d)
            elif kind == 4: a += " " + self.sub(d)
        elif t in (0x0B, 0x15, 0x16, 0x17, 0x25, 0x26, 0x27, 0x28, 0x2A, 0x2D, 0x30, 0x32, 0x3A, 0x3C, 0x3E, 0x40,
                   0x4D, 0x50, 0x53, 0x5A, 0x5E, 0x66):
            pass
        else:
            raise ValueError(f"unhandled token {t:#x} at disk {self.o - 1:#x}")
        return f"{nm}({a})" if a else nm

    def sub(self, d):
        return self.expr(d + 1)

    def params(self, d):
        out = []
        while self.b[self.o] != 0x16:
            out.append(self.sub(d))
        self.u8()
        return ", ".join(out)

    def list_until(self, end, d):
        out = []
        while self.b[self.o] != end:
            out.append(self.sub(d))
        self.u8()
        return ", ".join(out)

    def run(self):
        while self.o < len(self.b):
            m, o = self.mem, self.o
            s = self.expr()
            self.lines.append((m, o, s))
        return self.lines


def split_function(pkg, data):
    """Return (prefix, bytecode_mem_size, script_bytes, suffix) for a UFunction export blob."""
    import ue_pkg as ue
    props, o = ue.read_props(pkg, data)
    r = ue.R(data, o)
    r.i32()            # UField::Next / guid flag (0 in this game)
    r.i32()            # SuperStruct
    r.i32()            # Children
    nprops = r.i32()
    for _ in range(nprops):
        _skip_ffield(pkg, r)
    mem = r.i32(); disk = r.i32()
    pre = data[:r.o - 8]
    script = data[r.o:r.o + disk]
    suf = data[r.o + disk:]
    return pre, mem, script, suf


def _skip_ffield(pkg, r):
    ftype = pkg.name((r.i32(), r.i32()))
    r.i32(); r.i32()            # name
    r.u32()                     # flags
    r.i32(); r.i32(); r.take(8); r.u16()  # ArrayDim, ElementSize, PropertyFlags, RepIndex
    r.i32(); r.i32(); r.u8()    # RepNotifyFunc, BlueprintReplicationCondition
    if ftype in ("StructProperty", "ObjectProperty", "ClassProperty", "WeakObjectProperty", "SoftObjectProperty",
                 "SoftClassProperty", "LazyObjectProperty", "InterfaceProperty", "DelegateProperty",
                 "MulticastInlineDelegateProperty", "MulticastSparseDelegateProperty", "MulticastDelegateProperty"):
        r.i32()
        if ftype in ("ClassProperty", "SoftClassProperty"):
            r.i32()
        if ftype == "MulticastSparseDelegateProperty":
            pass
    elif ftype == "BoolProperty":
        r.take(6)               # FieldSize, ByteOffset, ByteMask, FieldMask, BoolSize, NativeBool
    elif ftype == "ByteProperty":
        r.i32()                 # Enum
    elif ftype == "EnumProperty":
        r.i32(); _skip_ffield(pkg, r)   # Enum + underlying prop
    elif ftype in ("ArrayProperty", "SetProperty"):
        _skip_ffield(pkg, r)
    elif ftype == "MapProperty":
        _skip_ffield(pkg, r); _skip_ffield(pkg, r)
    elif ftype in ("IntProperty", "FloatProperty", "NameProperty", "StrProperty", "TextProperty", "Int64Property",
                   "UInt32Property", "Int8Property", "Int16Property", "UInt16Property", "UInt64Property",
                   "DoubleProperty"):
        pass
    else:
        raise ValueError("unhandled FField type " + ftype)


def disasm_function(pkg, data):
    pre, mem, script, suf = split_function(pkg, data)
    d = Dis(pkg, script)
    lines = d.run()
    assert d.mem == mem, (d.mem, mem)
    return lines
