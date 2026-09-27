#!/usr/bin/env python3
"""tools/build_pack.py — compile the IANA database into the two packs
`src/tzpack.nv` carries.

The input is the system's tzdata: the TZif file of every zone
`tzdata.zi` names, and `zone1970.tab`.  The pack keeps each file's
version-2 data block and footer and drops the 32-bit block.  A system
file repeats, up to 2037, the transitions its POSIX footer rule already
gives, and the pack drops those: it keeps every transition up to the
point from which the footer reproduces the table, which is what `zic -b
slim` writes.  Python's `zoneinfo` evaluates the footer for that test.

The compact pack keeps the transitions from 1970-01-01T00:00:00Z up to
2038-01-19T03:14:07Z, the range a signed 32-bit second holds, and
writes each block in the version-1 layout with 4-byte times.  It makes
the type in force in 1970 the zone's type 0, which is the type RFC 8536
section 3.2 applies before the first transition.  Past 2038 the footer
rule answers.

The pack layout, all integers big-endian:

    "NVTZ1"                      magic
    u8                           layout version, 1
    u8 n, n bytes                the tzdata release, "2026c"
    u8                           1 when the pack keeps pre-1970 history
    u16                          zone count, then per zone, sorted by name:
        u8 n, n bytes            the canonical name
        u8 n, n bytes            the ISO 3166 codes from zone1970.tab, "CH,DE,LI"
        u8                       1 when zone1970.tab gives coordinates
        i32, i32                 latitude and longitude in seconds of arc
        u32 n, n bytes           a TZif data block and its footer: 8-byte
                                 times in the full pack, 4-byte times in
                                 the compact one
    u16                          link count, then per link, sorted by name:
        u8 n, n bytes            the link name
        u16                      the index of the zone it names

Run from anywhere:  python3 tools/build_pack.py
"""
import base64, datetime, io, os, struct, zoneinfo

ZI = "/usr/share/zoneinfo/tzdata.zi"
TAB = "/usr/share/zoneinfo/zone1970.tab"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "src", "tzpack.nv")


def read_zi():
    release, zones, links = None, [], {}
    for line in open(ZI):
        if line.startswith("# version"):
            release = line.split()[2]
        elif line.startswith("Z "):
            zones.append(line.split()[1])
        elif line.startswith("L "):
            _, target, name = line.split()
            links[name] = target
    return release, sorted(zones), links


def coord(text):
    """ISO 6709 `+DDMM[SS]` or `+DDDMM[SS]` to seconds of arc."""
    sign = -1 if text[0] == "-" else 1
    digits = text[1:]
    deg_len = 2 if len(digits) in (4, 6) else 3
    d = int(digits[:deg_len])
    m = int(digits[deg_len:deg_len + 2])
    s = int(digits[deg_len + 2:] or 0)
    return sign * (d * 3600 + m * 60 + s)


def read_tab():
    out = {}
    for line in open(TAB):
        if line.startswith("#"):
            continue
        parts = line.rstrip("\n").split("\t")
        codes, pos, name = parts[0], parts[1], parts[2]
        split = max(pos.rfind("+"), pos.rfind("-"))
        out[name] = (codes, coord(pos[:split]), coord(pos[split:]))
    return out


def v2_block(path):
    data = open(path, "rb").read()
    assert data[:4] == b"TZif" and data[4] >= ord("2"), path
    counts = struct.unpack(">6l", data[20:44])
    isut, isstd, leap, time, typ, char = counts
    v1 = 44 + time * 5 + typ * 6 + char + leap * 8 + isstd + isut
    return data[v1:]


def parse_block(block):
    isut, isstd, leap, timecnt, typecnt, charcnt = struct.unpack(">6l", block[20:44])
    p = 44
    times = list(struct.unpack(">%dq" % timecnt, block[p:p + 8 * timecnt])); p += 8 * timecnt
    idx = list(block[p:p + timecnt]); p += timecnt
    types = [struct.unpack(">lBB", block[p + 6 * i:p + 6 * i + 6]) for i in range(typecnt)]
    p += 6 * typecnt
    chars = block[p:p + charcnt]; p += charcnt
    p += leap * 12 + isstd + isut
    footer = block[p:]
    return times, idx, types, chars, footer


def write_block(times, idx, types, chars, footer, version, time_fmt):
    head = b"TZif" + bytes([version]) + b"\0" * 15
    head += struct.pack(">6l", 0, 0, 0, len(times), len(types), len(chars))
    body = b"".join(struct.pack(time_fmt, t) for t in times) + bytes(idx)
    body += b"".join(struct.pack(">lBB", *t) for t in types) + chars
    return head + body + footer


