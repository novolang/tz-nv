# tz-nv

**Status: NOT IMPLEMENTED — interface only.**

Every public function below is published with its signature and its
effect row, and every body is `todo()`. Installing this package works;
calling it panics with `not implemented`.

## What this is

The IANA time zone database, as data a novo-lang program holds rather
than a directory it reads. Give it a zone name and a UTC instant and it
answers the offset, the abbreviation and whether daylight saving was in
force; give it a wall-clock time and it answers what that wall clock
could have meant, which is not always one thing.

- `tzdata` — the compiled database, the name lookup, and the links;
- `tzzone` — one zone, and its answers at an instant;
- `tzlocal` — UTC to a wall clock and back, with the gap and the overlap;
- `tzposix` — the `TZ=CET-1CEST,M3.5.0,M10.5.0/3` rule, and the device half;
- `tzif` — RFC 8536, so a host may read the system's own zone files;
- `tzerr` — what can be wrong, and where.

```
novo pkg add tz-nv
novo pkg build
novo test
```

## The one example that will work

```novo ignore
use iso8601
use tzdata
use tzlocal

// A meeting somebody typed into a form, in the zone they are in.
fn meeting_instant(zone_name: Str, typed: Str) -> Result<Int, Str>
    let db = tzdata.data_compact()
    match tzdata.zone(db, zone_name)
        Err(_) => Err("no such zone")
        Ok(z)  =>
            match iso8601.parse_datetime(typed)
                Err(_) => Err("not a date-time")
                Ok(dt) =>
                    match tzlocal.resolve(z, dt)
                        TzLocalUnique(off)    => Ok(tzlocal.epoch_second(dt, off.total_seconds))
                        TzLocalAmbiguous(_, _) => Err("that hour happened twice — which one?")
                        TzLocalGap(_, _, _)    => Err("the clocks skipped that hour")
```

## The load-bearing interface: `TzLocal`

```novo ignore
pub enum TzLocal
    TzLocalUnique(offset: TzOffset)
    TzLocalGap(before: TzOffset, after: TzOffset, gap_seconds: Int)
    TzLocalAmbiguous(first: TzOffset, second: TzOffset)
```

**Converting a local time to an instant is not a function.** In every
zone that observes daylight saving, twice a year, one of these is true
of a wall time a person typed:

- **It happened twice.** 2026-10-25T02:30 in Berlin is 00:30 UTC, and
  again at 01:30 UTC. Both are real; they are an hour apart.
- **It never happened.** 2026-03-29T02:30 in Berlin does not exist. The
  clocks went from 02:00 to 03:00 and that minute was not on any of
  them.

An API that answered `Int` for those answered by guessing, and the
guess is invisible at the call site: the calendar entry lands an hour
out, the billing window double-counts, the nightly backup runs twice
and nothing logs a thing. `resolve` answers all three cases as data, so
the decision is made by the caller, in the caller's file, where a
person reviewing the code can see which one was chosen.

The asymmetry is the rest of the design: **the other direction cannot
fail.** Every UTC instant has exactly one wall time in a zone, so
`to_local` answers a `CivilDateTime` flat — no `Result`, no enum. Only
the inverse is a relation, and only the inverse gets an enum.

`to_utc` exists for callers who genuinely have a policy, and takes it
as an argument:

| `TzPick` | ambiguous | gap |
| --- | --- | --- |
| `TzPickEarlier` | the earlier instant | the instant before the jump |
| `TzPickLater` | the later instant | the instant after the jump |
| `TzPickShiftForward` | the earlier instant | 02:30 becomes 03:30 |
| `TzPickReject` | `Err` | `Err` |

It answers a `Result` only because `TzPickReject` is in that table: the
three other policies never produce one.

## The database is data, and it costs this much

Nothing in this package opens a file, so the tables are compiled into
it. A `core` package that embeds a table has to say how big the table
is, before somebody finds it in a firmware image:

| | size | what it holds |
| --- | --- | --- |
| `data_compact()` | about 96 KB | 340 zones, 250 links, transitions from 1970 to 2038, every footer rule |
| `data_full()` | about 310 KB | the same zones with the whole recorded history, back to the 1880s |

Both numbers are the design's budget rather than a measurement, and the
implementation step reports what they came out at. For scale: chrono-tz
compiles to roughly 250 KB, Go's embedded `zoneinfo.zip` is about
450 KB, and Python's `tzdata` wheel ships about 500 KB of raw TZif. The
claim being made here is that a compact pack fits under 100 KB, and it
is made by **dropping history** rather than by compressing harder —
because a service that will never see a timestamp from 1936 should not
carry the 1936 rules.

`data_from_pack` is the seam that makes the size somebody else's
choice: a program that must pin tzdata 2024a for a year, or that wants
only the twelve zones its customers are in, builds a pack once and
loads it here. Reading it is still `[]`, because the bytes arrived as
an argument.

## The device claim, and the half it covers

`@tier(embedded)` is claimed for **`tzposix`'s arithmetic and nothing
else**, and `tests/embedded_probe.nv` builds it for a Cortex-M4.

The device is a battery clock — a thermostat, a meter, a panel with an
RTC in it — that has to show the right hour to a person. It has no
filesystem, no network at the moment it needs the answer, and no
intention of spending 96 KB of flash on a time zone. What it has is one
zone, known at manufacture, and forty bytes that describe it:

