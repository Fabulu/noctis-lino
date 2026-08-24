# Noctis IV L.in.oleum port -- Windows and macOS prerelease

## Beta 24

Beta 24 adds the first native Apple-Silicon Noctis IV package. Download
`Noctis-IV-macos-arm64.zip` on an M-series Mac; the existing
`Noctis-IV-macos-x86_64.zip` remains available for Intel Macs and as the Rosetta
compatibility route. The new app is a thin arm64 build targeting macOS 11.0 or
newer. Both Mac packages are ad-hoc signed rather than Developer ID signed or
notarized, so macOS may require first-launch approval under System Settings,
Privacy & Security.

The generated game now comes from a compiler-owned AArch64 target instead of an
untracked CPU pack or translated x86 payload. The emitted operations required
by the shipped game cover integer, stack, control-flow, scalar binary32,
conversion, comparison, square-root, trigonometric, remainder, and arctangent
paths through a checked 32-bit Lino value ABI while retaining full-width host
pointers. The runtime reserves Darwin's x18, preserves the x19 through x25 Lino
register map, balances the link and frame registers, reloads the workspace after
host calls, keeps workspace memory non-executable, and seals generated code
read/execute-only.

The native Cocoa product includes display, resize, fullscreen, pointer and
keyboard input, focus handling, file services, screenshots, checkpoint saves,
and graceful window-close or App Quit handling. Dynamic Lino procedure values
are reconstructed as code-relative offsets from the full-width code origin,
which repairs the first full-game crash without scanning or rewriting generated
code. AudioQueue provides nonfatal stereo signed 16-bit PCM at 44,100 Hz. The
optional iGUI GlobalK service uses checked 24-unit names, exact 255-unit values,
atomic per-user files, and safe destruction; service families not reached by the
shipped Noctis source remain explicitly unsupported.

The Finder launcher installs mutable data under
`~/Library/Application Support/Noctis IV`, preserves regular player-owned
`STARMAP.BIN` and `GUIDE.BIN`, rejects non-regular mutable paths, and keeps the
nested game executable private to the app. Hosted Apple-Silicon execution proves
the compiler-owned fixture and full game above 4 GiB, exact Mach-O payload
boundaries, 16-KiB `__LINKEDIT` geometry, one exact ad-hoc signature suffix,
GlobalK write/read/destroy behavior, an actual Cocoa retrace, and normal raw and
extracted-package save/quit paths with a nonempty `CURRENT.LIN`.

Tagged releases now wait for Windows x86, macOS x86_64, and native macOS arm64
package jobs. Each platform publishes its ZIP, adjacent SHA-256 checksum, and
provenance record, for nine generated assets in total. The ARM64 provenance
separately binds the source revision, compiler, unsigned and signed executable
hashes, preserved Lino payload, launcher, manifest, architecture, deployment
target, bundle identity, release label, and archive.

Joris van de Donk's ARM64 `__PAGEZERO` analysis and x19-through-x25 register-map
work are credited in the replacement commits. The earlier prototype was not
merged because its forced mappings, pointer truncation, relocation, unwind,
code-patching, and build boundaries were unsafe; PR #10 was closed only after
the checked native product superseded it.

The macOS palette repair from PR #22 is included. It converts through
`FToIntChop` before clamping to `0..63`, avoiding uniform-white planet palettes
on macOS, and the Rosetta gate rejects any uniform palette before packaging.
The matched ROTOR IGNE native capture also corrected the Stardrifter exterior
camera. The source applies `user_beta + navigation_beta + 180`; omitting the
half-turn had moved a behind-camera companion into the viewport and generated a
false radial flare. The shipping renderer now retains the source half-turn, and
the pinned native indexed page, active palette, camera, clock, target-relative
position, and product diagnostics protect that negative visibility result.
Complete-page equality remains explicitly ungraded because the captured RAM had
already begun the following frame. A second native capture rotates only the
navigation angle and now pins the genuinely front-facing type-10 companion's
white corona and radial flare. The corrected product projects and renders that
companion, while its remaining corona brightness, palette, shape, and whole-page
gaps stay explicit rather than being hidden by the negative control.

The retained habitable and thin-atmosphere surface-sun BMP gates now distinguish
the final indexed contracts their capture provenance can actually support. A
canonical private-Windows trace places the thin scene's centre at index 126 on
the completed terrain/flare page; NIV+'s exact two post-render
`psmooth_64(adapted,160)` passes then change 22,537 indices and mix that centre
to 125 before the surrounding frame, while the next border pass leaves it
unchanged. The final low-six-bit centre therefore depends on live neighbouring
pixels that the timed native BMP did not retain and is no longer misgraded as a
same-state cross-product value. Exact active palette, every framebuffer palette
band, camera, flare gate/position and pre-smoothing sky-band admission sample,
exposure, distance, and ray remain graded. The separate ten-case primitive
flare oracle remains byte-exact to its native pages.

That product gate now covers seven landable surface types through fourteen
retained native BMP and surface records: five lunar type-1 cases, two dense-
atmosphere type-2 cases, habitable type 3, three rocky type-4 cases, thin-
atmosphere type 5, frozen type 7 around a class-1 star, and quartz type 8.
Habitable, thin, quartz, class-1/class-3/class-4/class-11 lunar, class-1/class-2
rocky, and class-8 dense authenticate positive radial flares; class-0
lunar/dense authenticate the `distance < 10*ray` lower
suppression gate; class-0 rocky/frozen authenticate the
`distance >= 1000*ray` upper gate. The certified quartz state keeps body 7
landed with power available at source time `1345761727`; the product matches the
exact projected centre `(161,101)` and final index 97, all 768 palette
components, and all 36,000 palette bands in the upper-sky crop, with
`51.5 <= 3923.7273 < 5150`. The additional rocky state keeps body 1 landed with
power 31505 at source time `1345723230`; around its class-1 star the product
matches centre `(161,72)`, final index 126, all 768 palette components, and all
27,000 upper-sky indices, with
`10 * 21.879 <= 245.8964 < 1000 * 21.879`. The additional lunar state keeps body
4 landed with power 19998 at source time `1345636830`; around the same class-1
star the product admits centre `(161,91)`, matches all 768 palette components
and all 64,000 final-page palette bands, and keeps
`10 * 21.879 <= 1757.4972 < 1000 * 21.879`. Native centre index 78 and product
index 80 remain in the same band while snapshot-time smoothing stays explicit.
SIENA V adds the orange class-3 primary at `(3363568,-4274032,-2404452)`: body
4 remains landed with power 20000 at source time `1345723230.090909`, and the
product matches centre `(161,71)` at exact index 73, all 768 palette components,
and all 37,800 indices in the `(40,10)..(309,149)` upper-sky crop. Its positive
interval is `10 * 27.753 <= 2365.4727 < 1000 * 27.753`; 128 palette-band
differences stay confined to snapshot-time terrain rows 157 through 185.
RIZI V adds the yellow-orange class-4 primary at `(3628560,-4254023,-915798)`:
body 4 remains landed with power 20000 at source time `1345723230.0`, and the
product retains all 768 palette components and all 29,700 palette bands in the
`(10,10)..(309,108)` upper-sky crop. Native/product centre indices 76/79 stay in
the same band at `(161,102)`. Its positive interval is
`10 * 19.877 <= 1438.3975 < 1000 * 19.877`; 489 palette-band differences stay
confined to snapshot-time horizon and terrain rows 109 through 159.
LUX I adds the cyan class-11 primary at `(4879984,-4603699,-1023471)`: body 0
remains landed with power 17482 at source time `1345723229.7777777`, and the
product matches centre `(161,100)` at exact index 105, all 768 palette
components, and all 64,000 final-page palette bands. Its positive interval is
`10 * 0.256 <= 23.0416 < 1000 * 0.256`; only 450 low-six-bit page values retain
the snapshot-time smoothing limit.
ROSVITA II adds the white class-2 primary at `(5800336,-4462999,-925592)`:
body 1 remains landed with power 17482 at source time `1345723229.7`, and the
product matches centre `(161,100)` at exact index 108, all 768 palette
components, and all 27,000 indices in the `(10,10)..(309,99)` upper-sky crop.
Its positive interval is `10 * 0.363 <= 61.7717 < 1000 * 0.363`; 1,081
palette-band differences stay confined to snapshot-time horizon rows 115
through 123.
The additional dense state keeps body 1 of the class-8 system
`(-1996240944,72703,944799)` landed with power 19998 at source time
`1345636830`; the product admits centre `(161,85)`, matches all 64,000
final-page palette bands, and keeps
`10 * 6.505 <= 129.4516 < 1000 * 6.505`. Native centre index 60 and product
index 59 remain in the same band. Authority remains artifact-specific:
habitable, thin, both dense cases, frozen, and class-1/class-11 lunar require all
64,000 palette-band assignments; the lower-gate lunar case, class-3 lunar, the
three rocky cases, and frozen additionally require exact 36,000-, 37,800-,
27,000-, 27,000-, 27,000-, and 36,000-index upper-sky crops; class-4 lunar and
quartz require 29,700- and 36,000-pixel upper-sky palette-band crops,
respectively, and quartz also requires its exact centre index. All active
palettes are exact except the two dense captures whose easing-dependent
components remain informational. The native Apple-Silicon job rebuilds and grades all fourteen
checkpoints independently with their case-specific clocks and retains their
product diagnostics.

