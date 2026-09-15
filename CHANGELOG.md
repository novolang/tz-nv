# Changelog

All notable changes to tz-nv are recorded here. The format is
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
package follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
with the pre-1.0 rule that a breaking change bumps the MINOR number.

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
