# Changelog

All notable changes to tz-nv are recorded here. The format is
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
package follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
with the pre-1.0 rule that a breaking change bumps the MINOR number.

## 0.1.0 — 2026-09-27

The IANA database as data, the two conversions between an instant and
a wall time, POSIX TZ rules, and TZif files, with tzdata 2026c
bundled.

- `tzdata.data_compact()` is 127 057 bytes and `data_full()` 233 354,
  each holding 447 zones and 151 links.  Each zone keeps its
  transitions up to the point its footer rule gives the rest, as
  `zic -b slim` does.  `tools/build_pack.py` makes both packs from the
  system's tzdata.
- `tzlocal.resolve` answers a gap and an overlap as `TzLocalGap` and
  `TzLocalAmbiguous`, found by searching two days either side of the
  wall time, so Samoa's missing day resolves.
- A TZif offset's saving is worked out from the standard offset next to
  it in the table, as Python's `zoneinfo` does.
- Both packs agree with Python's `zoneinfo` at 698 instants and 1 202
  wall times over twenty zones, written into
  `tests/zoneinfo_vectors_tests.nv` by `tools/zoneinfo_vectors.py`.
- `tests/embedded_probe.nv` builds `tzrule` for a Cortex-M4 and passes
  under QEMU, and `tests/alloc_scan.sh` finds no allocation in it.

Breaking changes against 0.0.2:

- The device half of `tzposix` is a module of its own, `tzrule`:
  `is_leap_year`, `rule_day_of_year`, `rule_second_of_year`,
  `local_is_dst`, `offset_for`, `local_second_of_year`, `local_year`
  and the enum `TzPosixForm`.  A device build compiles every function
  of each module it names for the device, and `tzposix` holds strings.
- Bytes are `Bytes` rather than `[u8]`: `tzdata.data_from_pack` and
  every function of `tzif` that reads a file.  `Bytes` is what a file
  read answers, and it has the big-endian readers a TZif file needs.
- `tzdata.pack_bytes(db)` and `tzif.write_tzif(z)` answer a new
  `Bytes` rather than writing into a buffer the caller passes.
- `TzError.TzifTruncated` carries the offset of the field that ran
  out, and a new variant, `TzLocalRefused`, is what `tzlocal.to_utc`
  answers under `TzPickReject`.  `tzerr.source_of` names it `"local"`.
- `tzdata.TZ_DATA_RELEASE` is `"2026c"`, the release the packs were
  compiled from.
- `TzDb` and `TzZone` carry their index and table as fields.
- `tzdata.coordinates_of` answers seconds of arc, which is the
  precision `zone1970.tab` gives.
- A `J60` rule date is day 60 of a leap year counting from zero, the
  1st of March.  The 0.0.2 tests expected 59.

## 0.0.2 — 2026-09-15

- README rewritten to the package README style guide (docs/writing-a-readme.md); no change to the interface.

## 0.0.1 — 2026-09-11

The **interface**: every signature and every effect row, and no bodies.
`stability = "draft"`, and the release is recorded `implemented = false`.

### Added

- `tzdata` — the compiled database as a value the package owns, with
  the compact and full packs sized in the README, a name lookup that
  resolves links to canonical zones, and `data_from_pack` so a program
  may supply its own tables.
- `tzzone` — one zone as a step function from instants to offsets:
  the offset, the abbreviation and the daylight flag at a UTC second,
  the transitions around it, and `table_covers` so a caller can tell a
  record from an extrapolation.
- `tzlocal` — `TzLocal`, `TzPick`, and the conversions both ways.
- `tzposix` — the `TZ` string parsed to a rule, and the rule arithmetic
  as integer algebra at `@tier(embedded)`.
- `tzif` — RFC 8536 versions 1 to 4, read from bytes the caller holds,
  and written back out into a buffer the caller owns.
- `tzerr` — one error type for four readers, every variant carrying a
  position.

### Known

- **`TzLocal` is the load-bearing interface.** Converting a local time
  to an instant is not a function: twice a year a wall time happened
  twice or never happened, and an API that answered `Int` answered by
  guessing.
- **The other direction cannot fail**, and the asymmetry is the design.
- **There is no clock.** `now()` is chrono-nv's, which depends on this.
- **The database is data**, and the README states what the two packs
  cost in kilobytes.
- **`@tier(embedded)` is claimed for `tzposix` and nothing else**, and
  `tests/embedded_probe.nv` builds it for a Cortex-M4. The pack does
  not fit a device and the claim does not pretend it does.
- **`tzif` reads bytes, never files**, which is what keeps a module
  named after a file format inside a `core` package.
- **Leap seconds are read and never applied.**
- **One dependency**, calendar-nv, and one deliberate duplication of it
  — `is_leap_year`, because the device probe cannot link into a package
  that makes no device claim.