A paired IDEAL capture extends that correction to a class-0 primary and type-1
orbital target. At matched clock, camera, radius, distance, and Stardrifter
position, the product retains the native exterior globe silhouette and all
18,000 native palette-band assignments where the turned camera sees the primary
corona and rays through the Stardrifter interior. The gallery's eleven generic
orbital fixtures now negate their target-local offsets for the restored source
half-turn while preserving their authored cockpit axis, and the capture tool
accepts complete exact local X/Y/Z overrides for matched native poses. A third
sync-0 IDEAL view now pins a genuine primary-beside-globe composition through
the Stardrifter: all 4,000 primary-window pixels retain the exact native palette
band and brightness classification, while the product's dark lunar mask differs
only at 99 bounded limb pixels. A fourth matched IDEAL capture pins the stable
Stardrifter roof branch at `(0,-750,-1900)`: the native BMP exactly retains its
frozen 64,000-byte framebuffer, and the product preserves 59,804 exact page
indices plus bounded upper-cupola and hull palette-band geometry. That retained
pre-repair checkpoint also exposed its brightness and 241 active-palette
component differences rather than treating them as exact lighting. Complete-page and palette equality remain
informational under the retained adjacent-frame authority limits. An additional
one-unit pair now pins the strict source `pos_y < -500` cupola transition: the
`-500` frame retains interior status, target telemetry, and the two fixed upper
target-label rows, while `-501` redraws the upper cupola after the hull and
returns before those details. The product selects the same branch, retains
61,619 native indices in the just-outside view, and exactly matches the
4,620-pixel roof telemetry crop. The just-inside path restores the source-shaped,
two-decimal `L.Y.` and `DYAMS` range rows plus the native-ordered 24-character
star and selected-body labels. Live catalogue names produce `IDEAL S00` and
`CASSANI P01` in the retained fixture; source-authentic unknown-star, planet, and
moon forms cover misses. The lower environmental fields now update in every
Stardrifter view at the source quarter, twentieth, fiftieth, and hundredth
smoothing rates; drawing retains the source `draw_hud` gate, value formats, and
spacing. All four visor lamps also use the source-ordered, in-place radius-five
low-six-bit diffusion while preserving their palette bands. The ordinary inside
and roof product captures each match the native 28-by-5 `GRAVITY`/lower-left-lamp
crop byte-for-byte; its palette-independent mask contains the same exact 69
pixels in both modes. This deliberately scoped runtime contract does not claim
that the differing native and product numerical histories make the complete row
byte-identical. The base palette also stops inventing a warm ramp for an absent
moon. In the retained planet state, source `surface()` owns only band 192; fresh
inside and roof captures therefore leave band 128 black and match all 192 native
moon-band components exactly. This removes 187 of the former 241 complete-palette
mismatches, leaving 54 components tied to still-unretained palette-easing state.
At the retained interior/primary-flare camera, a current private-desktop
`-OpenHud` capture now uses native fixed-chase sync 1 and visibly retains
`TRACKING`; its compensated authored Z converges to the exact staged
`0.01283555` target distance. Switching from the earlier sync-0 probe changes
491 complete-page indices but zero pixels in the graded crop, and leaves the
1,190 complete-page palette-band mismatches unchanged. The capture matches all
18,000 native palette bands and 17,395 exact indices in that crop. The
native-page/native-palette, native-page/product-palette,
product-page/native-palette, and product-page/product-palette brightness counts
are respectively 8,338, 8,338, 8,215, and 8,215. Thus the current 123-pixel gap
comes entirely from 605 same-band indexed-page differences; the current palette
mismatch and index 77 contribute zero in this crop. Upper and lower projected
HUD rows account for 460 differences and 66 deficit pixels, with 367 product
values equal to native X-1; this is retained for the cross-host font-fidelity
work. The remaining 145 differences and 57 deficit pixels occupy right-fixture
and central-flare regions. Source/port ordering, clipping, spoke arithmetic, and
two-pass smoothing expose no active divergence there, while native pass-level
intermediates were not retained, so no raster repair is claimed. Repeated
launches retain identical scoped indexed rasters despite palette variation, so
those rasters—not unstable product brightness—grade the repair. A new opt-in
private-desktop lift trace now records the post-render, post-restraint scalar
state and complete 64,000-byte indexed page on each authoritative simulation
tick while remaining inert during ordinary launches. The production game
retains all eight source ascent states from impulse `-100` through `y=-750`, all
twelve automatic-return states from `+75` through the exact `y=0` deck clamp,
the strict `y < -500` roof switch in both directions, and the source-ordered
camera-pitch and forward-restraint changes. Every one of the 20 states produces
a distinct complete indexed page even though presentation continues at 60 Hz.
Native direct star/body editing now owns character
input ahead of all other hotkeys and preserves source uppercase conversion,
Backspace, physical-Escape cancellation and held-key ownership, Return, the
20-byte cap, exact 32-byte `STARMAP.BIN` appends, and byte-exact player-local
removal. A registered private-desktop runtime test exercises those rules without
touching the interactive desktop. Its 32-byte state diagnostic proves active
editor preconditions, held/released Escape-latch state, native `EXTANT` for
case-insensitive duplicates, and `DENIED` for consolidated-record removal. Across complete 64,000-byte indexed pages, a full modulo-32 blink cycle recurs
byte-for-byte, a distinct phase changes only the 34-pixel shader-zero
underscore, and a same-phase invisible trailing-space edit translates only its
72 old/new raster pixels by one fixed label position. The HUD projector now
skips spaces and out-of-atlas bytes instead of redrawing its previous glyph
through padded cells. Exact projected glyph raster across hosts, complete
interior lighting, the remaining unretained palette-easing state, and whole-row
numerical environmental-state equality remain explicit rather than being claimed
as complete interior parity.

This release does not claim complete NIVGEN parity: the same 22 retained
XENOFELYS landed-artifact discrepancies described in Beta 23 remain deferred
pending the exact unpublished harness or paired upstream regeneration.

## Beta 23

Beta 23 completes the portable floating-point repair and raises the measured
production NIVGEN score from 38,893/49,823 to 49,801/49,823 exact authoritative
fields. Complete-row agreement rises from 426/4,546 to 4,540/4,546. Types 0, 6,
7, 8, 9, and 10 are exact, as are all comparable orbital surfaces, atmospheres,
and palettes. The score comes from retained, non-overlapping runs of all 4,546
comparable rows in the canonical 5,188-row snapshot rather than a sampled or
weakened comparison.

Historical positive fractional crater power now runs as ordinary portable Lino
integer code with the original x87 significand and spill behavior. An independent
instruction-level witness, exact soft-stack invariants, representative production
maps, and a complete model audit of all 9,564,210 reachable fractional crater
pairs guard that repair. Exact zero-numerator handling also closes the related
geometry and seed conversion boundaries without adding native game kernels or
planet-specific answers.

Public NIVGEN generation now uses request-scoped binary64 boundaries for orbital
geometry and atmosphere painting and preserves the exact doubled half-degree seed
threshold. The desktop game keeps its historical precision schedule. Generated
Windows executables receive a fail-closed post-link `FCWEXT=133Fh` patch, while
Linux and macOS runtimes install the same fixed environment below the language
boundary. Production game and generator source now have zero raw target blocks;
tagged Intel and Rosetta builds probe the live control word before packaging.

The remaining 22 nonmatching fields are landed outputs confined to XENOFELYS
bodies 4, 5, 8, 9, 10, and 11. They are retained caller/artifact discrepancies,
not omitted comparisons: two native NIV+ captures agree with current source-shaped
values at disputed boundaries, including an all-zero body-10 sky where the
retained artifact contains a later changed byte. The original SheetBot caller
ran five separate DOS programs per body in shared 12-body DOSBox chunks, and a
control proves that reused DOS allocations can retain a preceding process's
payload. The exact unpublished harness or a paired shared-session/clean-session
regeneration is still needed to identify that historical capture path. This beta
does not claim 49,823/49,823 parity and does not patch expected hashes or output
bytes.

The tagged release still builds both desktop packages from source, checks internal
manifests, and publishes each archive beside its SHA-256 checksum and provenance
record. The release body is extracted from this Beta 23 section only.

## Beta 22

Beta 22 adds the first packaged macOS game to the tagged release graph. The
Finder application targets x86_64 and macOS 10.15 or newer: it runs directly on
Intel Macs and through Rosetta 2 on Apple Silicon. The native Cocoa host provides
a resizable window, fullscreen, logical pointer mapping, clipboard and text
input, stable framebuffer snapshots, and AudioToolbox stereo PCM. No XQuartz is
required. Native ARM64 remains future work.