def footer_zone(footer):
    """A `zoneinfo` zone whose whole content is the footer rule."""
    head = b"TZif2" + b"\0" * 15 + struct.pack(">6l", 0, 0, 0, 0, 1, 1)
    body = struct.pack(">lBB", 0, 0, 0) + b"\0"
    return zoneinfo.ZoneInfo.from_file(io.BytesIO(head + body + head + body + footer))


def local_type(z, t):
    d = datetime.datetime.fromtimestamp(t, z)
    return int(d.utcoffset().total_seconds()), d.tzname()


def slim(block):
    """The block without the trailing transitions its footer gives."""
    times, idx, types, chars, footer = parse_block(block)
    rule = footer.strip(b"\n")
    if not rule or not times:
        return block
    fz = footer_zone(footer)

    def table(i):
        off, _, desig = types[idx[i]]
        return off, chars[desig:chars.index(b"\0", desig)].decode()

    # Transition k - 1 can go when the footer gives its change, on both
    # sides of it, and also agrees with the table just after the
    # transition that then becomes the last one kept.
    k = len(times)
    if local_type(fz, times[-1] + 1) != table(len(times) - 1):
        return block
    while k > 1 and local_type(fz, times[k - 1]) == table(k - 1) \
            and local_type(fz, times[k - 1] - 1) == table(k - 2) \
            and local_type(fz, times[k - 2] + 1) == table(k - 2):
        k -= 1
    return write_block(times[:k], idx[:k], types, chars, footer, block[4], ">q")


def compact(block):
    """The block with the transitions outside 1970 to 2038 dropped."""
    times, idx, types, chars, footer = parse_block(block)
    keep = [i for i, t in enumerate(times) if 0 <= t < 2 ** 31]
    before = [i for i, t in enumerate(times) if t < 0]
    start = idx[before[-1]] if before else 0
    order = [start] + [k for k in range(len(types)) if k != start]
    remap = {old: new for new, old in enumerate(order)}
    new_types = [types[k] for k in order]
    return write_block([times[i] for i in keep], [remap[idx[i]] for i in keep],
                       new_types, chars, footer, block[4], ">l")


def pack(release, zones, links, tab, blocks, history):
    out = bytearray(b"NVTZ1")
    out += bytes([1, len(release)]) + release.encode() + bytes([1 if history else 0])
    out += struct.pack(">H", len(zones))
    for z in zones:
        codes, lat, lon = tab.get(z, ("", 0, 0))
        out += bytes([len(z)]) + z.encode() + bytes([len(codes)]) + codes.encode()
        out += bytes([1 if z in tab else 0]) + struct.pack(">ll", lat, lon)
        b = blocks[z] if history else compact(blocks[z])
        out += struct.pack(">L", len(b)) + b
    index = {z: i for i, z in enumerate(zones)}
    names = sorted(links)
    out += struct.pack(">H", len(names))
    for n in names:
        out += bytes([len(n)]) + n.encode() + struct.pack(">H", index[links[n]])
    return bytes(out)


def main():
    release, zones, links = read_zi()
    tab = read_tab()
    blocks = {z: slim(v2_block("/usr/share/zoneinfo/" + z)) for z in zones}
    full = pack(release, zones, links, tab, blocks, True)
    small = pack(release, zones, links, tab, blocks, False)
    with open(OUT, "w") as f:
        f.write("// tzpack — the two packs, generated by tools/build_pack.py from tzdata\n")
        f.write("// %s.  Do not edit: run the tool.\n" % release)
        f.write("//\n// Each is base64 text.  The full pack is %d bytes and the compact one\n" % len(full))
        f.write("// %d, holding %d zones and %d links.\n\n" % (len(small), len(zones), len(links)))
        f.write("// The whole database, history included, as base64 text.\n")
        f.write("fn full_pack_text() -> Str\n    \"%s\"\n\n" % base64.b64encode(full).decode())
        f.write("// The database from 1970 onward, as base64 text.\n")
        f.write("fn compact_pack_text() -> Str\n    \"%s\"\n" % base64.b64encode(small).decode())
    print("release %s: %d zones, %d links; full %d bytes, compact %d bytes"
          % (release, len(zones), len(links), len(full), len(small)))


if __name__ == "__main__":
    main()