```text
CET-1CEST,M3.5.0,M10.5.0/3
```

Every number in that string is an `Int` in the firmware's own flash,
and turning it plus an RTC reading into a local hour is five calls of
integer algebra. That is the claim.

The other four modules are **not** claimed, and saying so is the honest
form of the claim: `tzdata` holds the pack, `tzzone` and `tzif` build
lists, and `tzlocal` speaks calendar-nv's civil types, which make no
device claim of their own. Four of the six modules are for a machine
with a heap.

One duplication follows from this and it is the only one in the
package: `tzposix.is_leap_year` repeats calendar-nv's. A probe that
called into calendar-nv would not link, and the Gregorian leap rule is
four lines that have not changed since 1582. Every other date question
in this package goes to calendar-nv.

## A `core` package with a file format in it

`tzif` reads RFC 8536 — the format of every file under
`/usr/share/zoneinfo`. It never opens one. The bytes arrive as an
argument and every function is arithmetic over them, so the `[fs]`
belongs to whoever read the file: chrono-nv on a server, a firmware
image with the file linked into flash, a test with the bytes written in
line.

It is worth having beside the bundled pack for three reasons, and each
one is a real deployment:

- an operating system updates its tzdata on its own schedule, and a
  service that must agree with `date(1)` has to read what `date(1)`
  reads;
- a container image pins its own zoneinfo, and a program that disagreed
  with it would be right about the world and wrong about the machine;
- a government moves a zone between releases of this package — the
  system file updates in days, a package release does not.

Versions 1 through 4 are read, and a version-2-or-later file is read
from its **second** block, always. Reading the first is how an
implementation ends up believing time stops in 2038.

**Leap seconds are read and never applied.** The records are in the
file and `leap_seconds` answers them, because a caller doing TAI
conversion needs them. No conversion here consults them, because POSIX
time does not count them and a library that silently did would
disagree with every clock its caller can read.

## The layer, and the one dependency

`core`, and the two places a reader expects an effect and does not find
one are the two halves of the design: the bundled pack is a byte array
the package owns rather than a file it opens, and `tzif` parses bytes
rather than reading them. There is no clock anywhere in the package —
`now()` is chrono-nv's, which depends on this one and declares its own
effects.

calendar-nv is the only dependency, and it is not optional. The
conversion this package exists for has a civil date-time on one side of
it, and a package that declared its own would be declaring a second
`CivilDateTime` that no calendar-nv function accepts — public type
identity is by name across the whole assembly, so two spellings of a
date are two types a consumer cannot pass between.

What the dependency buys is the composition the plan's row asks for —
*the tzdata rules as data; calendar-nv applies them*:

```novo ignore
// "Same time tomorrow" — added in LOCAL time, then resolved.
let tomorrow = arith.add_days(today, 1)
let when = tzlocal.resolve(zone, civil.datetime(tomorrow, at))
```

That order is the whole point. Adding a day in local time and then
resolving is what a person means; adding 86400 seconds to an instant is
what a machine means, and across a daylight-saving change the two
differ by an hour. Keeping the arithmetic in calendar-nv and the
resolution here is what makes the difference visible in the code.

## Seconds east of UTC, everywhere

Berlin in winter is `3600`. Kolkata is `19800`. New York in winter is
`-18000`. There is one convention in this package and no second one.

The POSIX TZ string writes the opposite sign — `CET-1` means one hour
*east*, because the number is read as what to add to local time to get
UTC — and `tzposix.parse` flips it once, at the boundary, so nothing
downstream has to remember which way round it was.

## Where the names come from, and the ones that were taken

`Tz` prefixes every public type, because the short names were gone: the
standard library declares `struct Tz` and `struct Zoned` in `std.time`,
and `Date`, `Duration` and `Instant` besides. Every enum variant is
prefixed too — `TzLocalGap`, `TzPickLater`, `TzifTruncated` — because a
variant is constructed by name and a bare `Gap` would collide with the
first other package to want one.

The module names echo unicode-nv on purpose: `data_full()`,
`data_compact()`, `data_from_pack()` and `pack_bytes()` are that
package's arrangement for the same problem, which is an embedded table
that a caller sometimes wants to supply themselves. A reader who knows
one knows this one.

## The reference implementation

chrono-tz and Python's `zoneinfo`, with the IANA database itself as the
source of both the data and the test vectors. `zdump -v` is the oracle:
every instant, offset and abbreviation in `tests/` is what it prints
for the named zone under tzdata 2025b.

Four zones carry the cases that break implementations, and all four are
in the suite: Europe/Berlin for an ordinary rule, Asia/Kolkata for a
half-hour offset and no daylight saving, Australia/Lord_Howe for a
**thirty-minute** saving, and Pacific/Apia for 2011-12-30 — the day
Samoa skipped entirely when it crossed the date line, which is a gap
86400 seconds wide.

## Status

**NOT IMPLEMENTED — interface only.** `0.0.1`, `stability = "draft"`,
recorded `implemented = false` on the registry. The first
implementation is the `0.1.0` published over it.

```
novo pkg build     # clean: the signatures type-check and the rows fit
novo test          # red: every body is a todo()
```
