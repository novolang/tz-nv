# tz-nv

The [IANA Time Zone Database](https://www.iana.org/time-zones), also
called tzdata, is the record of what the clocks have read in every
inhabited place on earth since the 1880s. This package is that database
as data a novo-lang program holds, together with the two conversions a
program needs: a UTC instant to a wall-clock time, and a wall-clock
time back to the instants it could mean. It also reads the system's own
zone files, whose format is
[RFC 8536](https://www.rfc-editor.org/rfc/rfc8536), and the POSIX `TZ`
string of [POSIX.1](https://pubs.opengroup.org/onlinepubs/9699919799/basedefs/V1_chap08.html)
section 8.3. [cron-nv](https://novo-lang.org/packages/cron-nv) is built
on it.

**Status: NOT IMPLEMENTED — interface only.** Every function is declared
with its full signature, but every body is a `todo()` that panics when
called. The package is published so its design can be reviewed and
depended on before it is implemented. Version 0.1.0 will be the first
working release.

## What it is

A **time zone** is a step function from instants to offsets. Give it a
UTC second and it answers how far east of UTC the wall clocks were,
what people called that offset, and whether daylight saving was in
force. That direction always has exactly one answer.

The inverse direction does not. A **wall-clock time** is what a clock
on a wall shows, with no offset attached. Twice a year, in every zone
that observes daylight saving, one of three things is true of a wall
time somebody typed.

| The case | What it means | Example |
| --- | --- | --- |
| Unique | one offset, one instant | the ordinary case |
| Ambiguous | the hour ran twice, an hour apart | 2026-10-25T02:30 in Berlin |
| Gap | the hour never happened | 2026-03-29T02:30 in Berlin |

`tzlocal.resolve` answers all three as data, in the `TzLocal` enum, so
the caller chooses. `tzlocal.to_local` goes the other way and cannot
fail.

An **offset** here is always a number of **seconds east of UTC**.
There is one convention in this package and no second one.

| Place and season | Offset |
| --- | --- |
| Berlin in winter | 3600 |
| Berlin in summer | 7200 |
| Kolkata, all year | 19 800 |
| New York in winter | -18 000 |
| Lord Howe Island's daylight saving | 1 800, not 3 600 |
| The gap Samoa skipped on 2011-12-30 | 86 400 |

A **transition** is one change of offset: when it happened, and what
the offset was on each side. A zone's **transition table** is the list
of them the database records. The table ends, because the IANA files
stop in 2037, so every modern zone file also carries a **POSIX footer
rule**: a forty-byte string such as `CET-1CEST,M3.5.0,M10.5.0/3` that
says what the rule becomes afterwards. A zone answers from its table
where the table reaches and from its footer past the end of it, and a
caller need not know which answered.

A **link** is an alternative spelling of a zone name. `US/Eastern` is a
link to the canonical name `America/New_York`.

The database is compiled into this package as a byte array. No function
here opens a file, reads an environment variable or consults a clock.
Two packs are bundled.

| Pack | Size | What it holds |
| --- | --- | --- |
| `data_compact()` | about 96 KB | 340 canonical zones, 250 links, transitions from 1970 to 2038, every footer rule |
| `data_full()` | about 310 KB | the same zones with the whole recorded history, back to the 1880s |

Those two sizes are what the design is written to. Nothing has been
compiled yet, so they are targets and not measurements, and the release
that implements the package reports what they came out at.

Every public type is prefixed `Tz`, and every enum variant is prefixed
too. The standard library declares `Tz` and `Zoned` in `std.time`, and
`Date`, `Duration` and `Instant` besides, so the short names are not
available.

| Name | Value |
| --- | --- |
| tzdata release the packs are compiled from | `2025b` |
| First bytes of a pack | `NVTZ1` |
| Pack layout version | 1 |
| TZif versions read | 1, 2, 3 and 4 |
| First bytes of a TZif file | `TZif` |

## Install

```
novo pkg add tz-nv
```

## Example

```novo
use iso8601
use tzdata
use tzlocal

// The UTC second a meeting happens at, from the wall time a person
// typed and the zone they are in.
fn meeting_instant(zone_name: Str, typed: Str) -> Result<Int, Str>
    // The bundled database. No file is opened and no clock is read.
    let db = tzdata.data_compact()

    match tzdata.zone(db, zone_name)
        Err(_) => Err("no such zone")
        Ok(z)  =>
            match iso8601.parse_datetime(typed)
                Err(_) => Err("not a date-time")
                Ok(dt) =>
                    // What that wall time means in the zone. Twice a
                    // year it means two instants, or none at all.
                    match tzlocal.resolve(z, dt)
                        // The ordinary case: one offset, one instant.
                        TzLocalUnique(off) =>
                            Ok(tzlocal.epoch_second(dt, off.total_seconds))
                        // The clocks went back, so this hour ran twice.
                        TzLocalAmbiguous(_, _) => Err("that hour happened twice")
                        // The clocks went forward over this hour.
                        TzLocalGap(_, _, _)    => Err("the clocks skipped that hour")

fn main() [io]
    match meeting_instant("Europe/Berlin", "2026-06-01T09:00:00")
        Ok(s)  => println("${s}")
        Err(m) => println(m)
```

Build and test with `novo pkg build` and `novo test`. Today `novo test`
fails on purpose: every test reaches a
`not implemented: tz-nv.<module>.<fn>` panic. The tests are the
specification the implementation will have to satisfy.

## What the package contains

| Module | Contents |
| --- | --- |
| `tzdata` | The compiled database: the two bundled packs, a pack the caller supplies, the name lookup, the links, and the country and coordinate tables. |
| `tzzone` | One zone, and the questions asked at a UTC instant: the offset, the abbreviation, daylight saving, and the transitions either side. |
| `tzlocal` | The two conversions: an instant to a wall-clock time, and a wall-clock time to the instants it could mean, with the policy that picks between them. |
| `tzposix` | The POSIX `TZ` string: parsing it, writing it, and the rule arithmetic that answers an offset from one without a database. |
| `tzif` | The RFC 8536 file format, parsed from bytes the caller supplies, and written back out. |
| `tzerr` | The ten reasons a lookup, a pack, a TZ string or a TZif file could not be read, and the byte offset of the one that stopped a parse. |

## How to choose an entry point

There are three places a zone can come from.

**`tzdata.data_compact()` is the default.** Every timestamp a service
will see is inside its range, and it is the smaller of the two bundled
packs. Take `data_full()` only when timestamps from before 1970 are
actually converted.

**`tzdata.data_from_pack` takes a pack the caller built.** Use it to
pin one tzdata release for a year, or to carry only the twelve zones
your customers are in. Reading it declares no effects, because the
bytes arrive as an argument.

**`tzif.parse_zone` reads the system's own file.** Use it when the
program must agree with `date(1)` on the same machine, when a container
image pins its own zoneinfo, or when a government moved a zone since
this package's last release. Opening the file is the caller's work and
the caller's `[fs]`.

There are two ways to answer a question about an offset.

**`tzzone` answers from a zone.** It needs a database and a heap.

**`tzposix` answers from a forty-byte rule.** It needs neither. See
"Running on a microcontroller".

## The rules a user needs

1. **Every offset in this package is seconds east of UTC.** Berlin in
   winter is 3600. There is no second convention and no function that
   takes minutes.
2. **The POSIX `TZ` string writes the opposite sign, and `tzposix.parse`
   flips it once.** `CET-1` means one hour *east*, because POSIX.1
   section 8.3 reads the number as what to add to local time to get
   UTC. Nothing downstream of the parser has to remember that.
3. **Converting a wall-clock time to an instant is not a function.**
   `tzlocal.resolve` answers `TzLocalUnique`, `TzLocalAmbiguous` or
   `TzLocalGap`. A caller must handle all three.
4. **Converting an instant to a wall-clock time cannot fail.**
   `tzlocal.to_local` answers a `CivilDateTime` with no `Result` and no
   enum, because every UTC instant has exactly one wall time in a zone.
5. **`tzlocal.to_utc` takes the policy as an argument.** The table below
   is what each policy does. Only `TzPickReject` ever produces an
   `Err`; the other three cannot.

   | `TzPick` | Ambiguous | Gap |
   | --- | --- | --- |
   | `TzPickEarlier` | the earlier instant | the instant before the jump |
   | `TzPickLater` | the later instant | the instant after the jump |
   | `TzPickShiftForward` | the earlier instant | 02:30 becomes 03:30 |
   | `TzPickReject` | `Err` | `Err` |

6. **A gap is not always an hour.** Lord Howe Island's is 1 800 seconds
   and Samoa's skip of 2011-12-30 was 86 400 seconds wide, a whole day
   with no wall time in it. `TzLocalGap` carries the width, so read it
   rather than assuming.
7. **Zone lookup is case-sensitive.** `"europe/berlin"` is
   `TzUnknownZone`, because IANA's own names are case-sensitive and a
   library that folded case would accept names no other implementation
   accepts.
8. **Store the canonical name, not a link.** `tzdata.canonical_name`
   turns `"US/Eastern"` into `"America/New_York"`. IANA may stop
   publishing a link, and a configuration file holding one stops
   working that day. `tzdata.names_for` answers the reverse, for a
   migration.
9. **Add days in local time, then resolve.** `civil.add_days(d, 1)`
   followed by `tzlocal.resolve(z, dt)` is what a person means by "same
   time tomorrow". Adding 86 400 seconds to an instant is what a
   machine means, and across a daylight-saving change the two differ by
   an hour.
10. **Ask `tzzone.table_covers` when the answer must be a record rather
    than an extrapolation.** Past the table's end the footer rule
    answers. Past the table's end with no footer rule, the last
    transition's offset answers, and `table_covers` is how a caller
    finds out that is what happened.
11. **A version-2-or-later TZif file is read from its second data
    block, always.** The first block is the 32-bit original, kept for
    compatibility (RFC 8536 section 3.1 carries the version byte).
    Reading the first block is how an implementation ends up believing
    time stops in 2038.
12. **Leap seconds are read and never applied.** `tzif.leap_seconds`
    answers the records in the file, because a caller doing TAI
    conversion needs them. No conversion here consults them, because
    POSIX time does not count them.
13. **The footer extends a zone forward and never replaces one.**
    `TZ=EST5EDT` names a rule, not a place. There is no function here
    that guesses a rule for a zone name the database does not know.
14. **Week 5 in an `Mm.w.d` rule means the last such weekday in the
    month, not the fifth.** That single convention is why almost every
    real zone uses this form: "the last Sunday in October" has no fixed
    date. POSIX.1 section 8.3 defines it.
15. **A `Jn` rule never counts the 29th of February.** `J60` is the 1st
    of March in a leap year as well as in a common one.
16. **`tzdata.pack_bytes` writes a short prefix rather than failing.**
    The caller sizes the buffer with `pack_len`. A buffer that is too
    short gives a short write, because a package that aborted on a
    caller's arithmetic would be unusable in the firmware case it
    exists for.
17. **A refusal carries a byte offset, or -1 where there is no byte to
    point at.** `tzerr.offset_of` answers it, the same way
    calendar-nv's `calerror.offset_of` does. The `Error` trait that
    `Result<T, TzError>` requires is SPEC section 3.4.

## Running on a microcontroller

novo-lang lets a package state which of its modules can run on a device
with no heap allocator, and the compiler checks that claim on every
build. Here the claim covers seven functions in `tzposix` and nothing
else: `is_leap_year`, `rule_day_of_year`, `rule_second_of_year`,
`local_is_dst`, `offset_for`, `local_second_of_year` and `local_year`.
All seven are integer arithmetic over numbers the caller supplies.

The device this is for is a battery clock with a real-time clock chip
in it: a thermostat, a meter, a panel. It has no filesystem and no
network at the moment it needs the answer. It has one zone, known when
it was made, and forty bytes that describe it.

```text
CET-1CEST,M3.5.0,M10.5.0/3
```

Every number in that string is an `Int` in the firmware's own flash,
and turning it plus a clock reading into a local hour is five calls.
The device never parses the string: `tzposix.parse` holds a `Str` and
is the host's call, and the firmware's build or its provisioning step
hands the integers over.

`tests/embedded_probe.nv` is the claim as a program that either builds
or does not. It builds today:

```bash
novo build --target=nrf52-qemu tests/embedded_probe.nv
```

produces a Cortex-M4 executable.

**The other five modules are not covered, and neither are the two packs.**
`tzdata` holds the pack, `tzzone` and `tzif` build lists, and `tzlocal`
speaks calendar-nv's civil types, which do not build for a
microcontroller with no heap allocator either. 96 KB does not fit a
part with 32 KB of flash to spare.

One duplication follows, and it is the only one in the package.
`tzposix.is_leap_year` repeats calendar-nv's. A probe that called into
calendar-nv would not link. Every other date question in this package
goes to calendar-nv.

## What is not included

- **Reading a file.** `tzif` parses bytes the caller supplies. The
  `[fs]` belongs to whoever opened the file: chrono-nv on a server, a
  firmware image with the file in flash, a test with the bytes written
  in line.
- **A clock.** There is no `now` here.
  [chrono-nv](https://novo-lang.org/packages/chrono-nv) reads the
  machine.
- **Civil arithmetic.** Adding a day, finding the start of a month and
  formatting are all
  [calendar-nv](https://novo-lang.org/packages/calendar-nv)'s, and a
  caller composes the two. See rule 9 for why the order matters.
- **Leap-second-aware conversion.** The records are read and reported.
  Applying them would disagree with every clock a caller can read.
- **Case-insensitive or fuzzy zone lookup.** See rule 7.
- **A geocoder.** `tzdata.coordinates_of` answers the arc-minute
  position of a zone's principal city, which IANA ships so a picker can
  draw a pin. Reverse-looking a user's position through it is wrong by
  a country.
- **A zone guessed from a POSIX rule.** See rule 13.

## Related packages

- [calendar-nv](https://novo-lang.org/packages/calendar-nv) is civil
  dates, times and lengths of time with no clock and no zone. It is
  this package's only dependency, and it is not optional: the
  conversion this package exists for has a civil date-time on one side
  of it, and a second declaration of that type would be a type no
  calendar-nv function accepts.
- [chrono-nv](https://novo-lang.org/packages/chrono-nv) reads the
  machine: the wall clock, the monotonic clock and the host's own
  offset. Its `Offset` is a fixed number of minutes, and this package
  is what produces one for a named zone at a given instant.
- [cron-nv](https://novo-lang.org/packages/cron-nv) computes the next
  fire of a crontab expression in a zone, and it is built on this
  package for the daylight-saving rule.
- `std.time` in the standard library has a `Tz`, and it is a fixed
  number of minutes east of UTC. There is no zone-name lookup, no
  daylight saving and no historical offset table, so
  `Tz.parse("Europe/Copenhagen")` is `None` and a `+01:00` timestamp
  stays `+01:00` across a daylight-saving boundary. That is a decision
  rather than a gap, written up in `docs/stdlib/time.md` under
  "Timezone data". This package is the one that carries the database.

## Tests

```bash
novo test tests/tzdata_tests.nv      # 8 tests: the database, the lookup, a zone at an instant
novo test tests/tzlocal_tests.nv     # 8 tests: the conversion that is not a function, and TZif
novo test tests/tzposix_tests.nv     # 8 tests: the TZ string and the rule arithmetic
```

The reference implementations are chrono-tz and Python's `zoneinfo`,
with the IANA database itself as the source of both the data and the
vectors. `zdump -v` is the oracle: every instant, offset and
abbreviation in `tests/` is what it prints for the named zone under
tzdata 2025b. Every `TZ` string in `tests/tzposix_tests.nv` appears
verbatim in the footer of a file under `/usr/share/zoneinfo`, and the
expected answers are glibc's `tzset` and Go's `time`.

Four zones carry the cases that break implementations, and all four are
in the suite.

| Zone | What it is there for |
| --- | --- |
| Europe/Berlin | an ordinary European rule, and both the gap and the overlap |
| Asia/Kolkata | a half-hour offset with no daylight saving at all |
| Australia/Lord_Howe | a thirty-minute saving |
| Pacific/Apia | 2011-12-30, the day Samoa skipped crossing the date line |

The tests compile today and fail at run, each on the
`not implemented: tz-nv.<module>.<fn>` panic that is its body. That is
the expected state of an interface release. They turn green one at a
time as bodies land.

`tests/embedded_probe.nv` is not a test. It is the program that shows
the seven `tzposix` functions build for a microcontroller with no heap
allocator, and it builds. See "Running on a microcontroller".

## Implementation status

| Item | Implemented |
| --- | --- |
| `tzdata.TZ_DATA_RELEASE`, `.TZ_PACK_MAGIC`, `.TZ_PACK_FORMAT`, `tzif.TZIF_MAGIC` | yes (they are constants) |
| `tzdata.TzDb`, `tzzone.TzOffset`, `.TzTransition`, `.TzZone` | declared |
| `tzlocal.TzLocal`, `.TzPick`, `tzposix.TzPosixForm`, `.TzPosixDate`, `.TzPosixRule` | declared |
| `tzif.TzifHeader`, `.TzifData`, `.TzifLeap`, `tzerr.TzError` | declared |
| `tzdata.data_full`, `.data_compact`, `.data_from_pack`, `.pack_bytes`, `.pack_len`, `.data_version` | no |
| `tzdata.zone_names`, `.link_names`, `.has_zone`, `.canonical_name`, `.names_for`, `.zone` | no |
| `tzdata.countries_of`, `.zones_in_country`, `.coordinates_of` | no |
| `tzzone.zone_name`, `.offset_at`, `.offset_seconds_at`, `.abbrev_at`, `.is_dst_at` | no |
| `tzzone.transition_after`, `.transition_before`, `.transitions_between`, `.transition_at`, `.transition_count` | no |
| `tzzone.table_covers`, `.table_range`, `.table_horizon`, `.posix_rule`, `.offsets_of` | no |
| `tzzone.fixed`, `.utc`, `.from_posix`, `.is_fixed` | no |
| `tzlocal.to_local`, `.to_local_with_offset`, `.resolve`, `.to_utc`, `.instants_of` | no |
| `tzlocal.is_unique`, `.is_gap`, `.is_ambiguous`, `.offsets_of` | no |
| `tzlocal.epoch_second`, `.civil_at`, `.format_offset` | no |
| `tzposix.parse`, `.format`, `.fixed`, `.is_fixed` | no |
| `tzposix.offset_seconds_at`, `.is_dst_at`, `.abbrev_at`, `.next_change_after`, `.last_change_before` | no |
| `tzposix`'s seven device functions, listed under "Running on a microcontroller" | no |
| `tzif.parse`, `.parse_zone`, `.is_tzif`, `.version_of` | no |
| `tzif.read_header`, `.block_len`, `.data_block_offset`, `.footer_of`, `.leap_seconds` | no |
| `tzif.write_tzif`, `.write_len` | no |
| `tzerr.offset_of`, `.source_of`, `TzError.message` | no |

## Licence

Apache-2.0. See `LICENSE`.

<!-- docs/writing-a-readme.md is the style guide for this page. -->