The macOS executable is built from tagged Lino source rather than checked in.
Apple Silicon first builds unsigned headless and Cocoa runtimes and records the
actual host/toolchain provenance. Ubuntu verifies those bytes, reaches the same
byte-identical `compiler114m` self-hosting fixpoint used by the Windows release,
audits the x64 CPU pack, and compiles dedicated NIVTEST and production game
images. Apple Silicon then runs the tagged generator through Rosetta and requires
all seven authoritative outputs: surface, atmosphere, palette, heightmap, object
chart, surface texture, and sky. The fixed fixture matches 7/7 exactly; a process
that merely launches cannot pass this gate.

The runtime no longer depends on a fixed low mapping that can replace an existing
region. Code and workspace are mapped below Lino's 32-bit address ceiling,
out-of-range results are rejected, and workspace growth maps, copies, clears,
and unmaps safely. The last Rosetta numerical fault was below game source in the
x64 CPU pack: an `add rsp,4` restore after `sahf` destroyed the floating compare
flags before a branch. Flag-preserving LEA restores now cover all 792 floating
branch records and 1,236 restore sites, guarded by a deterministic pack audit.

Historical Lino executables append initialized workspace, machine code, and an
intentional trailer beyond the runtime's original `__LINKEDIT`. Before signing,
the package tool parses the complete Mach-O and `LNLMInit`, requires the expected
runtime boundary and spare load-command slot, and extends only
`__LINKEDIT.filesize` and page-aligned `vmsize` over the exact unsigned image. It
proves every other byte unchanged. Apple codesign then adds one signature, and
post-sign validation requires both the signature and `__LINKEDIT` to end at EOF
while preserving the complete appended Lino payload byte-for-byte.

The nested game and outer app are ad-hoc signed and strictly verified before and
after ZIP extraction. They are not Developer ID signed or notarized, and hardened
runtime is not enabled. macOS may therefore require an explicit first-launch
approval under System Settings, Privacy & Security. This limitation is stated in
the packaged README rather than hidden behind the successful signature checks.

A Finder-safe launcher stores changing files under
`~/Library/Application Support/Noctis IV`. It repairs missing or byte-different
immutable assets while preserving regular player-owned `STARMAP.BIN` and
`GUIDE.BIN`, and rejects mutable seed paths that are directories, symlinks, or
other non-regular objects. Window close and AppKit Quit repeatedly provide full
Escape press/release intervals until fullscreen or a modal has been left and the
game reaches its ordinary save/audio/cleanup path. The extracted-package smoke
requires the first real Cocoa retrace, that graceful quit marker, and a nonempty
`CURRENT.LIN`.

Both desktop packages now carry internal SHA-256 manifests and are published
beside archive checksums and provenance records. The macOS record separately
binds the runtimes, compiler, original compiler output, normalized unsigned
Mach-O, unchanged appended Lino payload, signed executable, launcher, manifest,
NIVTEST evidence, release label, and archive. Tagged publication waits for both
complete Windows and macOS graphs, so a platform failure cannot create a partial
six-asset prerelease.

## Beta 21

Beta 21 restores a reproducible hosted source build for the downloadable Windows
package. GitHub Actions now starts with the protected historical Linux compiler,
runs it under an explicit executable-heap compatibility boundary, bootstraps the
extended compiler from the tracked `compiler114m` source, proves a byte-identical
self-hosting fixpoint, and then compiles the production `vhgame.txt` graph for
`win32/i386m`. The resulting 594,246-byte, four-section i386 PE is no longer a
checked-in executable repackaged by CI.

Build provenance is recorded where the Linux job consumes the bytes, before any
Windows checkout can convert text line endings. The release record identifies
the commit, root game source, both compilation scripts, dependency installer,
protected bootstrap compiler, compiler source and its two libraries, bootstrap
and target CPU/SYS packs, generated compiler, target, and final executable by
SHA-256. The Windows packaging job verifies the transferred executable and
compiler against that record, preserves it unchanged, emits a ZIP checksum, and
retains the per-file `MANIFEST.sha256` inside the archive. The latest snapshot
was independently unpacked and verified across all 13 payload entries before
this tag was prepared.

The game source also crosses the main portability milestone begun after beta 20:
ordinary rendering, terrain, geometry, stellar-seed, surface-seed, conversion,
and scalar floating-point paths no longer depend on hidden native game kernels.
Exact square root and the portable software floating-point ABI now live in Lino
source, while platform implementation remains below the language boundary. A
missing one-bit mask in software-x87 subtraction normalization was found at the
raw eccentricity-word boundary and repaired; the production NIVGEN fixture now
self-checks the quotient, subtraction, and binary64 store before generation.
Focused gameplay regression, all seven authoritative Windows NIVGEN outputs,
and the hosted source build pass at the tagged source revision.

The x86_64 macOS runtime now allocates code and workspace below 4 GB without
`MAP_FIXED`, rejects high mappings instead of truncating pointers, and grows an
`mmap` workspace by mapping, copying, clearing, and unmapping rather than passing
it to `realloc`. Both Cocoa and headless runtimes build on Intel macOS, and the
production generator executes to completion under Rosetta on Apple Silicon.
Its raw orbital geometry, seed value, and new portable-FP self-check are exact.
A macOS package is deliberately not attached yet: the exactness gate still finds
an independent downstream divergence in surface, atmosphere, and palette output,
while heightmap, object chart, surface texture, and sky remain exact. The gate is
being fixed rather than weakening its Windows/NIV+ reference hashes.

## Beta 20

Beta 20 removes the remaining multi-second interpreter tax from cold planetary
landings without changing generated terrain. Exact native kernels now perform
the shared 40,000-cell terrain fill, in-place smoothing, signed level pass,
fast-noise pass, and the corresponding 65,535-cell texture fill and smoothing
paths. Borland's signed random stream, the fast generator, draw counts, FNV
ledgers, traversal directions, and in-place write order remain intact.

`round_hill` and `std_crater` now share an exact generation-stamped radial
profile cache. Habitable asterism rays retain one binary64 sine and cosine pair
per ray instead of recomputing the same pair for every radial pixel. A fixed
habitable scene reached its first capturable frame in 3.17 seconds instead of
17.18 seconds. A fresh sweep placed all seven landable planet classes between
2.72 and 3.23 seconds on the same host. The focused 160,016-byte painter result
and both RNG hashes stayed identical, and the production clean-return fixture
still matches NIV+ across all 40,000 height bytes and all 65,532 deterministic
texture bytes.

Arbitrary resized windows now publish scaled pixels directly to both game
layers, removing a complete fitted-region copy. Exact native flare spans remove
the per-pixel interpreted walk from surface and Stardrifter sun beams while
retaining the established flare probe hashes. Gameplay regression and Windows
package checks passed for each merged optimization.

## Beta 19

Beta 19 makes the current production generator usable by the public NIVGEN
worker on macOS. The new x86_64 runtime executes compiled Lino programs through
a real headless host instead of returning from a placeholder process. A fresh
live-oracle smoke of the current runner matched all 11 available hashes for the
sampled planet, including both landed surface textures. The public sheet still
showed two surface-texture errors from its older deployed worker at release
time; rebuilding that worker from beta 19 should remove that discrepancy.

Planet generation also restores NIV+'s type-1 crater height literal and keeps
the original sequential orbital viewpoint state between bodies. These are
algorithmic fixes, not fixture-specific answers. The committed Windows game
executable has been rebuilt from the same current source before publication.

The macOS x86_64 host now uses native Cocoa without XQuartz. Its window resizes
the logical framebuffer, maps pointer coordinates back into Lino space, enters
native fullscreen through the original iGUI command, and consumes Escape once
to return to the window. The same runtime can be built without a display for
NIVGEN and other deterministic jobs. The x64 compiler pack also repairs a
push-from-memory code-generation fault and keeps the host boolean ABI stable.

Linux directory enumeration now uses a raw `getdents64` path that works under
the supported qemu-user environment. The focused macOS Cocoa and headless
runtime checks, gameplay regression, and Windows package checks passed before
merge. ARM64 remains a separate unfinished port and is not claimed here.

## Beta 18

Beta 18 makes the production Lino generator deployable to the public NIVGEN
worker. The SheetBot-facing wrapper now builds and runs the same current
`vhgame.txt` generation graph used by the game, including the exact benchmark
hash boundaries and arbitrary landed coordinates. Moon generation restores the
original two-pass surface-buffer history instead of treating the second pass as
an isolated allocation. That closes the observed moon palette mismatch without
using fixture keys or uninitialized host memory.

Fresh local replays against the live NIVGEN oracle add 40 planets and moons,
including arbitrary type-2 sites, with all 440 available hashes exact. The
previous 98-row leader-error set remains 1,078 for 1,078. The public Lino column
still reflects an older worker until it is rebuilt from this release, so these
figures describe the tagged production runner rather than the stale deployment.

The desktop renderer also restores two source details around the Stardrifter.
The physical onboard font now uses NIV+'s fixed 512-by-576 texture basis and
46-unit information-row spacing, removing giant shredded cockpit lettering.
A complete native capsule-ascent oracle confirms that the brief withdrawal of
nearby terrain during takeoff occurs at the same source frames; long-distance
walking coverage remains tracked separately.

## Beta 17

