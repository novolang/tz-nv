#!/usr/bin/env python3
"""tools/zoneinfo_vectors.py — the differential vectors in
`tests/zoneinfo_vectors_tests.nv`, answered by Python's `zoneinfo`.

`zoneinfo` reads the system's TZif files, which are compiled from the
same tzdata release as the packs.  For each zone below, the tool takes
transitions from across the zone's history and asks `zoneinfo` two
questions:

  * at the instants one second before, at and after the transition,
    and at fixed instants in 1900, 1950, 2100 and 2400: the offset in
    seconds and the abbreviation;
  * at the wall times on either side of and inside the jump: the UTC
    instant with `fold=0` and with `fold=1`, and whether the wall time
    is unique, ambiguous or never happened.

The answers are written into the test file as text, so the suite needs
no `zoneinfo` when it runs.

Run from anywhere:  python3 tools/zoneinfo_vectors.py
"""
import datetime, os, struct, zoneinfo

ZONES = [
    "Europe/Berlin", "Europe/London", "Europe/Dublin", "America/New_York",
    "America/Sao_Paulo", "America/Santiago", "America/St_Johns", "America/Nuuk",
    "America/Scoresbysund", "Australia/Sydney", "Australia/Lord_Howe", "Pacific/Apia",
    "Pacific/Chatham", "Asia/Kolkata", "Asia/Tehran", "Africa/Casablanca",
    "Antarctica/Troll", "Pacific/Kiritimati", "America/Caracas", "Asia/Gaza",
]
FIXED = [-2208988800, -631152000, 4102444800 + 15638400, 13569465600]
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "tests", "zoneinfo_vectors_tests.nv")
EPOCH = datetime.datetime(1970, 1, 1)


def transitions(zone):
    data = open("/usr/share/zoneinfo/" + zone, "rb").read()
    isut, isstd, leap, time, typ, char = struct.unpack(">6l", data[20:44])
    v1 = 44 + time * 5 + typ * 6 + char + leap * 8 + isstd + isut
    time = struct.unpack(">6l", data[v1 + 20:v1 + 44])[3]
    return list(struct.unpack(">%dq" % time, data[v1 + 44:v1 + 44 + 8 * time]))


def sample(ts):
    """Up to twelve transitions: the first three, three either side of
    1970, three around 2010, and the last three."""
    picks = set(ts[:3]) | set(ts[-3:])
    for pivot in (0, 1262304000):
        after = [t for t in ts if t >= pivot][:3]
        picks |= set(after)
    return sorted(picks)


def offset(z, t):
    d = datetime.datetime.fromtimestamp(t, z)
    return int(d.utcoffset().total_seconds()), d.tzname()


def wall_row(z, wall):
    naive = EPOCH + datetime.timedelta(seconds=wall)
    u0 = int(naive.replace(tzinfo=z, fold=0).timestamp())
    u1 = int(naive.replace(tzinfo=z, fold=1).timestamp())
    back = datetime.datetime.fromtimestamp(u0, z).replace(tzinfo=None)
    if back != naive:
        kind = "G"
    elif u0 != u1:
        kind = "A"
    else:
        kind = "U"
    return kind, u0, u1


def main():
    utc_rows, wall_rows = [], []
    for name in ZONES:
        z = zoneinfo.ZoneInfo(name)
        ts = transitions(name)
        for t in sample(ts):
            for u in (t - 1, t, t + 1):
                off, abbr = offset(z, u)
                utc_rows.append("%s %d %d %s" % (name, u, off, abbr))
            before, _ = offset(z, t - 1)
            after, _ = offset(z, t)
            lo, hi = t + min(before, after), t + max(before, after)
            for wall in sorted({lo - 1800, lo, (lo + hi) // 2, hi - 1, hi, hi + 1800}):
                kind, u0, u1 = wall_row(z, wall)
                wall_rows.append("%s %d %s %d %d" % (name, wall, kind, u0, u1))
        for u in FIXED:
            off, abbr = offset(z, u)
            utc_rows.append("%s %d %d %s" % (name, u, off, abbr))
    with open(OUT, "w") as f:
        f.write(VECTORS_HEAD)
        f.write("// Zone, UTC second, offset east of UTC in seconds, abbreviation.\n")
        f.write("fn utc_rows() -> Str\n    \"%s\"\n\n" % "\\n".join(utc_rows))
        f.write("// Zone, wall time as seconds on the wall clock since 1970-01-01T00:00,\n")
        f.write("// U unique, A ambiguous or G never happened, then the UTC second\n")
        f.write("// `zoneinfo` answers with fold 0 and with fold 1.\n")
        f.write("fn wall_rows() -> Str\n    \"%s\"\n" % "\\n".join(wall_rows))
        f.write(VECTORS_TAIL)
    print("%d instants and %d wall times over %d zones" % (len(utc_rows), len(wall_rows), len(ZONES)))


VECTORS_HEAD = open(os.path.join(HERE, "zoneinfo_vectors_head.txt")).read()
VECTORS_TAIL = open(os.path.join(HERE, "zoneinfo_vectors_tail.txt")).read()

if __name__ == "__main__":
    main()
