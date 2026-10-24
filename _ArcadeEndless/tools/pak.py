"""UE 4.26 .pak (version 11, uncompressed, unencrypted) reader and writer.

The writer mirrors the layout of the shipped Achilles-WindowsNoEditor.pak:
  [entries: 53-byte inline FPakEntry header + raw data] [primary index] [path hash index] [full directory index] [footer]
"""
import hashlib
import struct

PAK_MAGIC = 0x5A6F12E1
PAK_VERSION = 11
FOOTER_SIZE = 221
MOUNT_POINT = "../../../"


def _fstr(s):
    e = s.encode("latin-1") + b"\0"
    return struct.pack("<i", len(e)) + e


def _rd_fstr(b, o):
    (n,) = struct.unpack_from("<i", b, o); o += 4
    if n == 0:
        return "", o
    if n > 0:
        return b[o:o + n - 1].decode("latin-1"), o + n
    return b[o:o - 2 * n - 2].decode("utf-16-le"), o - 2 * n


def path_hash(rel_path, seed):
    """FPakFile::HashPath for PakFile_Version_Fnv64BugFix: FNV-64 over lowercase UTF-16, offset basis + seed."""
    h = (0xCBF29CE484222325 + seed) & 0xFFFFFFFFFFFFFFFF
    for c in rel_path.lower().encode("utf-16-le"):
        h ^= c
        h = (h * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return h


def _inline_header(data):
    return struct.pack("<qqqI", 0, len(data), len(data), 0) + hashlib.sha1(data).digest() + b"\0" + struct.pack("<I", 0)


def _encode_entry(offset, size):
    assert offset < 2 ** 32 and size < 2 ** 32
    return struct.pack("<III", 0xE0000000, offset, size)


def _dir_index(files):
    """files: {rel_path: encoded_location}. Includes every parent directory, like UnrealPak does."""
    dirs = {"/": {}}
    for path, loc in files.items():
        d, fn = path.rsplit("/", 1)
        parts = d.split("/")
        for i in range(1, len(parts) + 1):
            dirs.setdefault("/".join(parts[:i]) + "/", {})
        dirs[d + "/"][fn] = loc
    out = struct.pack("<i", len(dirs))
    for d, entries in dirs.items():
        out += _fstr(d) + struct.pack("<i", len(entries))
        for fn, loc in entries.items():
            out += _fstr(fn) + struct.pack("<i", loc)
    return out


def write_pak(out_path, files, seed=0):
    """files: list of (relative path under mount point, bytes)."""
    body = b""
    encoded = b""
    locations = {}
    for rel, data in files:
        assert "\\" not in rel and not rel.startswith("/")
        offset = len(body)
        body += _inline_header(data) + data
        locations[rel] = len(encoded)
        encoded += _encode_entry(offset, len(data))

    hashes = {}
    for rel, loc in locations.items():
        h = path_hash(rel, seed)
        assert h not in hashes, "path hash collision"
        hashes[h] = loc
    full_dir = _dir_index(locations)
    phi = struct.pack("<i", len(hashes)) + b"".join(struct.pack("<Qi", h, loc) for h, loc in hashes.items())
    phi += full_dir  # pruned directory index: keep everything

    index_off = len(body)

    def primary(phi_off, fdi_off):
        b = _fstr(MOUNT_POINT) + struct.pack("<iQ", len(files), seed)
        b += struct.pack("<iqq", 1, phi_off, len(phi)) + hashlib.sha1(phi).digest()
        b += struct.pack("<iqq", 1, fdi_off, len(full_dir)) + hashlib.sha1(full_dir).digest()
        b += struct.pack("<i", len(encoded)) + encoded + struct.pack("<i", 0)
        return b

    plen = len(primary(0, 0))
    phi_off = index_off + plen
    fdi_off = phi_off + len(phi)
    prim = primary(phi_off, fdi_off)
    footer = b"\0" * 16 + b"\0" + struct.pack("<IIqq", PAK_MAGIC, PAK_VERSION, index_off, len(prim))
    footer += hashlib.sha1(prim).digest() + b"\0" * (32 * 5)
    assert len(footer) == FOOTER_SIZE
    with open(out_path, "wb") as f:
        f.write(body + prim + phi + full_dir + footer)


class PakReader:
    def __init__(self, path):
        self.f = open(path, "rb")
        f = self.f
        f.seek(0, 2); size = f.tell()
        f.seek(size - FOOTER_SIZE); foot = f.read(FOOTER_SIZE)
        magic, ver, ioff, isz = struct.unpack_from("<IIqq", foot, 17)
        assert magic == PAK_MAGIC and ver == PAK_VERSION and foot[16] == 0, "unsupported pak"
        f.seek(ioff); idx = f.read(isz)
        self.index_ok = hashlib.sha1(idx).digest() == foot[41:61]
        o = 0
        self.mount, o = _rd_fstr(idx, o)
        self.count, self.seed = struct.unpack_from("<iQ", idx, o); o += 12
        has_phi = struct.unpack_from("<i", idx, o)[0]; o += 4
        phi_off, phi_sz = struct.unpack_from("<qq", idx, o); phi_hash = idx[o + 16:o + 36]; o += 36 if has_phi else 0
        has_fdi = struct.unpack_from("<i", idx, o)[0]; o += 4
        fdi_off, fdi_sz = struct.unpack_from("<qq", idx, o); fdi_hash = idx[o + 16:o + 36]; o += 36
        (elen,) = struct.unpack_from("<i", idx, o); o += 4
        self.encoded = idx[o:o + elen]
        f.seek(fdi_off); fdi = f.read(fdi_sz)
        self.fdi_ok = hashlib.sha1(fdi).digest() == fdi_hash
        self.phi = {}
        if has_phi:
            f.seek(phi_off); phi = f.read(phi_sz)
            self.phi_ok = hashlib.sha1(phi).digest() == phi_hash
            (n,) = struct.unpack_from("<i", phi, 0)
            for i in range(n):
                h, loc = struct.unpack_from("<Qi", phi, 4 + 12 * i)
                self.phi[h] = loc
        self.files = {}
        o = 0
        (nd,) = struct.unpack_from("<i", fdi, o); o += 4
        for _ in range(nd):
            d, o = _rd_fstr(fdi, o)
            (nf,) = struct.unpack_from("<i", fdi, o); o += 4
            for _ in range(nf):
                fn, o = _rd_fstr(fdi, o)
                (loc,) = struct.unpack_from("<i", fdi, o); o += 4
                self.files[d + fn] = loc

    def entry(self, loc):
        (v,) = struct.unpack_from("<I", self.encoded, loc); p = loc + 4
        assert (v >> 23) & 0x3F == 0 and not (v >> 22) & 1, "compressed/encrypted entries not supported"
        if v & 0x3F == 0x3F:
            p += 4

        def num(safe):
            nonlocal p
            if safe:
                x = struct.unpack_from("<I", self.encoded, p)[0]; p += 4
            else:
                x = struct.unpack_from("<q", self.encoded, p)[0]; p += 8
            return x
        off = num((v >> 31) & 1)
        size = num((v >> 30) & 1)
        return off, size

    def read(self, rel):
        off, size = self.entry(self.files[rel])
        self.f.seek(off)
        hdr = self.f.read(53)
        data = self.f.read(size)
        assert hashlib.sha1(data).digest() == hdr[28:48], "entry hash mismatch: " + rel
        return data