Beta 17 restores several pieces of live Stardrifter and orbital rendering.
The exterior again follows the source composition order, its halogen flare uses
the correct camera and NIV+ projection, the hull respects the original near
plane, and white space effects advance on the source cadence without smearing
across later frames. Orbital planet surfaces remain resident across repeated
views, and checkpoint restore preserves the active ship palette and drive
state instead of silently recolouring the Stardrifter.

The desktop host now defaults to smooth 60 Hz presentation while retaining the
authoritative gameplay clock. Exact native paths cover Stardrifter page filters
and glyph setup, hot panel loading, terrain height sampling, starfield and
cupola batches, and the shared projection handoffs used by every planet class.
The pilot-font loader also recognizes and repairs a byte-reversed word stream,
which hardens lower-right status and GOES wall text on compatibility hosts.

Public NIVGEN work is now part of the production repository. The current Lino
generator matches all 1,078 original hashes in the saved 98-row subset where
the public Rust leader had errors. A second breadth point for each ordinary
planet type matches 110 of 110 hashes, and five type-10 companion rows match all
40 available landed hashes. The scorer follows the coordinates encoded in the
original artifact names, grades only fields with an oracle, accepts saved JSON
with a UTF-8 marker, and never retries an unavailable private host. These are
measured subsets, not a claim that the complete live corpus is finished.

This remains a prerelease. Full XQuartz font authentication, every iGUI window
action, and the JavaScript site's Visual Effects and GOES menu crashes remain
open. Those browser defects do not change the packaged Windows executable, but
they remain tracked rather than being hidden behind passing scripted smokes.

## Beta 16

Beta 16 fixes the malformed rainbow tree regression introduced by beta 15's
mapped-object rotation shortcut. A disposable historical bisect isolated the
first bad revision, and the unsafe rotation kernel has been removed while the
exact projection, facing, basis, gradient, edge, and raster fast paths remain.
The fixed tree page and exit state again match the NIV+ oracle hashes exactly.
Fresh habitable, close-tree, and hopper scenes render in 9.85, 10.88, and 9.25
ms respectively, each without the giant slabs or rainbow pixels.

Sun rendering now forms clipped framebuffer offsets directly and reuses the
source's chopped viewport coordinates instead of routing every pixel through
generic segment and floating-bound helpers. Flare spokes inline their exact
vertical and general brightening rules. The 13-case NIV+ matrix remains exact
across all 3,328,000 staged bytes for the white-disc, flare, smoothing, and
palette-mask checkpoints. The dense sun scene fell from roughly 13.5 to 10.5
ms render time, while the thin-atmosphere radial flare measured 6.32 ms at 61
FPS.

Mapped terrain and object setup also receives exact native vertex expansion,
foliage preparation, and edge submission. Together with the corrected tree
path, every staged planet class and the Stardrifter now stays below the 16.7 ms
render budget in the playable performance matrix. Public documentation is
shorter, uses more scannable bullets, describes the actual hosted and optional
self-hosted release paths accurately, and contains no em dash characters.

## Beta 15

Beta 15 removes another layer of interpreter overhead from the exact landed
renderer. Mapped triangles now close their duplicate vertex, project fixed
tree and object points, and compute all nine texture-gradient cross products
through bounded native kernels. The shared gradient path applies to every
landable planet class as well as mapped surface objects.

Close trees now prepare foliage points, polar vertices, leaf tips, terminal
leaf fans, branch angles, and recursive node restores without repeatedly
crossing the generic scalar-float and RNG helpers. The original unsigned draw
order, binary64 spill points, binary32 stores, chopped integer boundaries,
depth-first traversal, polygon order, and texture sampling remain unchanged.

The direct NIV+ tree probe retains its exact 256,000-byte framebuffer hash
`1D8120F3CF329067AEF24D4C2D5693F5694EE875AEA04759D533369DCA08F7E2`
and 40-byte exit-state hash
`FF664C8DE0D8E3B8A1C510E3877F6E27D834F8BBD395451E963AD39F0B41FD34`.
The release matrix passed 23 unchanged suites, and its one stale structural
tree assertion passed after being updated to recognize the new native loader.
A fresh playable close-tree capture rendered in 25.24 ms at 36 FPS; this
authored scene remains time-varying, so the fixed oracle is the fidelity gate.

## Beta 14

Beta 14 removes the remaining interpreter-heavy setup stages from the mapped
surface-object path. Tree branch and leaf polygons now perform facing,
rotation, projection, and the four-vertex texture basis in exact native x87
kernels. The original binary64 spill points, binary32 local stores,
nearest-even projection, near-plane decisions, polygon order, and texture
sampling remain unchanged.

Fully visible terrain and mapped polygons now populate their near-plane output
arrays with one bounded native bit-copy loop instead of twelve generic helper
calls per polygon. Clipped polygons retain the original generic clipper. This
shared change applies to every landable planet class as well as mapped surface
objects.

The NIV+-anchored tree probe retains its exact framebuffer and exit-state
hashes after every stage. The frozen raster/projection check retains 107 exact
pages, 5,028 exact span integers, 122 exact topology groups, and 222 exact
projected components. A fresh dense-atmosphere product capture remained smooth
at 61 FPS with 8.11 ms render time.

## Beta 13

Beta 13 removes another layer of interpreter overhead from the exact renderer.
Additive and halo polygon fills now execute their source-ordered neighbour
sampling and saturation loops natively. Surface foliage stamps keep the same
three fast-random draws and six-pixel write order in one bounded loop, while
render-only tree, bush, grass, and rock draws no longer pay for the generator
corpus hash ledger.

Terrain height interpolation retains both binary32 stores and the source chop
boundary in a fused x87 path. Integer object vertices now enter projection
slots through one exact `fild`, and every accepted terrain cell performs its
seeded shade draw without two extra interpreted calls. These paths apply to
all landable planet classes. Fresh fixed captures measured 7.57 ms for the
dense-atmosphere surface, 9.62 ms for the rocky surface, 11.60 ms for the
NIV+-matched giant-tree scene, and 4.52 ms for the Stardrifter renderer.

The 107-page raster corpus remains byte-identical, including counters and edge
state. The frozen production tree probe also retains its exact framebuffer and
exit-state hashes. The unusual orange crown and blue limbs in that authored
daylight state are confirmed by the direct NIV+ framebuffer and full 768-entry
palette oracle; the former rainbow spray defect remains absent.

## Beta 12

Beta 12 restores the original Stardrifter lift impulse and completes the first
long smooth-presentation cadence audit across walking, flight, focus loss, and
mode transitions. The optional presenter continues to target 60 Hz while game
state advances only on the original 18.206-Hz simulation ticks.

Matched NIV+ stage captures authenticate the dense- and thin-atmosphere sun
pipelines. The surface panorama no longer erases a rectangular edge area that
the native renderer leaves intact, making the pinned pre-sun, post-sun, and
palette-mask pages exact for those fixtures.

The release also accelerates arbitrary-window scaling, exact panorama turns,
surface-background regeneration, and the shared solid-polygon fill and edge
paths. Focused page and edge-state comparisons, including deliberately broken
negative controls, retain the established renderer output while removing the
repeated interpreted scans.

## Beta 11

Beta 11 hardens smooth presentation, preserves more NIV+ memory behavior, and
turns the public NIVGEN leaderboard into a practical accuracy target. A saved
first-page snapshot contains 98 rows where the current Rust leader reports at
least one error. L.in.oleum matches all 1,078 original hashes across those
rows, covering types 1, 2, 4, 5, 6, and 9, orbital output, and both landed
sites. Network access remains deliberately polite: an outage is observed once
and is never retried or polled until the service owner brings it back.

Two generator corrections close the last failures in that subset. Stellar
identity conversion now uses Borland's qword `__ftol` boundary before taking
the low seed bits. Surface crevasses now retain the source's unchecked
four-neighbour stores in explicitly modeled memory, including the rare south
edge spill through the far-heap header into the adjacent object chart.

The 60 Hz presenter now carries calibrated sub-millisecond cadence residue
while the authoritative game continues at 18.206 Hz. Nearby articulated fauna
builds polygon midpoints only after its final transform. Fresh sequential
captures measure 56 through 61 FPS across every landable planet class and 58
FPS in the Stardrifter, with the slowest measured surface render at 10.69 ms.

Native-backed lighting coverage now includes the dense atmosphere disc, the
lunar lower flare gate, and the exact active surface palette. The tree gallery
uses the final NIV+-matched production renderer, and the README has a shorter,
more readable build and play guide without em dashes.

## Beta 10 foundation

Beta 10 restores live, phase-dependent surface lighting and begins the
cross-planet sun-authenticity gallery with direct Borland-built NIV+ evidence.
The surface renderer no longer replaces a generated world's terminator,
dawn/dusk side, and exposure with the opening-system defaults. Solar distance
now comes from the body's current three-dimensional orbit rather than its
nominal radius, including the separate companion-owner rule.

Automated captures pin the source epoch explicitly and clamp authored surface
pitch to the port's playable `-44..44` degree range. This closes two misleading
oracle setups: NIV+ reloads time from the DOS clock during landed resume, and
its floating camera clamps at `44.9` degrees even when a saved pose asks for
more. Fixed-epoch native and product runs now agree on the lighting state for a
clear type-3 world, a type-5 thin-atmosphere world, an airless type-4 world,
and a frozen type-7 world around a distinct class-1 star.

Three reproducible gallery scenes document the resulting behavior. `thinsun`
shows the native radial flare over a teal atmosphere. `rockysun` and
`frozensun` show visible stellar discs with no radial beams because their live
distances exceed NIV+'s original `1000 * ray` gate. Correct suppression is part
of renderer fidelity. The README publishes all three production captures.

Surface galaxy stars now follow the source camera and coordinate schedule
instead of a quantized view cache. Fused exact x87 kernels recover the cost of
that correction while retaining the matched frozen-world points. Additional
exact globe and Stardrifter hull paths remove redundant scaling and scratch
copies across every orbital planet type and the vehicle exterior.

Live NIVGEN service work has resumed from one deliberate 2026-08-14 snapshot.
The public schema currently exposes original, Rust, and LR results but does not
yet expose L.in.oleum columns. Accuracy work uses the saved snapshot locally;
an unavailable host is recorded once and is never retried or polled.

The first-page accuracy sweep now covers all 98 rows on which the current Rust
leader reports an error. L.in.oleum matches all 1,078 scored NIV+ hashes across
types 1, 2, 4, 5, 6, and 9, including orbital output and both landed sites. The
last three random-site object charts exposed a source memory effect:
`felisian_srf_darkline()` bounds
its centre pixel but not its four neighbouring writes. A south-edge neighbour
can cross the 40,000-byte heightmap, pass through the 16-byte far-heap header,
and alter the adjacent object chart. The port now reproduces that bounded spill
inside its explicit framebuffer model, without using uninitialized host memory.

## Beta 9 foundation

Beta 9 completes the current native-matched companion-star checkpoint and
ships the latest exact terrain and presentation optimizations. Stationary
local-system rendering is active again, local tracking status survives the
renderer, and companion flare radius retains its source binary32 precision.
The complete 64,000-byte flare page matches direct Borland-built NIV+
framebuffer captures for real thin-atmosphere, quartz, and clear habitable
surface inputs. The opening Stardrifter star also matches at every staged
checkpoint: white core, radial flare, smoothing, and mask. Companion stars
restore `planets()`'s per-body fast-RNG seed and exact
`0.15 - fast_flandom() * 0.3` corona factor instead of using a fixed value.

The gallery tool now defaults to the game's own no-flash 320x200 snapshot path.
This captures the completed game frame directly and cannot include iGUI hover
balloons or desktop chrome. Explicit camera-distance, user-yaw, and navigation-
yaw controls support like-for-like native viewpoints, while a compact exit
trace records the selected body and companion vectors used by the live frame.

The surface weather sweep confirms the source gates between full flare, bare
sun, and storm suppression. Broad sun authenticity remains an open acceptance
item: every planet, atmosphere, star class, orbital configuration, and
Stardrifter transition still requires a matching native viewpoint before the
matrix can be called complete.

Timing protection now derives its safe sampling window from the live host
counter rate and rejects aliased deltas even under an artificial million-count
clock. The stale class-A renderer census is closed, and generated floating-point
helpers now reject unsafe integer conversions instead of silently weakening the
port's narrowing contract.

Live NIVGEN service integration is intentionally paused while the external
service is unavailable. Its local harness, protocol notes, and generator work
remain preserved, but this release does not poll, submit to, or claim a current
score from the service.

This release completes the playable Windows route from the Stardrifter through
galactic flight, local approach, capsule descent, surface exploration, and
automatic capsule return. It also repairs the final capsule coordinate-space
and timing failures found during live play, restores the historical
Suricrasian Cube, and retains the source-equivalent ship, terrain, devices,
GOES modules, persistence, presentation, and soundtrack systems established in
the earlier betas.

The README gallery refresh is complete. The LANE IV tree capture now aims at
the measured tree record itself from 45,000 units away. The previous checkpoint
faced north while its advertised tree was west of the camera, so the frame only
showed an unrelated foliage mass. The gallery also retains the distant whole
Suricrasian Cube and a close type-8 planet through the Stardrifter window after
a genuine fine-approach checkpoint. Separate, radius-matched fine-approach
frames now cover every orbital planet type, including internally hot type 0,
the large banded type 6, and a second milky type-8 world.

Tree recursion now retains the source binary32 coordinates, scale, spread,
width, peak, and root-height values. The earlier integer recursion changed the
fractional coordinate sum after the first limb, which changed every later node
seed and could explode a crown into rainbow polygons across the sky. The live
renderer now preserves the native branch and foliage topology and uses bounded
branch centrelines. The promoted tree frame contains no rainbow spray or slab.

The tree mapper now also restores the source's 256-scaled repeat dimensions,
four-byte Borland texture-window residue, right-to-left leaf-coordinate random
draws, binary32 leaf-tip projection, and buffer-relative foliage stamps. Limb
faces retain the source's 48-byte texture stride, while every leaf face uses
the same fixed texture window. With corrected native height input, the full
tree now differs from the NIV+ framebuffer at only 7 pixels out of 64,000:
one native-only edge pixel and six colour-value differences, with no Lino-only
pixels. With identical landed inputs, all 768 palette components match NIV+
exactly, including the unusual orange crown and blue limbs produced by this
particular daylight state.

The gallery tree has been recaptured from the final production renderer rather
than retaining the older pre-addressing frame. Its SHA-256 is
`e06a746f034c1025235e6a6f0c94d6db0968d0ccca01f7c5d6bae71c4e26dc15`.

The production NIVGEN harness now speaks the public command protocol, emits the
actual L.in.oleum orbital and landed buffers, and scores public sheet rows by
field. Surface generation restores the source crater workload and matches all
deterministic bytes covered by the current type sweep. The known final four
surface-texture bytes are documented as NIV+/vanilla undefined data rather than
being fitted to one arbitrary memory capture.

Large stellar identities now pass through Borland's real qword `__ftol`
boundary before their low 16 bits seed the class stream. The earlier dword
store returned the integer-indefinite pattern beyond signed 32-bit and could
generate a completely different system. The two affected `NOCHUT` rows now
match all 22 public orbital and landed hashes; the bounded ten-row type-2
Rust-error sample is exact on all 110 fields.

The optional 60 Hz path now presents completed simulation states at stable
boundaries and keeps original gameplay cadence. Surface panorama addressing is
canonicalized before sampling, removing the moving black horizon pillar, and
the refreshed frozen-world frame no longer contains its former diagonal stroke
or blown-out foreground cluster.

The smooth presenter now derives its 18.206-Hz simulation remainder from the
calibrated high-resolution counter instead of a whole-millisecond wall clock.
The conversion splits whole milliseconds from the sub-millisecond remainder to
stay inside 32-bit arithmetic and carries the division residue across frames.
This removes roughly 1.8-percent interpolation-phase steps without changing the
authoritative simulation rate, state order, or the original presentation mode.
A ten-second habitable-world smoke with terrain, fauna, and storm rendering
completed at 62 reported FPS with 10.29 ms render and 2.98 ms present time.
A separate 30-second real-input session held forward continuously and alternated
left and right yaw. It completed without a crash, terrain loss, black horizon
pillar, or input stall, and retained the world detail in all four live frames.

The common 640x400 host path now expands the complete indexed page through the
live RGB palette and performs its exact 2x duplication in bounded native loops.
This removes 32,000 interpreted presenter iterations per frame while retaining
the generic resizable aspect-fit path. Fresh production captures measured 56
to 61 FPS across every landable planet class and 58 FPS in the Stardrifter;
the slowest measured surface render was 10.69 ms.

Surface turns now clear the page and run the 3,670-record wrapped panorama
mapper and its five-row stamps in native kernels. Storm inversion likewise
avoids 80,000 interpreted source-pixel iterations per lightning frame. A
full-context thin-atmosphere page remains byte-exact against the NIV+ oracle
after the changes.

The shared polygon framebuffer load and store primitives now perform their
fixed page addressing, 16-bit DOS wrap, and byte masks in native code. This
benefits solid and effect polygons across surface and Stardrifter views. All
107 joined exact raster corpus pages remain byte-identical after the change.

Flat solid and colour-ramp polygon spans now write each complete run in one
native loop instead of making an interpreted framebuffer call per pixel. The
same exact raster corpus remains byte-identical, including its fill counters,
and a fresh Stardrifter smoke held the hull pass at 2.43 ms.

The solid-polygon sentinel searches now execute their exact `repne` and
`repe` scan semantics in native loops. In consecutive fixed Stardrifter
captures, total render time fell from 6.17 ms to 4.79 ms and the hull pass
from 2.43 ms to 1.51 ms. All 107 exact raster pages remained byte-identical.

Solid polygon edge strokes now execute both the vertical and general DDA
trace loops natively while retaining the original inclusive vertical rule,
half-open greater-X endpoint, and 16-bit page wrap. The exact raster corpus
remains byte-identical and a fresh Stardrifter capture rendered in 4.75 ms.

Additive effect polygons now execute each complete source-dependent fill run
in one native loop, preserving the previous-pixel sampling order and original
clamp at colour 62. The exact raster pages remain byte-identical and the live
Stardrifter sun and corona smoke remains intact.

Halo effect polygons now execute both source paths natively, including the
historical `di-321` and `di-642` neighbor samples and the remaining-run-length
brightness term. Exact raster pages remain byte-identical, and a fresh
multi-sun Stardrifter smoke rendered intact in 4.52 ms.

That fixed 2x path now publishes each duplicated RGB pixel to Backdrop and
Primary Display while the value is already loaded. The two synchronized layers
therefore no longer need a subsequent 1 MiB Backdrop reread and copy. Resized
windows now run the same integer nearest-neighbour accumulator in a native
single-layer scaler before the normal iGUI copy, while the default path retains
the same cursor composition and physical retrace order.

The timing servo now derives its maximum sampling window from the live host
counter rate, capped at 60 seconds and kept fourfold inside the 32-bit counter
ring. A synthetic million-counts-per-millisecond replay rejects every unsafe
window instead of accepting an aliased delta, while ordinary host timing and
the original 18.206 Hz gameplay cadence remain unchanged.

Close stellar coronas are bright filled discs again. The second and third
stellar palette ramps had inherited the previous shade routine's divisor, so
otherwise correct high-index sun pixels were mapped back toward black. Each
ramp now restores the unit divisor before converting its endpoint colors. A
Borland-built NIV+ source oracle at the same star, camera, distance, and class
confirmed the expected filled white center. The reproducible capture harness
continues to identify its deliberately limited synthetic state as version 15;
it does not invent the transient lighting/reset word added to live version-16
saves.

Close local planets now select their intended ring, disc, and resident-surface
LOD paths. Six comparison results had accidentally been tested as unsigned, so
the near result `-1` always took the far-point branch. The local-body pass also
installs its zero-origin exterior camera explicitly instead of inheriting the
previous frame's final interior fixture view.

Ocean horizons now use a clipped, stable sea-palette backdrop rather than
mapping terrain bytes across a behind-camera quad. This removes the flickering
rainbow strip seen at shoreline viewpoints while preserving foreground land,
reflections, waves and surface life.

The gallery now includes a separate close view of LANE IV's naturally generated
source-model hopper. The reproducible checkpoint starts near its deterministic
fauna record; it does not inject or replace an animal for the capture.

Type-1 lunar landings retain the source's complete zero-to-thirty height-crater
field, uncapped texture-crater field, dark lines, rocks, mottling and airless
presentation. A radial profile cache reuses the identical float result for
pixels at equal integer squared radius, accelerating the authentic workload
without shrinking or removing terrain content. The crater loop now also clips
its side-effect-free map bounds once, advances squared radius and map address
by exact integer recurrences, and inlines the already-bounded byte access. All
source crater calls, RNG draws, profile calculations, application ordering and
float-to-byte conversion points remain in place. On a radial-cache miss, the
same exactly representable integer `dx*dx+dz*dz` now feeds x87 `fsqrt`
directly, eliminating two conversions, two multiplies and an add without
changing the square root input. Texture dark lines likewise retain every
source step and both RNG draws per step while using the already masked texture
address directly and removing a post-mask upper-bound test that could never
succeed.

Galactic Cartography's manual Parsis target now accepts ten coordinate digits
plus an optional minus sign. This corrects the original ten-character editor
limit while retaining signed 32-bit range checks, so the distant Feltyrion
region is reachable without wrapping a coordinate.

Landed terrain now uses NIV+'s fully textured unit-tile depth-64 mesh, source
triangle-facing test and view-quadrant painter order. The invented 8/32-tile
mesh and compensating late ruins pass were removed; they caused moving walls
and erased real terrain detail. The panorama cursor now follows NIV+'s exact
pitch/yaw formula. Equivalent negative headings are canonicalized before both
cursor calculations, preventing the source mapper from sampling the 736-byte
allocation tail as a moving black five-pixel pillar. Its signed shift is also
formed in a clobber-safe order instead of retaining arithmetic scratch state.
An off-screen `polymap` rejection and the source Manhattan gate reduce only
work that cannot contribute pixels. Texture-basis construction now occurs
after that rejection, cutting the hidden lunar checkpoint from 38,792,130 to
31,852,389 render counts and from 6,689 to 5,728 ms for 60 frames. Specialized
bounded surface-map reads were remeasured against the preceding committed
binary with the same ten-second hidden warmup: they reduced the steady
12-frame sample from 1,973 to 1,311 ms and the 60-frame wall time from 10,237
to 6,650 ms, raising the measured rate from 6 to 9 FPS. A subsequent exact
fusion of the per-tile x87 distance chain retained every qword spill, square
root and chop-conversion boundary; in
a same-scene hidden A/B against its immediate predecessor, the 11-frame sample
fell from 1,482 to 1,329 ms and the 60-frame wall time from 6,858 to 6,665 ms.
The landed projection cache now takes a direct three-vertex hit path instead
of re-entering six small index/validation routines for every reused triangle.
On the same retained lunar checkpoint, the 60-frame render profile fell from
1,422 to 1,207 ms and render-plus-presentation from 1,732 to 1,481 ms, raising
the unconstrained measured rate from 34.64 to 40.52 FPS.

Further exact terrain work fused the mapper's bounded spans, cached repeated
terrain normals and projections, reused stationary-frame projections, and
combined the source Manhattan admission with its accepted-cell x87 depth
schedule. On the repaired retained lunar checkpoint, two immediate 60-frame
runs of the committed baseline measured 70.52 and 70.43 FPS including
presentation, crossing the optional 60-Hz presenter's target on the test host.
This is a scene and host measurement, not a minimum guarantee for every planet
or machine. A native landed-sky cache copy was removed after visual bisection
showed that it erased the local sun's source lens-flare halo. The defect in
that implementation is identified and corrected below.

The sky-cache copy is native again after correcting the actual defect in that
earlier attempt: it changed EDI to the destination before loading the workspace
copy count, then copied a framebuffer-derived garbage length. The corrected
loop keeps the workspace base intact and preserves the sun halo. Stationary
source ticks now retain the exact terrain projection cache because waves,
weather, and fauna do not mutate the ground grid. Off-screen fauna keep their
simulation and RNG schedule but skip model deformation only when a conservative
whole-model frustum bound proves they cannot contribute a pixel. Distant fauna
also skip midpoint rebuilding when the source has already disabled depth sort.
The fixed pvfile float accessors and animal model-block copy no longer rebuild
generic region addresses for every byte. In the retained F5 scene sweep,
Stardrifter and the simpler landed worlds remained inside the 60 Hz budget; the
heaviest habitable samples measured about 15.0 ms render plus 1.2 ms present,
with wildlife-dependent runs near the boundary rather than the former 20 to
23 ms render cost.

Nearby mammals and birds now defer polygon-midpoint rebuilding until their
last articulated body transform. The original path rebuilt the complete model
after scaling, each limb or wing operation, gait, inclination, and heading,
although no draw or later transform observed any intermediate midpoint set.
The final coordinates, one final midpoint set, depth sort, painter order, and
RNG schedule are unchanged. A controlled fixed-checkpoint smoke using the
committed predecessor and the new executable measured the same habitable scene
at 12.06 ms and 10.08 ms render time respectively, with the new run holding
59 FPS. This one-scene measurement is evidence of the removed work, not a
minimum guarantee for every fauna population or host.

Ordinary generated worlds now bypass the four per-tile ruin-marker probes when
the authoritative historical-ruin anchor is absent. Those surfaces begin with
an explicitly wiped ruin chart and have no writer outside the anchored ruin
generator, so the shortcut removes only repeated reads of known zeroes while
the three historical systems retain the complete marker path.

Close surface stones now follow NIV+'s complete `roccia()` path: type-3
generation retains the final `random(5)` quartz choice, type-8 sets quartz
unconditionally, close-rock RNG draws keep their source order, rear faces use
the source's inverse-facing gate, depths zero and one map `p_background` as a
four-vertex degenerate face, and depth two remains solid. The former flat,
unculled close faces made an observer standing inside a dense crystal group
look like a moving wall. The reproducible lunar capture now starts at its
measured terrain-relative eye height and faces the clean 90-degree green-sun
composition; the promoted frame retains genuine crystals without presenting
an inside-a-crystal view as landscape evidence.

The earlier release audit passed all 24 then-registered suites. The integrated
build/flight/render/present loop also completed 600,000 frames in 8,125.55
seconds (2 h 15 min 25.55 s) at 73.84 FPS, with advanced state and power,
nonzero framebuffer samples, exact terminal telemetry, and a clean exit. That
ship-mode soak predates the faithful landed renderer and is not evidence of
the current surface frame rate.

## What is playable

- Walk through the Stardrifter interior, use the roof lift, explore the roof,
  and operate the onboard devices.
- Use GOES to select a nearby generated star or enter exact coordinates.
- Fly through the deterministic Feltyrion galaxy and inspect generated systems.
- Select generated planets and moons, approach them, choose longitude/latitude,
  and land in the physical capsule.
- Walk generated surfaces with distinct terrain classes, skies, weather,
  source-positioned local suns, vegetation, animals, capturable birds, ruins,
  water/ice effects, jump, and jetpack behavior.
- Return to the capsule and Stardrifter, manage power and lithium, collect fuel,
  or request the complete two-minute rescue fly-by with a second lit
  Stardrifter.
- Stellar lithium collection now preserves the original class-5 minimum yield,
  class-6 distance failure, reached-target gate, collection during planetary
  approach, `+1` distance term, and continuously refreshed status feedback.
- Save and resume versioned checkpoints. Verified saves retain a backup and a
  damaged primary visibly recovers from the last-known-good copy.
- Resize the native iGUI window while the authentic 320x200 renderer remains
  nearest-neighbor scaled and aspect fitted.
- F5's optional 60-Hz presenter now interpolates simulation-driven flight,
  roof-lift, capsule descent/recovery, ordinary player poses, and surface
  mammal/bird translation, gait, wing articulation, ocean swell, player wakes,
  and class-specific close-star rotation while leaving gameplay at the original
  18.206-Hz cadence. Non-spinning star classes retain the source's separate
  clock-driven globe phase, and the physical orbital console no longer runs
  faster when F5 is active. Its interpolation phase follows measured scheduler
  time, eliminating the periodic catch-up step between uneven presentation gaps.
- Surface mammals no longer snap between four cardinal travel directions.
  Their source-seeded stop and turn decisions, species speed ranges,
  scale-dependent reaction, continuous heading, and sine/cosine movement are
  restored from `live_animal`.
- Surface birds now use `live_animal`'s continuous flight path as well, including
  its grounded, descent, low-altitude and high-altitude regimes, deterministic
  heading and altitude wander, and cautious-approach takeoff response.
- Wildlife RNG schedules now use NIV+'s raw 18 Hz tick. Mammal turn and stop
  decisions plus low-, mid-, and high-flight bird wandering no longer wait on
  an invented one-second quantization.
- Flying bird wings now use NIV+'s global six-tick and twenty-tick flap cycles;
  the port's invented per-bird phase offset is gone.
- Surface rain now reacts to the player's movement as well as atmospheric
  wind, restoring NIV+'s per-tick apparent streak direction.
- Storm drops now use the original backward-shifted rain camera and luminous
  line mode, with both states restored before subsequent rendering.
- Lightning restores NIV+'s raininess-scaled probability and variable palette
  intensity instead of using coarse probability buckets and one fixed blend.
- Lightning now activates on the source-ordered following tick and temporarily
  inverts the mapped sky source, restoring the original illuminated cloud flash
  without persisting the inverted panorama in the cache.
- Ground birds now fold both wing groups at the source's scale-dependent rate
  instead of sharing an oversized fixed-altitude closing ramp.
- Ocean-world birds use their sampled ground height as well as the biome when
  choosing between grounded and flight poses, restoring island behavior.
- Captured birds restore all five original trailing cords around the player.
- Those cords now apply the original short-lived drag to surface momentum while
  their capture counter relaxes.
- Wildlife range now includes vertical separation through the original 3D
  distance calculation. Mammals restore planetary skin mapping; close birds
  alternate the original textured and recursively remapped appearances, with
  depth sorting enabled at the source threshold.
- Out-of-range wildlife now re-enters around the player through the original
  live RNG continuation and complete 100,000-unit draw range instead of
  repeating a truncated fixed offset. Presentation-only F5 frames no longer
  mutate relocation state.
- Rare mammals generated on open-ocean biomes now use the original swimming
  silhouette and stroke: flattened body, hidden legs, raised pitch, and a
  smoothly presented half-second oscillation replace the terrestrial gait.
- Terrestrial mammal animation now follows NIV+'s shared half-second clock,
  exact species bounce amplitudes, full body/rear articulation, and
  source-indexed idle-tail selection instead of the port's per-animal wobble.
- Mammal posture now uses the original forward terrain sample and atan slope
  calculation, including its full 45-degree inclination range.
- The documented GOES `PRIF name[:X..Y]` module is live and writes its selected
  72-column Galactic Guide stream to the historical `GDOUTPUT.TXT` file.
- GOES `X text` restores the Release 9 Xnice file bridge, including active
  `X.TXT`, FIFO `XBUFF.TXT`, and bare-`X` promotion. `IMPORTGD` now explains why
  its NICE-only old-to-new database conversion does not apply to this build.
- Toggle Ryan J. Bury's manual soundtrack with F8; silence remains available.
- Save the completed 320x200 game view with M or `*`. Numbered BMP files are
  written to `GALLERY` without overwriting earlier captures.
- Open the original moviemaker with F3 and record numbered raw 320x200 frames
  into selectable `MOVIES\DDD` decks, with the source interval, flash, pause,
  resume, frame count, and rate controls.
- F1 restores the original framed Noctis IV+ About page with separate ship and
  surface text. F9 or `?` retains the accurate current-port control card.

## Important behavior in this build

- Descending terrain traversal now stops safely at map-edge zero instead of
  interpreting a negative tile index as unsigned and clearing or crashing the
  surface frame.
- Surface gravity, backward/lateral momentum, slope motion, and capsule
  centring use signed arithmetic. Backward input no longer launches the player
  across the planet, and re-entry pulls inward correctly from every side.
- Surface and capsule coordinates can no longer pass through the ship-interior
  clamp. Interrupted old checkpoints settle at the persisted pod rather than
  resuming underground.
- The settled pod is mapped and transparent, keeps the source structural line
  modes and sky beacon, opens locally as the player leaves/re-enters, seals for
  32 original ticks, and returns after the source 250-tick ascent.
- Capsule simulation now uses elapsed wall time at a fixed 18.206 Hz and hands
  back to the Stardrifter only at a clean top-level frame boundary.
- Ylastravenia body 3 at LQ 018:060 restores the source's separate 25x25
  Suricrasian Cube landmark and marked wall faces.
- Focus changes no longer let a re-entrant iGUI repaint corrupt the live game
  frame. The supported iGUI size control scales both ship and surface views.

- This is the first prerelease produced by the automated tagged GitHub path.
  GitHub reran the focused regression, verified the versioned i386 PE, built the
  standalone ZIP, and published its checksum and explicit build provenance.
- The authentic 18.206 FPS presentation is the default.
- F5 opts into the higher presentation rate; simulation remains 18.206 Hz in
  either presentation mode.
- Capsule settlement now resets the final airborne presentation sample before
  the landed LOD renderer starts. Optional 60-Hz mode no longer crashes on the
  first walking frame after a live descent.
- Surface walking now retains the original forward and lateral momentum,
  asymmetric ground friction, steep-uphill resistance, tiredness input, and
  circular landed/airborne exploration limits. WASD, held left-click, and digit
  cruise all feed that same source-ordered motion.
- F2 opens the source-equivalent visual-effects card. T toggles passive HUD
  text, F cycles visor-only/always-on/always-off flare reflections, and B
  selects the default or seamless visor border. These choices persist.
- Page Up and Page Down animate the source visor edge at its original five
  lines per simulation tick; visor-only reflections follow its closed state.
- Landed views restore the original 3x5 SQC location readout, scrolling compass
  strip, and four corner HUD lamps; jetpack thrust produces the bright flash.
- Ship and surface visors restore the live Noctis EPOC clock and its three
  zero-padded sub-billion second triads.
- The ship visor again carries the compact source command strip. Large temporary
  power, capsule, FCS, and body rows no longer cover ordinary gameplay; FCS stays
  on its original 3D HUD path, and X returns from onboard pages to the clear view.
- Landed gravity, temperature, pressure, and pulse now use the original indexed
  3x5 lower-visor line and source smoothing rates instead of an oversized host-font row.
- The Stardrifter is visible from the initial frame and remains stable during
  movement.
- The Stardrifter hull now uses the original live palette instead of a fixed
  cobalt tint. Selected-star color and distance, navigation heading, planetary
  eclipses, and the internal lamp's gradual 0-through-63 fade all affect its
  lighting at the authentic simulation cadence, without presentation-mode
  flicker.
- True emergency illumination is now separate from ordinary hull lighting.
  Depleting both power and lithium blacks the wall-console text, disconnects
  navigation, suppresses the normal halogen reflection, and enables only the
  source's intentional emergency flicker. Rescue transmission adds its exact
  recurring 63-tick signal and four-frame white hull pulse, while onboard reset
  restores systems through the original staged 150-step sequence.
- Approaching stars now cross the source's actual geometric detail thresholds:
  the luminous shell appears inside 100 stellar radii and the textured globe
  inside eight, independently of the autopilot's final arrival flag. From
  1,550 to 100 radii the selected target also gains the source's rising,
  three-pass light-emitting point and complete spread halo. Inside eight radii,
  its full 64,800-texel stellar surface cycles at the original source cadence.
- Close stars now recover the source's live distance response: globe detail
  uses the per-star seeded saturation floor, nearby stellar colors whiten with
  distance, and all six palette endpoints ease by one unit per source tick.
  The original `sqrt(...)+1` boundary arithmetic is retained.
- Space stars now restore the original pre-mask optical pass. Beyond six
  radii, eligible stellar classes produce the source's 60-spoke visor flare
  below 1,000 radii, including the rotating class-11 visibility gate. The
  exact four-row grayscale smoother then softens the space field before its
  conversion into stellar palette band 64.
- Generated companion stars now contribute their original flare as well as
  their corona when the Stardrifter lies between five and 1,000 companion
  radii. Their source float distance rounding and shared visor reflections are
  retained.
- Space frames now follow the original palette and draw order: luminous
  coronas are drawn first, the central space viewport moves into stellar band 64,
  resolved globes and planets follow, and the generated galaxy is submitted
  only after the Stardrifter. The source `sky(0x405C)` target gate therefore
  keeps stars behind the hull while allowing approach halos to brighten space.
- During Vimana flight, the central 182-row space viewport now retains and
  fades its prior low-six-bit intensities by eight instead of being cleared.
  Moving stars consequently leave the original short luminous trails.
- E directly starts the source lift event while inside the Stardrifter. Up
  remains a look control, and walking into the roof cupola opening starts the
  original automatic return. The calibrated ascent retains the source's
  forward momentum through the final roof frame, carries the player clear, and
  uses the same heading for the view and ride motion.
- Facing the first right-wall computer and pressing Enter focuses physical
  GOES. Command input and retained output use the original mapped 32x36 font
  directly on the wall faces. `HELP` restores the exact original seven-row
  resident module directory. The original resident `CLR` command clears the
  output tree, while `WHERE <catalogued name>` searches the mutable starmap,
  distinguishes stars from planets, reports ambiguous prefixes, and resolves
  a planet's parent star. Bare `SL` lists every non-removed star in source file
  order. Its 7,586 output rows fit in the expanded 8,192-row scrollback, and
  literal underscores in catalogue names remain visible. `SL <range>` runs
  the original centred procedural scan, reports matching stars with X, -Y, Z,
  and two-decimal light-year distance, and can be interrupted with Escape while
  the window remains responsive. `PAR <catalogued
  name>[:range]` now regenerates the
  original procedural sector cube and reports X, -Y, Z coordinates. The G
  shortcut includes the same seven retained output rows as the wall display.
  `ST <catalogued name>[:range]` now sends a resolved star to Vimana or begins
  local drive for a named planet belonging to the currently reached system.
  `DL <catalogued name>[:range]` now regenerates the requested system and lists
  its charted planets, moons, and Guide note counts in the original dependency
  tree. Bare `DL` examines the current remote target, and every query restores
  the player's prior generated system and selected body.
  `CAT <catalogued name>[:X..Y]` reads the original 48,376-record Galactic
  Guide with its source one-based ranges and 21-column word wrapping.
  `PRI <catalogued name>[:X..Y]` selects the same subject records and exports
  them beside the game as `GUIDE-PRINT.TXT`, preserving the original heading,
  padded subject label, continuous message stream, CRLF lines, and 72-column
  printer word wrapping.
  `CAST <catalogued name>:<notes>` appends a source-compatible 84-byte record
  after the consolidated guide boundary. Notes are limited to 76 characters,
  persist in `GUIDE.BIN`, and are readable by a later `CAT` command.
  `REP <catalogued name>:<record>:<notes>` corrects a selected local record
  while retaining the original module's protection for consolidated entries.
  `DELE <catalogued name>[:X..Y]` applies the original `Removed:` tombstone to
  ranged local entries and reports total, removed, and protected counts.
  `CLEAN` compacts tombstones from both mutable databases and preserves the
  consolidated source boundary separately from appended player data.
  `REPAIR` restores the original first-record-wins duplicate scan. It uses the
  source identity window for STARMAP and requires both that subject match and
  an exact 76-byte comment for GUIDE, then leaves compaction to `CLEAN`.
  `OUTBOX` exports only those live player additions to `OUTBOX.ZIP` using the
  original `STARMAP_` and `GUIDE___` packet framing, ready to copy to another
  Stardrifter installation.
  `INBOX` completes that exchange path. It validates a received `INBOX.ZIP`
  before writing, imports non-duplicate records into the consolidated archives,
  replaces matching local copies, retains unrelated local additions, and can
  restore both original database images if a write fails.
  The third station starts planetary approach and,
  after FCS reaches STANDBY, opens the physical longitude/latitude selector.
- Planetary views finish with the original default `surrounding()` visor
  frame. Its stable graded edge replaces both the incorrect bright sawtooth
  and the intermediate plain-black guard without changing polygon clipping.
- The Stardrifter's physical Preferences control restores the original PFS page:
  auto screen sleep, reversed navigation steering, auto-hidden menus, and the
  polarized/depolarized hull are functional rather than opening the F2 card.
  A resize-aware GAME-menu mirror exposes the same four commands and cleanly
  returns control to the physical computer when closed.
- The native GAME dropdown now installs and displays all twelve actions; its
  former eight-entry capacity silently clipped the final four menu commands.
- Emergency assistance now shows the complete second Stardrifter hull between
  its source-ordered near and far cupola passes throughout the two-minute orbit.
- Version 16 saves additionally retain the internal lamp's exact fade level,
  emergency illumination, rescue-signal phase, and staged reset progress.
  Versions 1 through 15 migrate without stranding the player or losing their
  established defaults.

## Run it

### Windows

Extract `Noctis-IV-windows-x86.zip` without removing individual files, then
double-click `Play Noctis IV.cmd`. The launcher keeps assets, `CURRENT.LIN`,
`CURRENT.BAK`, mutable `STARMAP.BIN`, mutable `GUIDE.BIN`, and diagnostics in
the extracted game folder.

### macOS

Verify and extract `Noctis-IV-macos-x86_64.zip`, drag `Noctis IV.app` to
Applications, and open the app rather than its nested game executable. Intel
Macs run the x86_64 app directly; Apple Silicon requires Rosetta 2. The app is
ad-hoc signed and not notarized. If first launch is blocked, approve Noctis IV
under System Settings, Privacy & Security, then open it again.

The Mac launcher stores mutable state under
`~/Library/Application Support/Noctis IV`. Back up `CURRENT.LIN`,
`STARMAP.BIN`, and `GUIDE.BIN` from that directory to preserve the journey and
player catalogue additions.

Useful controls:

- W/A/S/D: move; held left-click also walks forward on surfaces; right-drag or arrows: look
- E inside the Stardrifter: ascend; walk into the roof opening to return
- First wall panel + Enter: physical GOES; `NEXT`: choose/fly to a nearby star
- `SL` lists all known stars; `SL <range>` scans locally; Escape stops a scan
- `CAT`: read; `PRI`: text export; `CAST`: add; `REP`: correct; `DELE`: remove;
  `REPAIR`: find duplicates; `CLEAN`: compact
- `OUTBOX`: export player data; `INBOX`: import a received `INBOX.ZIP`
- Third wall panel + Enter: approach, select a landing site, and descend
- G and L: accessible GOES and landing fallbacks
- R: device back/close aboard ship; return in capsule on a surface
- F2: visual effects; Page Up/Down: visor; F4: FPS display; F5: higher presentation rate
- F6/F7: save/load; F8: music; M or `*`: numbered Gallery snapshot
- B, or surface Delete: raw Gallery snapshot without port display overlays
- F3: moviemaker; +/-: interval; Ctrl +/-: deck; F: flash; Enter/P: record/pause
- Surface N or `/`: 916x200 panorama; V or `.`: raw panorama
- Plus/minus: adjust the original HUD and visor-frame brightness
- F1: original About page; F9 or `?`: complete current-port control card
- Esc: save and quit

## Known limitations

- The Mac package is x86_64. Apple Silicon needs Rosetta 2; a native ARM64 CPU
  pack and runtime remain unfinished.
- The Mac app is ad-hoc signed, not Developer ID signed or notarized, and does
  not enable hardened runtime. First launch can require explicit approval in
  macOS Privacy & Security.
- The historical Linux runtime's PCM layer remains a stub. The packaged Windows
  and macOS hosts both have soundtrack output, but Linux is not a packaged game
  target.
- Hosted source builds require the historical compiler's 32-bit glibc/X11
  dependencies and an explicit Linux executable-heap compatibility boundary;
  release workflows install and bound that environment automatically.

## Integrity and licence

Both platform packages include `MANIFEST.sha256` payload coverage. The Windows
manifest covers every bundled payload file. The Mac manifest covers `Info.plist`,
the nested game, and immutable Resources; codesign verifies the launcher and
signature material separately, and package provenance hashes the launcher,
manifest, and signed game. The GitHub release supplies a checksum and explicit
provenance record beside each ZIP. The macOS record also distinguishes the
original compiler output, normalized unsigned Mach-O, unchanged appended Lino
payload, signed executable, and exact Rosetta result.

Noctis IV and Noctis-derived port material are distributed under the original
WTOF Public License included as `WPL.htm`, with Alessandro Ghignola's
authorization for this port and the condition that original gameplay be
preserved. Redistribution must remain free and comply with the included terms.
Original Noctis IV and L.in.oleum credits belong to Alessandro Ghignola;
manual/soundtrack portions are credited to Ryan J. Bury.

For the full development timeline and technical evidence, see `HISTORY.md` and
`PLAYTEST.md` in the source repository.
